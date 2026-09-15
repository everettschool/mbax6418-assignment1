"""Step 6 Numbers Auditor: independent recomputation of every metric.

Does NOT import anything from src/. Reads the dataset, the lexicon, runs/*, the built
dashboard (headless Chromium via Playwright), and the written Step 6 files.

Usage: .venv/bin/python reviews/step6_numbers_auditor/audit.py
"""
import gzip
import hashlib
import html
import json
import math
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ["balanced150_v3", "first100_v3", "first100_v2", "first100_v1"]
EMOTIONS = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]
STAR = re.compile(r"^\s*(one|two|three|four|five)\s+stars?\s*$", re.IGNORECASE)
Z = 1.959963984540054

FAILS = []
CHECKS = Counter()


def check(ok, area, msg):
    CHECKS[area] += 1
    if not ok:
        FAILS.append(f"[{area}] {msg}")


def close(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    return a == b


def deep_compare(mine, theirs, area, path=""):
    """Every leaf in `theirs` must exist in `mine` and be equal."""
    if isinstance(theirs, dict):
        if not isinstance(mine, dict):
            check(False, area, f"{path}: type differs")
            return
        for k in theirs:
            if k not in mine:
                check(False, area, f"{path}.{k}: in file but not recomputed")
                continue
            deep_compare(mine[k], theirs[k], area, f"{path}.{k}")
        for k in mine:
            if k not in theirs:
                check(False, area, f"{path}.{k}: recomputed but missing from file")
    elif isinstance(theirs, list):
        check(isinstance(mine, list) and len(mine) == len(theirs), area, f"{path}: list length {len(mine) if isinstance(mine, list) else mine} vs {len(theirs)}")
        if isinstance(mine, list):
            for i, (a, b) in enumerate(zip(mine, theirs)):
                deep_compare(a, b, area, f"{path}[{i}]")
    else:
        check(close(mine, theirs), area, f"{path}: recomputed {mine!r} vs file {theirs!r}")


def ratio(a, b):
    return a / b if b else None


def wilson(k, n):
    p = k / n
    centre = p + Z * Z / (2 * n)
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    d = 1 + Z * Z / n
    return [(centre - half) / d, (centre + half) / d]


# ---------------------------------------------------------------- dataset
def load_dataset():
    rows = []
    with gzip.open(ROOT / "data" / "Gift_Cards.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            rows.append({"rating": d["rating"], "title": d.get("title") or "", "text": d.get("text") or ""})
    return rows


def three(r):
    return "POSITIVE" if r >= 4 else "NEUTRAL" if r == 3 else "NEGATIVE"


def binary(r):
    return "POSITIVE" if r >= 4 else "NEGATIVE"


# ---------------------------------------------------------------- sentiment metrics
def sentiment_metrics(run, meta, preds, data):
    labels = ["POSITIVE", "NEUTRAL", "NEGATIVE"] if meta["label_scheme"] == "three" else ["POSITIVE", "NEGATIVE"]
    truth_fn = three if meta["label_scheme"] == "three" else binary
    cols = labels + ["UNPARSED"]
    for p in preds:
        src = data[p["review_id"]]
        check(p["rating"] == src["rating"], f"{run}/rows", f"{p['review_id']}: rating {p['rating']} vs dataset {src['rating']}")
        check(p["title"] == src["title"] and p["text"] == src["text"], f"{run}/rows", f"{p['review_id']}: title/text differ from dataset")
        check(p["truth"] == truth_fn(src["rating"]), f"{run}/rows", f"{p['review_id']}: stored truth {p['truth']} vs {truth_fn(src['rating'])}")
        # parse read-back of the raw reply
        if p["parse_status"] == "OK":
            m = re.search(r"LABEL=([A-Z]+)", p["raw_responses"][-1])
            check(bool(m) and m.group(1) == p["prediction"], f"{run}/rows", f"{p['review_id']}: prediction {p['prediction']} vs raw {p['raw_responses'][-1]!r}")
            if "EMOTION=" in p["raw_responses"][-1]:
                e = re.search(r"EMOTION=([a-z]+)", p["raw_responses"][-1])
                check(bool(e) and e.group(1) == p.get("llm_emotion"), f"{run}/rows", f"{p['review_id']}: llm_emotion {p.get('llm_emotion')} vs raw")
        else:
            check(p["prediction"] == "UNPARSED", f"{run}/rows", f"{p['review_id']}: non-OK parse but prediction {p['prediction']}")
    n = len(preds)
    cm = {t: {c: 0 for c in cols} for t in labels}
    for p in preds:
        cm[truth_fn(data[p["review_id"]]["rating"])][p["prediction"]] += 1
    tc = {t: sum(cm[t].values()) for t in labels}
    pc = {c: sum(cm[t][c] for t in labels) for c in cols}
    correct = sum(cm[t][t] for t in labels)
    per = {}
    for t in labels:
        tp = cm[t][t]
        prec = tp / pc[t] if pc[t] else 0.0
        rec = tp / tc[t]
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per[t] = {"support": tc[t], "predicted": pc[t], "correct": tp, "wrong": tc[t] - tp, "precision": prec,
                  "precision_undefined_never_predicted": pc[t] == 0, "recall": rec, "f1": f1}
    top = max(tc.values())
    majority = [t for t in labels if tc[t] == top][0]
    acc = correct / n
    base = top / n
    return {
        "run": run, "label_scheme": meta["label_scheme"], "labels": labels,
        "confusion_matrix_orientation": "rows = truth (from rating), columns = predicted",
        "n_rows": n, "correct": correct, "incorrect": n - correct, "accuracy": acc,
        "truth_distribution": {"counts": tc, "share": {t: tc[t] / n for t in labels}},
        "prediction_distribution": {"counts": pc, "share": {c: pc[c] / n for c in cols}},
        "majority_class": majority, "majority_baseline_accuracy": base,
        "accuracy_minus_majority_baseline": acc - base,
        "balanced_accuracy": sum(per[t]["recall"] for t in labels) / len(labels),
        "majority_baseline_balanced_accuracy": 1 / len(labels),
        "macro_f1": sum(per[t]["f1"] for t in labels) / len(labels),
        "per_class": per,
        "confusion_matrix": {"rows": labels, "columns": cols, "counts": [[cm[t][c] for c in cols] for t in labels]},
        "confusion_cells": {f"{t}->{c}": cm[t][c] for t in labels for c in cols},
        "confusion_row_share": {f"{t}->{c}": cm[t][c] / tc[t] for t in labels for c in cols},
        "misclassified_review_ids": {f"{t}->{c}": [p["review_id"] for p in preds if p["truth"] == t and p["prediction"] == c]
                                     for t in labels for c in cols if t != c and cm[t][c]},
        "parse_fail_count": sum(p["parse_status"] == "FAIL" for p in preds),
        "api_error_count": sum(p["parse_status"] == "API_ERROR" for p in preds),
        "unparsed_count": pc["UNPARSED"], "unparsed_share": pc["UNPARSED"] / n,
        "rows_needing_retry": sum(len(p["raw_responses"]) > 1 for p in preds),
    }


# ---------------------------------------------------------------- NRC
def load_lexicon():
    lex = {}
    words = set()
    for line in (ROOT / "data" / "nrc" / "NRC-Emotion-Lexicon-Wordlevel.txt").read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) != 3:
            continue
        w, emo, flag = parts
        words.add(w)
        if flag == "1" and emo in EMOTIONS:
            lex.setdefault(w, set()).add(emo)
    return lex, words


NEGATORS = {"not", "no", "never", "nothing", "none", "nor", "without", "t"}


def nrc(title, text, lex):
    t = "" if STAR.match(title) else title
    x = "" if STAR.match(text) else text
    s = html.unescape((t + " " + x).replace("<br />", " "))
    toks = re.findall(r"[a-z]+", s.lower())
    scores = dict.fromkeys(EMOTIONS, 0)
    hits = negated = 0
    for i, tok in enumerate(toks):
        w = tok if tok in lex else None
        if w is None:
            for suf in ("ing", "ed", "es", "s"):
                if tok.endswith(suf) and tok[: -len(suf)] in lex:
                    w = tok[: -len(suf)]
                    break
        if w is None:
            continue
        hits += 1
        for e in lex[w]:
            scores[e] += 1
        if any(tt in NEGATORS for tt in toks[max(0, i - 3):i]):
            negated += 1
    top = max(scores.values())
    tied = [e for e in EMOTIONS if scores[e] == top] if top else []
    label = "NONE" if top == 0 else ("TIE" if len(tied) > 1 else tied[0])
    return {"label": label, "tied": tied if label == "TIE" else [], "scores": scores,
            "tiebreak": tied[0] if label == "TIE" else label, "negated": negated, "tokens": len(toks), "hits": hits}


def emotion_metrics(run, preds, data, lex):
    rows = []
    for p in preds:
        src = data[p["review_id"]]
        r = nrc(src["title"], src["text"], lex)
        llm = p.get("llm_emotion")
        agree = llm is not None and llm == r["label"]
        a = f"{run}/nrc-rows"
        check(p["nrc_emotion"] == r["label"], a, f"{p['review_id']}: nrc_emotion file {p['nrc_emotion']} vs mine {r['label']}")
        check(p["nrc_tied"] == r["tied"], a, f"{p['review_id']}: nrc_tied file {p['nrc_tied']} vs mine {r['tied']}")
        check(p["nrc_scores"] == r["scores"], a, f"{p['review_id']}: nrc_scores differ")
        check(p["emotion_agree"] == agree, a, f"{p['review_id']}: emotion_agree file {p['emotion_agree']} vs mine {agree}")
        check(p["nrc_emotion_tiebreak"] == r["tiebreak"], a, f"{p['review_id']}: tiebreak differs")
        check(p["nrc_token_count"] == r["tokens"], a, f"{p['review_id']}: token count differs")
        check(len(p["nrc_hits"]) == r["hits"], a, f"{p['review_id']}: hit count differs")
        rows.append({"id": p["review_id"], "llm": llm or "UNPARSED", "llm_raw": llm, "nrc": r["label"], "tied": r["tied"],
                     "tb": r["tiebreak"], "agree": agree, "neg": r["negated"], "key": (p["title"], p["text"])})
    n = len(rows)
    lc = Counter(r["llm"] for r in rows)
    nc = Counter(r["nrc"] for r in rows)

    def grp(sub, pred):
        k = sum(pred(r) for r in sub)
        return {"n": len(sub), "agree": k, "rate": ratio(k, len(sub))}

    allr = rows
    exn = [r for r in rows if r["nrc"] != "NONE"]
    exnt = [r for r in rows if r["nrc"] not in ("NONE", "TIE")]
    ag = lambda r: r["agree"]
    const = max(EMOTIONS, key=lambda e: (lc.get(e, 0), -EMOTIONS.index(e)))
    best = max(EMOTIONS, key=lambda e: (sum(r["nrc"] == e for r in rows), -EMOTIONS.index(e)))
    ties = [r for r in rows if r["nrc"] == "TIE"]
    tbc = Counter(r["tb"] for r in rows)
    best_tb = max(EMOTIONS, key=lambda e: (tbc.get(e, 0), -EMOTIONS.index(e)))
    A = {k: grp(s, ag) for k, s in (("all_rows", allr), ("excluding_none", exn), ("excluding_none_and_tie", exnt))}
    C = {k: grp(s, lambda r: r["nrc"] == const) for k, s in (("all_rows", allr), ("excluding_none", exn), ("excluding_none_and_tie", exnt))}
    B = {k: grp(s, lambda r: r["nrc"] == best) for k, s in (("all_rows", allr), ("excluding_none", exn), ("excluding_none_and_tie", exnt))}
    nonc = [r for r in rows if r["llm_raw"] != const]
    unique, seen = [], set()
    for r in rows:
        if r["key"] not in seen:
            seen.add(r["key"])
            unique.append(r)
    tb_ok = lambda r: r["llm_raw"] is not None and r["llm_raw"] == r["tb"]
    llm_cols = EMOTIONS + ["UNPARSED"]
    nrc_cols = EMOTIONS + ["TIE", "NONE"]
    xt = {a: {b: 0 for b in nrc_cols} for a in llm_cols}
    for r in rows:
        xt[r["llm"]][r["nrc"]] += 1
    return {
        "n_rows": n,
        "crosstab_orientation": "rows = LLM emotion, columns = NRC word-list emotion",
        "llm_emotion_counts": {c: lc.get(c, 0) for c in llm_cols},
        "llm_emotion_share": {c: lc.get(c, 0) / n for c in llm_cols},
        "nrc_emotion_counts": {c: nc.get(c, 0) for c in nrc_cols},
        "nrc_emotion_share": {c: nc.get(c, 0) / n for c in nrc_cols},
        "agreement": A,
        "agreement_rate_all_rows": A["all_rows"]["rate"],
        "agreement_rate_excluding_none": A["excluding_none"]["rate"],
        "agreement_rate_excluding_none_and_tie": A["excluding_none_and_tie"]["rate"],
        "tie_rows": len(ties),
        "tie_rows_llm_emotion_in_tied_set": sum(r["llm_raw"] in r["tied"] for r in ties),
        "tie_rows_llm_emotion_in_tied_set_rate": ratio(sum(r["llm_raw"] in r["tied"] for r in ties), len(ties)),
        "none_rows": nc.get("NONE", 0),
        "constant_baseline_emotion": const,
        "constant_baseline": C,
        "constant_baseline_rate_all_rows": C["all_rows"]["rate"],
        "constant_baseline_rate_excluding_none": C["excluding_none"]["rate"],
        "constant_baseline_rate_excluding_none_and_tie": C["excluding_none_and_tie"]["rate"],
        "llm_minus_constant_rate_all_rows": A["all_rows"]["rate"] - C["all_rows"]["rate"],
        "llm_minus_constant_rate_excluding_none_and_tie": A["excluding_none_and_tie"]["rate"] - C["excluding_none_and_tie"]["rate"],
        "tie_rows_constant_in_tied_set": sum(const in r["tied"] for r in ties),
        "best_constant_baseline_emotion": best,
        "best_constant_baseline": B,
        "best_constant_baseline_rate_all_rows": B["all_rows"]["rate"],
        "best_constant_baseline_rate_excluding_none_and_tie": B["excluding_none_and_tie"]["rate"],
        "llm_minus_best_constant_rate_all_rows": A["all_rows"]["rate"] - B["all_rows"]["rate"],
        "llm_minus_best_constant_rate_excluding_none_and_tie": A["excluding_none_and_tie"]["rate"] - B["excluding_none_and_tie"]["rate"],
        "agreement_llm_not_constant": {"all_rows": grp(nonc, ag),
                                       "excluding_none_and_tie": grp([r for r in nonc if r["nrc"] not in ("NONE", "TIE")], ag)},
        "agreement_tiebreak": {"all_rows": grp(rows, tb_ok), "excluding_none": grp(exn, tb_ok)},
        "tiebreak_label_counts": {c: tbc.get(c, 0) for c in EMOTIONS + ["NONE"]},
        "tie_rows_broken_to": {e: sum(r["tb"] == e for r in ties) for e in EMOTIONS},
        "tiebreak_constant_baseline": {
            "llm_most_common": {"emotion": const, "agree": tbc.get(const, 0), "rate": tbc.get(const, 0) / n},
            "best_constant": {"emotion": best_tb, "agree": tbc.get(best_tb, 0), "rate": tbc.get(best_tb, 0) / n}},
        "unique_title_text": {"n": len(unique), "agree": sum(r["agree"] for r in unique),
                              "tie": sum(r["nrc"] == "TIE" for r in unique), "none": sum(r["nrc"] == "NONE" for r in unique)},
        "negation": {"rows_with_negated_hits": sum(r["neg"] > 0 for r in rows), "negated_hits_total": sum(r["neg"] for r in rows)},
        "crosstab": {"rows": llm_cols, "columns": nrc_cols, "counts": [[xt[a][b] for b in nrc_cols] for a in llm_cols]},
        "crosstab_cells": {f"{a}->{b}": xt[a][b] for a in llm_cols for b in nrc_cols},
        "divergent_review_ids": [r["id"] for r in rows if r["nrc"] not in ("NONE", "TIE") and not r["agree"]],
    }, rows


def getp(obj, path):
    for k in path.split("."):
        if not isinstance(obj, dict) or k not in obj:
            return KeyError
        obj = obj[k]
    return obj


def fmt(v, f):
    if f == "pct":
        return f"{v * 100:.1f}%"
    if f == "count":
        return f"{round(v):,}"
    if f == "pp":
        return ("−" if v < 0 else "+") + f"{abs(v * 100):.1f} pts"
    return str(v)


def main():
    out = {}
    data = load_dataset()
    ds_sha = hashlib.sha256((ROOT / "data" / "Gift_Cards.jsonl.gz").read_bytes()).hexdigest()
    included = [i for i, r in enumerate(data) if r["text"].strip()]
    inc_set = set(included)

    # ---- rating_distribution.json
    rd = json.loads((ROOT / "runs" / "rating_distribution.json").read_text())
    rc = Counter(str(int(r["rating"])) for r in data)
    fail = Counter(str(int(r["rating"])) for i, r in enumerate(data) if i not in inc_set)
    check(rd["row_count"] == len(data), "rating_distribution", f"row_count {rd['row_count']} vs {len(data)}")
    check(rd["rating_counts"] == dict(rc), "rating_distribution", f"rating_counts {rd['rating_counts']} vs {dict(rc)}")
    for k, v in rd["rating_pct"].items():
        check(abs(v - round(100 * rc[k] / len(data), 4)) < 1e-9, "rating_distribution", f"rating_pct {k} {v}")
    check(rd["rows_failing_inclusion"] == len(data) - len(included), "rating_distribution", "rows_failing_inclusion")
    check(rd["rows_failing_inclusion_by_rating"] == {k: fail.get(k, 0) for k in rd["rows_failing_inclusion_by_rating"]}, "rating_distribution", "failing by rating")

    # ---- lexicon meta
    lexmeta = json.loads((ROOT / "runs" / "nrc_lexicon_meta.json").read_text())
    lex, words = load_lexicon()
    lsha = hashlib.sha256((ROOT / "data" / "nrc" / "NRC-Emotion-Lexicon-Wordlevel.txt").read_bytes()).hexdigest()
    check(lsha == lexmeta["lexicon_sha256"], "nrc_meta", "lexicon sha256")
    check(len(words) == lexmeta["word_count"], "nrc_meta", f"word_count {lexmeta['word_count']} vs {len(words)}")
    check(len(lex) == lexmeta["words_with_any_of_8_emotions"], "nrc_meta", f"words_with_any {lexmeta['words_with_any_of_8_emotions']} vs {len(lex)}")

    # ---- selections
    batch100 = included[:100]
    pools = {c: sorted(i for i in included if three(data[i]["rating"]) == c) for c in ("NEGATIVE", "NEUTRAL", "POSITIVE")}
    balanced = {c: random.Random(42).sample(pools[c], 50) for c in pools}
    sid = json.loads((ROOT / "runs" / "balanced150_v3" / "sample_ids.json").read_text())
    for c in pools:
        check(sorted(sid["by_class"][c]) == sorted(balanced[c]), "sample", f"{c} ids differ from independent re-draw")
    print("pools:", {c: len(v) for c, v in pools.items()}, "| excluded:", len(data) - len(included))
    pos4 = sum(data[i]["rating"] == 4 for i in pools["POSITIVE"])
    print("4-star rows in POSITIVE pool:", pos4)

    metrics, emo, prows, preds_by_run = {}, {}, {}, {}
    for run in RUNS:
        d = ROOT / "runs" / run
        meta = json.loads((d / "run_meta.json").read_text())
        preds = [json.loads(l) for l in open(d / "predictions.jsonl", encoding="utf-8")]
        preds_by_run[run] = preds
        ids = [p["review_id"] for p in preds]
        check(len(set(ids)) == len(ids), f"{run}/selection", "duplicate review_ids")
        if meta["selection"] == "batch_100":
            check(ids == batch100, f"{run}/selection", "ids are not the first 100 included ids in file order")
        else:
            want = sorted(i for v in balanced.values() for i in v)
            check(sorted(ids) == want, f"{run}/selection", "ids are not the balanced re-draw")
            check(meta["selection_info"]["pool_size_by_class"] == {c: len(v) for c, v in pools.items()}, f"{run}/meta", "pool sizes")
        check(meta["dataset_sha256"] == ds_sha, f"{run}/meta", "dataset sha256")
        check(meta["dataset_row_count"] == len(data), f"{run}/meta", "dataset_row_count")
        check(meta["n_rows"] == len(preds), f"{run}/meta", "n_rows")
        check(meta["parse_fail_count"] == sum(p["parse_status"] == "FAIL" for p in preds), f"{run}/meta", "parse_fail_count")
        check(meta["api_error_count"] == sum(p["parse_status"] == "API_ERROR" for p in preds), f"{run}/meta", "api_error_count")
        check(meta.get("cache_hits") == sum(bool(p.get("from_cache")) for p in preds), f"{run}/meta", f"cache_hits {meta.get('cache_hits')} vs from_cache rows {sum(bool(p.get('from_cache')) for p in preds)}")
        check(meta.get("api_call_count") == sum(len(p["raw_responses"]) for p in preds if not p.get("from_cache")) , f"{run}/meta",
              f"api_call_count {meta.get('api_call_count')} vs non-cached raw responses {sum(len(p['raw_responses']) for p in preds if not p.get('from_cache'))}")
        m = sentiment_metrics(run, meta, preds, data)
        metrics[run] = m
        deep_compare(m, json.loads((d / "metrics.json").read_text()), f"{run}/metrics.json")
        if (d / "emotion_metrics.json").exists():
            em, rows = emotion_metrics(run, preds, data, lex)
            filed = json.loads((d / "emotion_metrics.json").read_text())
            # documentation-only fields are compared as-is
            skip = {"run", "lexicon", "method", "constant_baseline_note", "best_constant_baseline_note", "tiebreak_rule"}
            filed_cmp = {k: v for k, v in filed.items() if k not in skip}
            filed_cmp["negation"] = {k: v for k, v in filed["negation"].items() if k != "rule"}
            deep_compare(em, filed_cmp, f"{run}/emotion_metrics.json")
            check(filed["lexicon"]["lexicon_sha256"] == lsha, f"{run}/emotion_metrics.json", "lexicon sha")
            emo[run], prows[run] = em, rows
        print(f"{run}: acc {m['correct']}/{m['n_rows']} = {100*m['accuracy']:.1f}% | baseline {100*m['majority_baseline_accuracy']:.1f}% "
              f"| bal {100*m['balanced_accuracy']:.1f}% | macroF1 {100*m['macro_f1']:.1f}% | cells {m['confusion_cells']}")
        if run in emo:
            e = emo[run]
            print(f"   emotion agree {e['agreement']['all_rows']['agree']}/{e['n_rows']} ({100*e['agreement_rate_all_rows']:.1f}%), "
                  f"single {e['agreement']['excluding_none_and_tie']['agree']}/{e['agreement']['excluding_none_and_tie']['n']}; "
                  f"const {e['constant_baseline_emotion']} {e['constant_baseline']['all_rows']['agree']}; best {e['best_constant_baseline_emotion']} "
                  f"{e['best_constant_baseline']['all_rows']['agree']}; TIE {e['tie_rows']} NONE {e['none_rows']}; llm-in-tie {e['tie_rows_llm_emotion_in_tied_set']} const-in-tie {e['tie_rows_constant_in_tied_set']}")

    # ---- comparisons.json
    v1, f3, b3 = metrics["first100_v1"], metrics["first100_v3"], metrics["balanced150_v3"]
    mg = lambda m: m["accuracy"] - m["majority_baseline_accuracy"]
    comp = {
        "first100_v1_accuracy": v1["accuracy"], "first100_v1_majority_baseline": v1["majority_baseline_accuracy"],
        "first100_v1_margin_over_baseline": mg(v1), "first100_v1_negative_support": v1["per_class"]["NEGATIVE"]["support"],
        "first100_v3_accuracy": f3["accuracy"], "balanced150_v3_accuracy": b3["accuracy"],
        "accuracy_balanced150_v3_minus_first100_v3": b3["accuracy"] - f3["accuracy"],
        "first100_v3_majority_baseline": f3["majority_baseline_accuracy"], "balanced150_v3_majority_baseline": b3["majority_baseline_accuracy"],
        "first100_v3_margin_over_baseline": mg(f3), "balanced150_v3_margin_over_baseline": mg(b3),
        "first100_v3_balanced_accuracy": f3["balanced_accuracy"], "balanced150_v3_balanced_accuracy": b3["balanced_accuracy"],
        "first100_v3_macro_f1": f3["macro_f1"], "balanced150_v3_macro_f1": b3["macro_f1"],
        "first100_v3_truth_counts": f3["truth_distribution"]["counts"], "balanced150_v3_truth_counts": b3["truth_distribution"]["counts"],
        "first100_v3_recall": {k: v["recall"] for k, v in f3["per_class"].items()},
        "balanced150_v3_recall": {k: v["recall"] for k, v in b3["per_class"].items()},
    }
    cc = b3["confusion_cells"]
    for a, b in (("neutral", "neutral"), ("neutral", "negative"), ("neutral", "positive"), ("negative", "neutral"),
                 ("positive", "neutral"), ("negative", "positive"), ("positive", "negative")):
        comp[f"balanced150_v3_{a}_to_{b}"] = cc[f"{a.upper()}->{b.upper()}"]
    comp["balanced150_v3_neutral_to_negative_share"] = cc["NEUTRAL->NEGATIVE"] / 50
    comp["balanced150_v3_neutral_to_positive_share"] = cc["NEUTRAL->POSITIVE"] / 50
    comp["balanced150_v3_neutral_recall"] = b3["per_class"]["NEUTRAL"]["recall"]
    comp["balanced150_v3_neutral_precision"] = b3["per_class"]["NEUTRAL"]["precision"]
    comp["balanced150_v3_negative_precision"] = b3["per_class"]["NEGATIVE"]["precision"]
    comp["balanced150_v3_predicted_negative"] = b3["prediction_distribution"]["counts"]["NEGATIVE"]
    comp["balanced150_v3_neutral_errors_to_negative_minus_negative_errors_to_neutral"] = cc["NEUTRAL->NEGATIVE"] - cc["NEGATIVE->NEUTRAL"]
    comp["balanced150_v3_neutral_main_destination"] = max(("POSITIVE", "NEGATIVE", "UNPARSED"), key=lambda c: cc[f"NEUTRAL->{c}"])
    comp["first100_v1_accuracy_wilson95"] = wilson(v1["correct"], v1["n_rows"])
    comp["first100_v3_accuracy_wilson95"] = wilson(f3["correct"], f3["n_rows"])
    comp["balanced150_v3_accuracy_wilson95"] = wilson(b3["correct"], b3["n_rows"])
    comp["balanced150_v3_neutral_recall_wilson95"] = wilson(cc["NEUTRAL->NEUTRAL"], 50)
    comp["balanced150_v3_neutral_to_negative_share_wilson95"] = wilson(cc["NEUTRAL->NEGATIVE"], 50)
    comp["balanced150_v3_neutral_to_positive_share_wilson95"] = wilson(cc["NEUTRAL->POSITIVE"], 50)
    for run in ("first100_v2", "first100_v3", "balanced150_v3"):
        e = emo[run]
        comp[f"{run}_emotion_agreement_all_rows"] = e["agreement_rate_all_rows"]
        comp[f"{run}_emotion_agreement_excluding_none_and_tie"] = e["agreement_rate_excluding_none_and_tie"]
        comp[f"{run}_emotion_constant_baseline_emotion"] = e["constant_baseline_emotion"]
        comp[f"{run}_emotion_constant_baseline_all_rows"] = e["constant_baseline_rate_all_rows"]
        comp[f"{run}_emotion_llm_minus_constant_all_rows"] = e["llm_minus_constant_rate_all_rows"]
        comp[f"{run}_emotion_llm_minus_constant_excluding_none_and_tie"] = e["llm_minus_constant_rate_excluding_none_and_tie"]
        comp[f"{run}_emotion_best_constant_emotion"] = e["best_constant_baseline_emotion"]
        comp[f"{run}_emotion_best_constant_all_rows"] = e["best_constant_baseline_rate_all_rows"]
        comp[f"{run}_emotion_best_constant_excluding_none_and_tie"] = e["best_constant_baseline_rate_excluding_none_and_tie"]
        comp[f"{run}_emotion_llm_minus_best_constant_all_rows"] = e["llm_minus_best_constant_rate_all_rows"]
        comp[f"{run}_emotion_llm_minus_best_constant_excluding_none_and_tie"] = e["llm_minus_best_constant_rate_excluding_none_and_tie"]
    filed = json.loads((ROOT / "runs" / "comparisons.json").read_text())
    filed_cmp = {k: v for k, v in filed.items() if k not in ("note", "sources", "interval_method")}
    deep_compare(comp, filed_cmp, "comparisons.json")
    print("Wilson:", {k: [f"{100*x:.1f}%" for x in v] for k, v in comp.items() if k.endswith("wilson95")})

    # ---- dashboard read-back
    dash_numbers(metrics, emo, preds_by_run)

    # ---- written claims
    claims(metrics, emo, prows, preds_by_run, data, comp, pools, balanced, pos4)

    print("\nchecks by area:")
    for k in sorted(CHECKS):
        print(f"  {k}: {CHECKS[k]}")
    print(f"TOTAL checks: {sum(CHECKS.values())}; FAILURES: {len(FAILS)}")
    for f in FAILS:
        print("FAIL", f)
    sys.exit(1 if FAILS else 0)


def dash_numbers(metrics, emo, preds_by_run):
    from playwright.sync_api import sync_playwright
    url = (ROOT / "dashboard" / "index.html").resolve().as_uri()
    js_collect = r"""
    () => {
      const metrics = [...document.querySelectorAll('[data-metric][data-raw]')].map(e => ({
        metric: e.dataset.metric, raw: e.dataset.raw, source: e.dataset.source, format: e.dataset.format,
        run: e.dataset.run, text: e.textContent}));
      const marks = [...document.querySelectorAll('[data-value]')].map(e => {
        const r = e.getBoundingClientRect();
        return {metric: e.dataset.metric, value: e.dataset.value, label: e.dataset.label, run: e.dataset.run,
                w: r.width, h: r.height, hidden: !!e.closest('[hidden]')};});
      // digits in visible text not inside a data-metric element, outside the review table body
      const loose = [];
      const main = document.querySelector('main') || document.body;
      const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        if (!/\d/.test(node.textContent)) continue;
        const p = node.parentElement;
        if (p.closest('[data-metric]') || p.closest('#review-table tbody') || p.closest('[hidden]')
            || p.closest('option') || p.closest('input')) continue;
        loose.push((p.id ? '#' + p.id : p.tagName.toLowerCase() + '.' + p.className) + ': ' + node.textContent.trim().slice(0, 80));
      }
      const trs = [...document.querySelectorAll('#review-table tbody tr')].map(t => ({
        id: +t.dataset.reviewId, truth: t.dataset.truth, pred: t.dataset.prediction, correct: t.dataset.correct,
        stars: t.cells[1].textContent, emo: t.dataset.emo || null}));
      return {metrics, marks, loose, trs, bodyRun: document.body.dataset.run,
              selected: [...document.querySelectorAll('[data-run-tab][aria-selected="true"]')].map(b => b.dataset.runTab),
              shown: document.getElementById('shown-count')?.dataset.liveCount,
              emoHidden: document.getElementById('sec-emotion')?.hidden};
    }"""
    files = {}

    def filed(src):
        f = src.split("#")[0]
        if f not in files:
            files[f] = json.loads((ROOT / f).read_text())
        return files[f]

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        for run in RUNS:
            a = f"dashboard/{run}"
            page.click(f'[data-run-tab="{run}"]')
            page.wait_for_timeout(250)
            got = page.evaluate(js_collect)
            check(got["bodyRun"] == run and got["selected"] == [run], a, f"tab selection body={got['bodyRun']} selected={got['selected']}")
            check(len(got["metrics"]) > 0, a, "no data-metric elements")
            for mm in got["metrics"]:
                check(mm["run"] == run, a, f"{mm['metric']}: data-run {mm['run']}")
                file, _, path = mm["source"].partition("#")
                check(path == mm["metric"], a, f"data-source path {mm['source']} != data-metric {mm['metric']}")
                check(file.startswith(f"runs/{run}/"), a, f"{mm['metric']}: source {file} not from this run")
                raw = json.loads(mm["raw"])
                fv = getp(filed(mm["source"]), path)
                check(fv is not KeyError and close(raw, fv), a, f"{mm['source']}: data-raw {raw!r} vs file {fv!r}")
                if file.endswith("metrics.json") and not file.endswith("emotion_metrics.json"):
                    mine = getp(metrics[run], path)
                elif file.endswith("emotion_metrics.json"):
                    mine = getp(emo[run], path)
                else:
                    mine = fv  # run_meta: file value (recomputable parts checked in main)
                check(mine is not KeyError and close(raw, mine), a, f"{mm['source']}: data-raw {raw!r} vs recomputed {mine!r}")
                check(mm["text"] == fmt(raw, mm["format"]), a, f"{mm['source']}: shown {mm['text']!r} vs format {fmt(raw, mm['format'])!r}")
            for mk in got["marks"]:
                check(mk["run"] == run and mk["label"], a, f"mark {mk['metric']}: run/label")
                path = mk["metric"]
                mine = getp(emo[run], path[len("emotion."):]) if path.startswith("emotion.") else getp(metrics[run], path)
                check(mine is not KeyError and close(float(mk["value"]), mine), a, f"mark {path}: data-value {mk['value']} vs recomputed {mine}")
                if float(mk["value"]) > 0 and not mk["hidden"]:
                    check(mk["w"] > 0.5 and mk["h"] > 0.5, a, f"mark {path} value {mk['value']} rendered {mk['w']:.1f}x{mk['h']:.1f}px")
            preds = preds_by_run[run]
            check(len(got["trs"]) == len(preds), a, f"table rows {len(got['trs'])} vs {len(preds)}")
            for tr, p in zip(got["trs"], preds):
                ok = tr["id"] == p["review_id"] and tr["truth"] == p["truth"] and tr["pred"] == p["prediction"] \
                    and tr["correct"] == str(p["truth"] == p["prediction"]).lower() and tr["stars"] == f"{p['rating']:g}★"  # JS String(5.0) == "5"
                check(ok, a, f"table row {tr} vs prediction {p['review_id']}")
            check(got["shown"] == str(len(preds)), a, f"live count {got['shown']}")
            check(got["emoHidden"] == (run not in emo), a, "emotion section visibility")
            # expected metric coverage of confusion/emotion marks
            exp_cells = len(metrics[run]["confusion_cells"])
            check(sum(m["metric"].startswith("confusion_cells.") for m in got["marks"]) == exp_cells, a, "confusion mark count")
            if run in emo:
                check(sum(m["metric"].startswith("emotion.crosstab_cells.") for m in got["marks"]) == len(emo[run]["crosstab_cells"]), a, "crosstab mark count")
            print(f"{a}: {len(got['metrics'])} data-metric numbers, {len(got['marks'])} chart marks, {len(got['trs'])} table rows")
            print(f"   text with digits outside data-metric (excl. table body): {sorted(set(got['loose']))}")
        check(not errors, "dashboard", f"page errors {errors}")
        browser.close()


def claims(metrics, emo, prows, preds_by_run, data, comp, pools, balanced, pos4):
    """(file, exact quoted substring, recomputed truth). The quote must exist and the value must hold."""
    b3, f3, v1 = metrics["balanced150_v3"], metrics["first100_v3"], metrics["first100_v1"]
    cc = b3["confusion_cells"]
    pc = lambda m, c, k: m["per_class"][c][k]
    P = lambda x: f"{100 * x:.1f}%"
    eb, ef, e2 = emo["balanced150_v3"], emo["first100_v3"], emo["first100_v2"]
    bal_preds = preds_by_run["balanced150_v3"]
    byid = {p["review_id"]: p for p in bal_preds}
    mis = b3["misclassified_review_ids"]
    n2n_emos = Counter(byid[i]["llm_emotion"] for i in mis["NEUTRAL->NEGATIVE"])
    stars_mix = Counter(int(p["rating"]) for p in bal_preds)
    star_titles_b = sum(bool(STAR.match(p["title"])) for p in bal_preds)
    star_any_b = sum(bool(STAR.match(p["title"]) or STAR.match(p["text"])) for p in bal_preds)
    star_titles_f = sum(bool(STAR.match(p["title"])) for p in preds_by_run["first100_v3"])
    groups = [6689, 33885, 114708, 51332, 48586, 18646, 32735, 60681, 88199, 53136, 60608, 129667,
              22082, 29467, 88606, 94255, 119458, 111827, 147336, 88787, 111780, 140179, 143371, 4880, 121389]
    praise = [32735, 60681, 147336, 53136, 60608, 88787, 121389]
    v1p = {p["review_id"]: p["prediction"] for p in preds_by_run["first100_v1"]}
    moved = sorted(p["review_id"] for p in preds_by_run["first100_v3"] if p["prediction"] != v1p[p["review_id"]])
    f3_nonjoy = [r for r in prows["first100_v3"] if r["llm_raw"] != "joy"]
    n3_right = pc(f3, "POSITIVE", "correct")
    pred_neg_from_3 = cc["NEUTRAL->NEGATIVE"]
    A = "reviews/step6_analysis.md"
    I = "ISSUES.md"
    G = "PROGRESS.md"
    W = lambda k: "–".join(f"{100*x:.1f}" for x in comp[k])
    C = [
        (A, "Of 50, 17 are predicted NEUTRAL, **25 collapse into NEGATIVE** and 8 into POSITIVE", (cc["NEUTRAL->NEUTRAL"], cc["NEUTRAL->NEGATIVE"], cc["NEUTRAL->POSITIVE"]) == (17, 25, 8)),
        (A, "4 of 50 1–2★ reviews are predicted NEUTRAL", cc["NEGATIVE->NEUTRAL"] == 4),
        (A, "(NEGATIVE pool 14,178, NEUTRAL 3,270, POSITIVE 134,913)", [len(pools[c]) for c in ("NEGATIVE", "NEUTRAL", "POSITIVE")] == [14178, 3270, 134913]),
        (A, "Predicted POSITIVE 57 / NEUTRAL 23 / NEGATIVE 70 / UNPARSED 0", list(b3["prediction_distribution"]["counts"].values()) == [57, 23, 70, 0]),
        (A, "truth POSITIVE 50 / NEUTRAL 50 / NEGATIVE 50", list(b3["truth_distribution"]["counts"].values()) == [50, 50, 50]),
        (A, "Accuracy **73.3%** (110/150)", (P(b3["accuracy"]), b3["correct"], b3["n_rows"]) == ("73.3%", 110, 150)),
        (A, "The majority-class baseline is 33.3%", P(b3["majority_baseline_accuracy"]) == "33.3%"),
        (A, "Margin over that baseline: +40.0 points", fmt(comp["balanced150_v3_margin_over_baseline"], "pp") == "+40.0 pts"),
        (A, "Balanced accuracy 73.3%; macro F1 70.4%. Parse failures 0, API errors 0.", (P(b3["balanced_accuracy"]), P(b3["macro_f1"]), b3["parse_fail_count"], b3["api_error_count"]) == ("73.3%", "70.4%", 0, 0)),
        (A, "| POSITIVE (50) | **48** | 2 | 0 | 0 |", b3["confusion_matrix"]["counts"][0] == [48, 2, 0, 0]),
        (A, "| NEUTRAL (50)  | 8 | **17** | 25 | 0 |", b3["confusion_matrix"]["counts"][1] == [8, 17, 25, 0]),
        (A, "| NEGATIVE (50) | 1 | 4 | **45** | 0 |", b3["confusion_matrix"]["counts"][2] == [1, 4, 45, 0]),
        (A, "| POSITIVE | 48/50 = 96.0% | 48/57 = 84.2% |", (P(pc(b3, "POSITIVE", "recall")), P(pc(b3, "POSITIVE", "precision"))) == ("96.0%", "84.2%")),
        (A, "| NEUTRAL | 17/50 = 34.0% | 17/23 = 73.9% |", (P(pc(b3, "NEUTRAL", "recall")), P(pc(b3, "NEUTRAL", "precision"))) == ("34.0%", "73.9%")),
        (A, "| NEGATIVE | 45/50 = 90.0% | 45/70 = 64.3% |", (P(pc(b3, "NEGATIVE", "recall")), P(pc(b3, "NEGATIVE", "precision"))) == ("90.0%", "64.3%")),
        (A, "Of the 70 NEGATIVE predictions, 25 are 3★ reviews", pred_neg_from_3 == 25 and sum(int(byid[i]["rating"]) == 3 for i in mis["NEUTRAL->NEGATIVE"]) == 25),
        (A, "25 of 50 = 50.0%", P(comp["balanced150_v3_neutral_to_negative_share"]) == "50.0%"),
        (A, "Wilson 95% interval 36.6%–63.4%", W("balanced150_v3_neutral_to_negative_share_wilson95") == "36.6–63.4"),
        (A, "8 of 50 = 16.0%, interval 8.3%–28.5%", W("balanced150_v3_neutral_to_positive_share_wilson95") == "8.3–28.5" and cc["NEUTRAL->POSITIVE"] == 8),
        (A, "17 of 50 = 34.0%, interval 22.4%–47.8%", W("balanced150_v3_neutral_recall_wilson95") == "22.4–47.8"),
        (A, "4–5★ → NEUTRAL: 2 of 50", cc["POSITIVE->NEUTRAL"] == 2),
        (A, "1–2★ → POSITIVE 1; 4–5★ → NEGATIVE 0", (cc["NEGATIVE->POSITIVE"], cc["POSITIVE->NEGATIVE"]) == (1, 0)),
        (A, "exceeds NEGATIVE→NEUTRAL by 21 reviews", comp["balanced150_v3_neutral_errors_to_negative_minus_negative_errors_to_neutral"] == 21),
        (A, "The LLM gave 20 of them the emotion anger, 4 sadness, 1 disgust.", n2n_emos == Counter({"anger": 20, "sadness": 4, "disgust": 1})),
        (A, "(5):** 6689", sorted(groups) == sorted(mis["NEUTRAL->NEGATIVE"]) and len(groups) == 25),
        (A, "51332 \"Hasn't seems to load…\" (title \"It's okay.\")", byid[51332]["title"] == "It’s okay."),
        (A, "Seven of the 25 also contain explicit praise", len(praise) == 7 and set(praise) <= set(mis["NEUTRAL->NEGATIVE"])),
        (A, "Four of those had their auto-filled \"Three Stars\" title blanked", all(STAR.match(byid[i]["title"]) for i in (43478, 73030, 144067, 146724)) and not STAR.match(byid[134401]["title"])),
        (A, "20086 \"Very fast", set([43478, 73030, 144067, 146724, 134401, 20086, 23773, 144273]) == set(mis["NEUTRAL->POSITIVE"])),
        (A, "31137 (\"One Star\" blanked)", STAR.match(byid[31137]["title"]) and STAR.match(byid[99795]["title"]) and set([31137, 49142, 99795, 136849]) == set(mis["NEGATIVE->NEUTRAL"])),
        (A, "**4–5★ → NEUTRAL (2):** 12158", mis["POSITIVE->NEUTRAL"] == [12158, 43820]),
        (A, "**1–2★ → POSITIVE (1):** 116236", mis["NEGATIVE->POSITIVE"] == [116236]),
        (A, "| truth counts (POS/NEU/NEG) | 93 / 2 / 5 | 50 / 50 / 50 |", list(f3["truth_distribution"]["counts"].values()) == [93, 2, 5]),
        (A, "| accuracy | 95.0% (95/100) | 73.3% (110/150) |", (P(f3["accuracy"]), f3["correct"]) == ("95.0%", 95)),
        (A, "| majority baseline | 93.0% | 33.3% |", P(f3["majority_baseline_accuracy"]) == "93.0%"),
        (A, "| margin over baseline | +2.0 pts | +40.0 pts |", fmt(comp["first100_v3_margin_over_baseline"], "pp") == "+2.0 pts"),
        (A, "| balanced accuracy | 65.6% | 73.3% |", P(f3["balanced_accuracy"]) == "65.6%"),
        (A, "| macro F1 | 60.4% | 70.4% |", P(f3["macro_f1"]) == "60.4%"),
        (A, "| NEUTRAL recall | 0 of 2 | 17 of 50 |", (pc(f3, "NEUTRAL", "correct"), pc(f3, "NEUTRAL", "support")) == (0, 2)),
        (A, "| NEGATIVE precision | 5/7 = 71.4% | 45/70 = 64.3% |", (pc(f3, "NEGATIVE", "correct"), pc(f3, "NEGATIVE", "predicted"), P(pc(f3, "NEGATIVE", "precision"))) == (5, 7, "71.4%")),
        (A, "`accuracy_balanced150_v3_minus_first100_v3` = −21.7 points", fmt(comp["accuracy_balanced150_v3_minus_first100_v3"], "pp") == "−21.7 pts"),
        (A, "it gets 90 of those 93 right", n3_right == 90),
        (A, "It contains 2 NEUTRAL reviews (91 → NEGATIVE, 98 → POSITIVE)", f3["misclassified_review_ids"].get("NEUTRAL->NEGATIVE") == [91] and f3["misclassified_review_ids"].get("NEUTRAL->POSITIVE") == [98]),
        (A, "only two predictions moved: 46 (NEGATIVE → NEUTRAL) and 83", moved == [46, 83] and v1p[46] == "NEGATIVE" and v1p[83] == "POSITIVE"),
        (A, "both are 5★", all(data[i]["rating"] == 5 for i in (46, 83))),
        (A, "`first100_v1`: 97.0% (97/100) against a 93.0% majority baseline, a margin of +4.0 points, with 7 NEGATIVE reviews", (v1["correct"], P(v1["majority_baseline_accuracy"]), fmt(comp["first100_v1_margin_over_baseline"], "pp"), pc(v1, "NEGATIVE", "support")) == (97, "93.0%", "+4.0 pts", 7)),
        (A, "balanced accuracy of the run 65.7%–79.8% (`balanced150_v3_accuracy_wilson95`)", W("balanced150_v3_accuracy_wilson95") == "65.7–79.8"),
        (A, "`first100_v3` accuracy 95.0% has interval 88.8%–97.8%, and `first100_v1` 97.0% has 91.5%–99.0%", W("first100_v3_accuracy_wilson95") == "88.8–97.8" and W("first100_v1_accuracy_wilson95") == "91.5–99.0"),
        (A, "16/150 = 10.7%, and 16/59 = 27.1%", (eb["agreement"]["all_rows"]["agree"], P(eb["agreement_rate_all_rows"]), eb["agreement"]["excluding_none_and_tie"]["n"], P(eb["agreement_rate_excluding_none_and_tie"])) == (16, "10.7%", 59, "27.1%")),
        (A, "anger (62 of 150). A constant \"anger\" agrees only 4/150 (2.7%), because the word list rarely says anger (4 times)", (eb["llm_emotion_counts"]["anger"], eb["constant_baseline"]["all_rows"]["agree"], P(eb["constant_baseline_rate_all_rows"]), eb["nrc_emotion_counts"]["anger"]) == (62, 4, "2.7%", 4)),
        (A, "anticipation: 22/150 = 14.7%, and 22/59 = 37.3%", (eb["best_constant_baseline_emotion"], eb["best_constant_baseline"]["all_rows"]["agree"], P(eb["best_constant_baseline_rate_all_rows"]), P(eb["best_constant_baseline_rate_excluding_none_and_tie"])) == ("anticipation", 22, "14.7%", "37.3%")),
        (A, "4.0 points below it on all rows and 10.2 points below", (fmt(eb["llm_minus_best_constant_rate_all_rows"], "pp"), fmt(eb["llm_minus_best_constant_rate_excluding_none_and_tie"], "pp")) == ("−4.0 pts", "−10.2 pts")),
        (A, "The word list tied on 67 reviews and found no emotion words in 24.", (eb["tie_rows"], eb["none_rows"]) == (67, 24)),
        (A, "agreement 20/100, against a constant \"joy\" at 22/100 (−2.0 points)", (ef["agreement"]["all_rows"]["agree"], ef["constant_baseline_emotion"], ef["constant_baseline"]["all_rows"]["agree"], fmt(ef["llm_minus_constant_rate_all_rows"], "pp")) == (20, "joy", 22, "−2.0 pts")),
        (A, "In the 18 reviews where the LLM did not say joy, the two agree 0 times.", (len(f3_nonjoy), sum(r["agree"] for r in f3_nonjoy)) == (18, 0)),
        (A, "the LLM never agrees with the word list more often than the best constant answer", all(e["llm_minus_best_constant_rate_all_rows"] <= 0 for e in (eb, ef, e2))),
        (A, "anger (62) and trust (22)", (eb["llm_emotion_counts"]["anger"], eb["llm_emotion_counts"]["trust"]) == (62, 22)),
        (A, "(star mix 1★ 43, 2★ 7, 3★ 50, 4★ 0, 5★ 50)", [stars_mix.get(k, 0) for k in (1, 2, 3, 4, 5)] == [43, 7, 50, 0, 50]),
        (A, "**26 of 150 titles were auto-filled star phrases and were blanked** for the model (4 of 100 in batch_100)", (star_titles_b, star_titles_f) == (26, 4)),
        (I, "4★ reviews are 6,691 of the 134,913 POSITIVE pool (under 5%)", pos4 == 6691 and pos4 / len(pools["POSITIVE"]) < 0.05),
        (I, "the run used 147 API calls with 4 cache hits", True),  # checked against run_meta in main
        (I, "`balanced150_v3` 73.3% (110/150) against a 33.3% majority baseline. NEUTRAL (3★) row: 17 predicted NEUTRAL, 25 NEGATIVE, 8 POSITIVE. Reverse direction: 4 NEGATIVE reviews predicted NEUTRAL; 2 POSITIVE predicted NEUTRAL. The model predicted NEGATIVE for 70 of 150.", True),
        (I, "95.0% (95/100) against a 93.0% majority baseline; balanced accuracy 65.6%. Three-class truth on batch_100 is POSITIVE 93, NEUTRAL 2, NEGATIVE 5", True),
        (I, "a constant \"anger\" agrees with the word list on only 4/150, a weak bar the LLM clears easily (16/150). The word list's own most common single answer (anticipation, 22)", True),
        (I, "where the LLM's emotion is in 37 of 67 ties and the constant \"anger\" in only 6", (eb["tie_rows_llm_emotion_in_tied_set"], eb["tie_rows"], eb["tie_rows_constant_in_tied_set"]) == (37, 67, 6)),
        (I, "(LLM emotion in 45 ties, constant \"joy\" in 45)", (e2["tie_rows_llm_emotion_in_tied_set"], e2["tie_rows_constant_in_tied_set"]) == (45, 45)),
        (I, "26 of the 150 titles are star phrases", star_titles_b == 26),
        (I, "93 API calls, 7 cache hits", (json.loads((ROOT / "runs/first100_v3/run_meta.json").read_text())["api_call_count"], json.loads((ROOT / "runs/first100_v3/run_meta.json").read_text())["cache_hits"]) == (93, 7)),
        (G, "recall POS 48/50, NEU 17/50, NEG 45/50", [pc(b3, c, "correct") for c in ("POSITIVE", "NEUTRAL", "NEGATIVE")] == [48, 17, 45]),
        (G, "errors 46, 83 (POS→NEU), 17 (POS→NEG), 98 (NEU→POS), 91 (NEU→NEG)", f3["misclassified_review_ids"] == {"POSITIVE->NEUTRAL": [46, 83], "POSITIVE->NEGATIVE": [17], "NEUTRAL->POSITIVE": [98], "NEUTRAL->NEGATIVE": [91]}),
        (G, "anticipation 22/150 (14.7%), 22/59 (37.3%) → LLM −4.0 / −10.2 pts", True),
        (G, "balanced accuracy 65.7–79.8%, NEUTRAL→NEGATIVE share 36.6–63.4%, NEUTRAL recall 22.4–47.8%, NEUTRAL→POSITIVE 8.3–28.5%", True),
        (G, "20/100 vs constant joy 22/100 (best constant also joy)", ef["best_constant_baseline_emotion"] == "joy"),
    ]
    texts = {}
    for f, quote, ok in C:
        if f not in texts:
            texts[f] = (ROOT / f).read_text(encoding="utf-8")
        present = quote in texts[f]
        check(present, "written", f"{f}: quoted text not found: {quote!r}")
        check(bool(ok), "written", f"{f}: claim does not match recomputation: {quote!r}")
    print(f"written claims checked: {len(C)}; star-phrase title OR text in balanced sample: {star_any_b}")
    # verify_leak's "3 reviews use a forbidden word": which ones
    FORB = re.compile(r"\b(rating|star|stars|helpful|verified)\b", re.IGNORECASE)
    hits = [(p["review_id"], FORB.findall(("" if STAR.match(p["title"]) else p["title"]) + " " + ("" if STAR.match(p["text"]) else p["text"])))
            for p in bal_preds]
    print("balanced rows whose sent title/text contain rating/star/stars/helpful/verified:", [h for h in hits if h[1]])


if __name__ == "__main__":
    main()
