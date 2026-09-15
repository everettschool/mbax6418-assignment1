"""Step 7 Numbers Auditor: independent recomputation of every saved and displayed number.

Does NOT import any project module. Re-implements from the documented rules:
  1. whole-file star distribution (from data/Gift_Cards.jsonl.gz)
  2. per-run sample membership, row content vs the data file, truth labels, predictions re-parsed
     from raw_responses, and every field of metrics.json
  3. NRC word-list emotion per row and every field of emotion_metrics.json
  4. every field of runs/comparisons.json
  5. dashboard/index.html in headless Chromium: every [data-raw] number against MY recomputed value
     and display rule; every chart mark's value, >= 2px size, bar length vs value, and a visible label
     showing its true value; embedded DATA vs files on disk; untagged digit text outside the table.
  6. written numbers in the Step 7 entries of ISSUES.md / PROGRESS.md.

Usage: .venv/bin/python reviews/step7_numbers_auditor/audit.py
"""
import gzip
import hashlib
import html as htmllib
import json
import math
import random
import re
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
RUNS = ["balanced150_v3", "first100_v3", "first100_v2", "first100_v1"]
EMO = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]
PROBLEMS, N_CHECKS = [], [0]


def chk(ok, msg):
    N_CHECKS[0] += 1
    if not ok:
        PROBLEMS.append(msg)
        print("  MISMATCH", msg)


def same(a, b, tol=1e-12):
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=0, abs_tol=tol)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k], tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y, tol) for x, y in zip(a, b))
    return a == b


def deep_compare(mine, saved, where):
    """Every leaf of the saved file must equal my value; report missing/extra keys."""
    if isinstance(saved, dict) and isinstance(mine, dict):
        for k in saved:
            if k not in mine:
                chk(False, f"{where}.{k}: field in file but not recomputed")
                continue
            deep_compare(mine[k], saved[k], f"{where}.{k}")
        for k in mine:
            chk(k in saved, f"{where}.{k}: recomputed field missing from file")
    else:
        chk(same(mine, saved), f"{where}: file {saved!r} != recomputed {mine!r}")


# ---------------- 1. whole file ----------------
def read_file():
    rows = []
    with gzip.open(ROOT / "data" / "Gift_Cards.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def audit_distribution(rows):
    n = len(rows)
    cnt = Counter(int(r["rating"]) for r in rows)
    chk(all(float(r["rating"]).is_integer() for r in rows), "non-integral rating in file")
    fail = Counter(int(r["rating"]) for r in rows if not (r.get("text") or "").strip())
    mine = {
        "source_file": "Gift_Cards.jsonl.gz", "row_count": n,
        "rating_counts": {str(s): cnt[s] for s in sorted(cnt)},
        "rating_pct": {str(s): round(100 * cnt[s] / n, 4) for s in sorted(cnt)},
        "inclusion_rule": "text is non-empty after stripping whitespace",
        "rows_failing_inclusion": sum(fail.values()),
        "rows_failing_inclusion_by_rating": {str(s): fail[s] for s in sorted(fail)},
        "rating_share": {str(s): cnt[s] / n for s in sorted(cnt)},
    }
    saved = json.loads((ROOT / "runs" / "rating_distribution.json").read_text())
    deep_compare(mine, saved, "rating_distribution.json")
    print(f"[file] rows {n}; counts {dict(sorted(cnt.items()))}; failing inclusion {sum(fail.values())}")
    return mine


# ---------------- 2. per-run metrics ----------------
def truth_of(rating, scheme):
    r = int(rating)
    if scheme == "binary":
        return "POSITIVE" if r >= 4 else "NEGATIVE"
    return "POSITIVE" if r >= 4 else ("NEUTRAL" if r == 3 else "NEGATIVE")


def reparse(raws, labels, emotion):
    """Last reply; last non-fence line matching the strict format."""
    if not raws or not isinstance(raws[-1], str):
        return None
    pat = (rf"^LABEL=({'|'.join(labels)});EMOTION=({'|'.join(EMO)})$" if emotion
           else rf"^LABEL=({'|'.join(labels)})$")
    for line in reversed(raws[-1].strip().splitlines()):
        line = line.strip()
        if re.fullmatch(r"`{3,}[a-zA-Z]*", line):
            continue
        m = re.match(pat, line.strip("`").strip())
        if m:
            return m.group(1), (m.group(2) if emotion else None)
    return None


def audit_sample(run, preds, meta, filerows):
    ids = [p["review_id"] for p in preds]
    chk(len(set(ids)) == len(ids), f"{run}: duplicate review_ids")
    included = [i for i, r in enumerate(filerows) if (r.get("text") or "").strip()]
    if meta["selection"] == "batch_100":
        chk(ids == included[:100], f"{run}: ids are not the first 100 included rows")
    else:
        pools = {c: [] for c in ("NEGATIVE", "NEUTRAL", "POSITIVE")}
        for i in included:
            pools[truth_of(filerows[i]["rating"], "three")].append(i)
        want = {c: sorted(random.Random(42).sample(sorted(v), 50)) for c, v in pools.items()}
        sample = json.loads((ROOT / "runs" / run / "sample_ids.json").read_text())
        chk(sample["by_class"] == want, f"{run}: sample_ids.json by_class != independent redraw")
        chk(sorted(ids) == sorted(sum(want.values(), [])), f"{run}: prediction ids != independent redraw")
        chk(sample["review_ids"] == sorted(sum(want.values(), [])), f"{run}: sample_ids.json review_ids != redraw")
        chk(sample["selection_info"]["pool_size_by_class"] == {c: len(v) for c, v in pools.items()},
            f"{run}: pool sizes differ")
        chk(meta["selection_info"]["pool_size_by_class"] == {c: len(v) for c, v in pools.items()},
            f"{run}: run_meta pool sizes differ")
    for p in preds:
        fr = filerows[p["review_id"]]
        chk(fr["title"] == p["title"] and fr["text"] == p["text"] and float(fr["rating"]) == float(p["rating"]),
            f"{run} row {p['review_id']}: title/text/rating differ from line {p['review_id']} of the data file")


def audit_metrics(run, filerows):
    d = ROOT / "runs" / run
    meta = json.loads((d / "run_meta.json").read_text())
    preds = [json.loads(l) for l in open(d / "predictions.jsonl", encoding="utf-8")]
    scheme, labels = meta["label_scheme"], meta["labels"]
    emotion = bool(meta.get("emotion_requested"))
    audit_sample(run, preds, meta, filerows)
    for p in preds:
        t = truth_of(p["rating"], scheme)
        chk(p["truth"] == t, f"{run} row {p['review_id']}: truth {p['truth']} != {t}")
        parsed = reparse(p["raw_responses"], labels, emotion)
        if p["parse_status"] == "OK":
            chk(parsed is not None and parsed[0] == p["prediction"],
                f"{run} row {p['review_id']}: prediction {p['prediction']} != re-parsed {parsed}")
            if emotion:
                chk(parsed is not None and parsed[1] == p.get("llm_emotion"), f"{run} row {p['review_id']}: llm_emotion mismatch")
        else:
            chk(p["prediction"] == "UNPARSED", f"{run} row {p['review_id']}: non-OK status but prediction {p['prediction']}")
    cols = labels + ["UNPARSED"]
    n = len(preds)
    cm = {t: {c: 0 for c in cols} for t in labels}
    for p in preds:
        cm[truth_of(p["rating"], scheme)][p["prediction"] if p["prediction"] in labels else "UNPARSED"] += 1
    sup = {t: sum(cm[t].values()) for t in labels}
    prd = {c: sum(cm[t][c] for t in labels) for c in cols}
    correct = sum(cm[t][t] for t in labels)
    pc = {}
    for t in labels:
        tp = cm[t][t]
        prec = tp / prd[t] if prd[t] else None
        rec = tp / sup[t] if sup[t] else None
        f1 = 2 * prec * rec / (prec + rec) if prec and rec else 0.0
        pc[t] = {"support": sup[t], "predicted": prd[t], "correct": tp, "wrong": sup[t] - tp,
                 "precision": prec or 0.0, "precision_undefined_never_predicted": prec is None, "recall": rec, "f1": f1}
    top = max(sup.values())
    majority = [t for t in labels if sup[t] == top][0]
    stars = Counter(int(p["rating"]) for p in preds)
    acc = correct / n
    mine = {
        "run": run, "label_scheme": scheme, "labels": labels,
        "confusion_matrix_orientation": "rows = truth (from rating), columns = predicted",
        "n_rows": n, "correct": correct, "incorrect": n - correct, "accuracy": acc,
        "sample_rating_counts": {str(s): stars.get(s, 0) for s in range(1, 6)},
        "sample_rating_share": {str(s): stars.get(s, 0) / n for s in range(1, 6)},
        "truth_distribution": {"counts": sup, "share": {t: sup[t] / n for t in labels}},
        "prediction_distribution": {"counts": prd, "share": {c: prd[c] / n for c in cols}},
        "majority_class": majority, "majority_baseline_accuracy": top / n,
        "accuracy_minus_majority_baseline": acc - top / n,
        "balanced_accuracy": sum(pc[t]["recall"] for t in labels) / len(labels),
        "majority_baseline_balanced_accuracy": 1 / len(labels),
        "macro_f1": sum(pc[t]["f1"] for t in labels) / len(labels),
        "per_class": pc,
        "confusion_matrix": {"rows": labels, "columns": cols, "counts": [[cm[t][c] for c in cols] for t in labels]},
        "confusion_cells": {f"{t}->{c}": cm[t][c] for t in labels for c in cols},
        "confusion_row_share": {f"{t}->{c}": cm[t][c] / sup[t] for t in labels for c in cols},
        "misclassified_review_ids": {f"{t}->{c}": [p["review_id"] for p in preds if p["truth"] == t and p["prediction"] == c]
                                     for t in labels for c in cols if t != c and cm[t][c]},
        "parse_fail_count": sum(p["parse_status"] == "FAIL" for p in preds),
        "api_error_count": sum(p["parse_status"] == "API_ERROR" for p in preds),
        "unparsed_count": prd["UNPARSED"], "unparsed_share": prd["UNPARSED"] / n,
        "rows_needing_retry": sum(len(p["raw_responses"]) > 1 for p in preds),
    }
    deep_compare(mine, json.loads((d / "metrics.json").read_text()), f"{run}/metrics.json")
    chk(meta["n_rows"] == n, f"{run}: run_meta n_rows {meta['n_rows']} != {n}")
    for k in ("parse_fail_count", "api_error_count", "rows_needing_retry"):
        chk(meta[k] == mine[k], f"{run}: run_meta {k} {meta[k]} != {mine[k]}")
    chk(meta["dataset_row_count"] == len(filerows), f"{run}: run_meta dataset_row_count")
    print(f"[{run}] accuracy {correct}/{n}; truth {sup}; predicted {prd}")
    return mine, preds, meta


# ---------------- 3. emotions ----------------
def load_lexicon():
    raw = (ROOT / "data" / "nrc" / "NRC-Emotion-Lexicon-Wordlevel.txt").read_bytes()
    lexmeta = json.loads((ROOT / "runs" / "nrc_lexicon_meta.json").read_text())
    chk(hashlib.sha256(raw).hexdigest() == lexmeta["lexicon_sha256"], "lexicon sha256 != nrc_lexicon_meta.json")
    lex, words = {}, set()
    for line in raw.decode("utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) == 3 and parts[2] in ("0", "1"):
            words.add(parts[0])
            if parts[2] == "1" and parts[1] in EMO:
                lex.setdefault(parts[0], set()).add(parts[1])
    chk(len(words) == lexmeta["word_count"], f"lexicon word_count {len(words)} != meta {lexmeta['word_count']}")
    chk(len(lex) == lexmeta["words_with_any_of_8_emotions"], f"lexicon 8-emotion words {len(lex)} != meta")
    return lex, lexmeta


STAR = re.compile(r"^\s*(one|two|three|four|five)\s+stars?\s*$", re.IGNORECASE)
NEG = {"not", "no", "never", "nothing", "none", "nor", "without", "t"}


def nrc_row(title, text, lex):
    s = ("" if STAR.match(title) else title) + " " + ("" if STAR.match(text) else text)
    s = htmllib.unescape(re.sub(r"<br\s*/?>", " ", s, flags=re.IGNORECASE)).lower()
    toks = re.findall(r"[a-z]+", s)
    sc = dict.fromkeys(EMO, 0)
    hits, negs = [], []
    for i, t in enumerate(toks):
        w = t if t in lex else next((t[:-len(x)] for x in ("ing", "ed", "es", "s") if t.endswith(x) and t[:-len(x)] in lex), None)
        if w is None:
            continue
        for e in lex[w]:
            sc[e] += 1
        hits.append([t, w, sorted(lex[w])])
        before = [b for b in toks[max(0, i - 3):i] if b in NEG]
        if before:
            negs.append([before[-1], t])
    top = max(sc.values())
    tied = [e for e in EMO if sc[e] == top] if top else []
    label = "NONE" if not top else ("TIE" if len(tied) > 1 else tied[0])
    return {"nrc_emotion": label, "nrc_tied": tied if label == "TIE" else [], "nrc_scores": sc, "nrc_hits": hits,
            "nrc_token_count": len(toks), "nrc_emotion_tiebreak": tied[0] if tied else "NONE", "nrc_negated_hits": negs}


def audit_emotions(run, preds, lex, lexmeta):
    d = ROOT / "runs" / run
    if not (d / "emotion_metrics.json").exists():
        chk(all(p.get("llm_emotion") is None for p in preds), f"{run}: has LLM emotions but no emotion_metrics.json")
        return None
    rows = []
    for p in preds:
        r = nrc_row(p["title"], p["text"], lex)
        for k, v in r.items():
            chk(p.get(k) == v, f"{run} row {p['review_id']}: {k} saved {p.get(k)!r} != recomputed {v!r}")
        r.update(review_id=p["review_id"], title=p["title"], text=p["text"], llm=p["llm_emotion"])
        r["agree"] = r["llm"] is not None and r["llm"] == r["nrc_emotion"]
        chk(p["emotion_agree"] == r["agree"], f"{run} row {p['review_id']}: emotion_agree")
        rows.append(r)
    n = len(rows)
    lc = Counter(r["llm"] or "UNPARSED" for r in rows)
    nc = Counter(r["nrc_emotion"] for r in rows)
    tc = Counter(r["nrc_emotion_tiebreak"] for r in rows)
    rate = lambda a, b: a / b if b else None

    def grp(sub, pred):
        a = sum(pred(r) for r in sub)
        return {"n": len(sub), "agree": a, "rate": rate(a, len(sub))}
    excl_none = [r for r in rows if r["nrc_emotion"] != "NONE"]
    single = [r for r in rows if r["nrc_emotion"] not in ("NONE", "TIE")]
    ties = [r for r in rows if r["nrc_emotion"] == "TIE"]
    argmax = lambda c: sorted(EMO, key=lambda e: (-c.get(e, 0), EMO.index(e)))[0]
    const, best, best_tb = argmax(lc), argmax(nc), argmax(tc)
    A = lambda r: r["agree"]
    agr = {"all_rows": grp(rows, A), "excluding_none": grp(excl_none, A), "excluding_none_and_tie": grp(single, A)}
    cb = {k: grp(s, lambda r: r["nrc_emotion"] == const) for k, s in (("all_rows", rows), ("excluding_none", excl_none), ("excluding_none_and_tie", single))}
    bb = {k: {"n": len(s), "agree": nc.get(best, 0), "rate": rate(nc.get(best, 0), len(s))} for k, s in (("all_rows", rows), ("excluding_none", excl_none), ("excluding_none_and_tie", single))}
    seen, uniq = set(), []
    for r in rows:
        if (r["title"], r["text"]) not in seen:
            seen.add((r["title"], r["text"]))
            uniq.append(r)
    lcols, ncols = EMO + ["UNPARSED"], EMO + ["TIE", "NONE"]
    xt = Counter((r["llm"] or "UNPARSED", r["nrc_emotion"]) for r in rows)
    tb_all = sum(r["llm"] is not None and r["llm"] == r["nrc_emotion_tiebreak"] for r in rows)
    tb_en = sum(r["llm"] == r["nrc_emotion_tiebreak"] for r in excl_none)
    nm = [r for r in rows if r["llm"] != const]
    mine = {
        "run": run,
        "lexicon": {k: lexmeta.get(k) for k in ("source", "download_url", "lexicon_sha256", "word_count", "words_with_any_of_8_emotions", "citation")},
        "n_rows": n, "crosstab_orientation": "rows = LLM emotion, columns = NRC word-list emotion",
        "llm_emotion_counts": {c: lc.get(c, 0) for c in lcols}, "llm_emotion_share": {c: lc.get(c, 0) / n for c in lcols},
        "nrc_emotion_counts": {c: nc.get(c, 0) for c in ncols}, "nrc_emotion_share": {c: nc.get(c, 0) / n for c in ncols},
        "agreement": agr, "agreement_rate_all_rows": agr["all_rows"]["rate"],
        "agreement_rate_excluding_none": agr["excluding_none"]["rate"],
        "agreement_rate_excluding_none_and_tie": agr["excluding_none_and_tie"]["rate"],
        "tie_rows": len(ties), "tie_rows_llm_emotion_in_tied_set": sum(r["llm"] in r["nrc_tied"] for r in ties),
        "tie_rows_llm_emotion_in_tied_set_rate": rate(sum(r["llm"] in r["nrc_tied"] for r in ties), len(ties)),
        "none_rows": nc.get("NONE", 0), "constant_baseline_emotion": const, "constant_baseline": cb,
        "constant_baseline_rate_all_rows": cb["all_rows"]["rate"], "constant_baseline_rate_excluding_none": cb["excluding_none"]["rate"],
        "constant_baseline_rate_excluding_none_and_tie": cb["excluding_none_and_tie"]["rate"],
        "llm_minus_constant_rate_all_rows": agr["all_rows"]["rate"] - cb["all_rows"]["rate"],
        "llm_minus_constant_rate_excluding_none_and_tie": (agr["excluding_none_and_tie"]["rate"] or 0) - (cb["excluding_none_and_tie"]["rate"] or 0),
        "tie_rows_constant_in_tied_set": sum(const in r["nrc_tied"] for r in ties),
        "best_constant_baseline_emotion": best, "best_constant_baseline": bb,
        "best_constant_baseline_rate_all_rows": bb["all_rows"]["rate"],
        "best_constant_baseline_rate_excluding_none_and_tie": bb["excluding_none_and_tie"]["rate"],
        "llm_minus_best_constant_rate_all_rows": agr["all_rows"]["rate"] - bb["all_rows"]["rate"],
        "llm_minus_best_constant_rate_excluding_none_and_tie": (agr["excluding_none_and_tie"]["rate"] or 0) - (bb["excluding_none_and_tie"]["rate"] or 0),
        "agreement_llm_not_constant": {"all_rows": grp(nm, A), "excluding_none_and_tie": grp([r for r in nm if r["nrc_emotion"] not in ("NONE", "TIE")], A)},
        "agreement_tiebreak": {"all_rows": {"n": n, "agree": tb_all, "rate": rate(tb_all, n)},
                               "excluding_none": {"n": len(excl_none), "agree": tb_en, "rate": rate(tb_en, len(excl_none))}},
        "tiebreak_label_counts": {c: tc.get(c, 0) for c in EMO + ["NONE"]},
        "tie_rows_broken_to": {e: sum(r["nrc_emotion_tiebreak"] == e for r in ties) for e in EMO},
        "tiebreak_constant_baseline": {k: {"emotion": e, "agree": tc.get(e, 0), "rate": tc.get(e, 0) / n} for k, e in (("llm_most_common", const), ("best_constant", best_tb))},
        "unique_title_text": {"n": len(uniq), "agree": sum(r["agree"] for r in uniq), "tie": sum(r["nrc_emotion"] == "TIE" for r in uniq), "none": sum(r["nrc_emotion"] == "NONE" for r in uniq)},
        "negation": {"rows_with_negated_hits": sum(bool(r["nrc_negated_hits"]) for r in rows), "negated_hits_total": sum(len(r["nrc_negated_hits"]) for r in rows)},
        "crosstab": {"rows": lcols, "columns": ncols, "counts": [[xt[(a, b)] for b in ncols] for a in lcols]},
        "crosstab_cells": {f"{a}->{b}": xt[(a, b)] for a in lcols for b in ncols},
        "divergent_review_ids": [r["review_id"] for r in single if not r["agree"]],
    }
    saved = json.loads((d / "emotion_metrics.json").read_text())
    # prose-only fields (not numbers): method, notes, rules
    prose = {"method", "constant_baseline_note", "best_constant_baseline_note", "tiebreak_rule"}
    saved_cmp = {k: v for k, v in saved.items() if k not in prose}
    saved_cmp["negation"] = {k: v for k, v in saved["negation"].items() if k != "rule"}
    deep_compare(mine, saved_cmp, f"{run}/emotion_metrics.json")
    print(f"[{run}] emotions: agree {agr['all_rows']['agree']}/{n}; TIE {len(ties)}; NONE {nc.get('NONE', 0)}; constant {const}; best {best}")
    return mine


# ---------------- 4. comparisons ----------------
def wilson(k, n, z=1.959963984540054):
    p = k / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [(c - h) / (1 + z * z / n), (c + h) / (1 + z * z / n)]


def audit_comparisons(M, E, filerows):
    v1, f3, b3 = M["first100_v1"], M["first100_v3"], M["balanced150_v3"]
    cc, rs = b3["confusion_cells"], b3["confusion_row_share"]
    mine = {
        "first100_v1_accuracy": v1["accuracy"], "first100_v1_majority_baseline": v1["majority_baseline_accuracy"],
        "first100_v1_margin_over_baseline": v1["accuracy"] - v1["majority_baseline_accuracy"],
        "first100_v1_negative_support": v1["per_class"]["NEGATIVE"]["support"],
        "first100_v3_accuracy": f3["accuracy"], "balanced150_v3_accuracy": b3["accuracy"],
        "accuracy_balanced150_v3_minus_first100_v3": b3["accuracy"] - f3["accuracy"],
        "first100_v3_majority_baseline": f3["majority_baseline_accuracy"], "balanced150_v3_majority_baseline": b3["majority_baseline_accuracy"],
        "first100_v3_margin_over_baseline": f3["accuracy"] - f3["majority_baseline_accuracy"],
        "balanced150_v3_margin_over_baseline": b3["accuracy"] - b3["majority_baseline_accuracy"],
        "first100_v3_balanced_accuracy": f3["balanced_accuracy"], "balanced150_v3_balanced_accuracy": b3["balanced_accuracy"],
        "first100_v3_macro_f1": f3["macro_f1"], "balanced150_v3_macro_f1": b3["macro_f1"],
        "first100_v3_truth_counts": f3["truth_distribution"]["counts"], "balanced150_v3_truth_counts": b3["truth_distribution"]["counts"],
        "first100_v3_recall": {k: v["recall"] for k, v in f3["per_class"].items()},
        "balanced150_v3_recall": {k: v["recall"] for k, v in b3["per_class"].items()},
        "balanced150_v3_neutral_to_neutral": cc["NEUTRAL->NEUTRAL"], "balanced150_v3_neutral_to_negative": cc["NEUTRAL->NEGATIVE"],
        "balanced150_v3_neutral_to_positive": cc["NEUTRAL->POSITIVE"], "balanced150_v3_negative_to_neutral": cc["NEGATIVE->NEUTRAL"],
        "balanced150_v3_positive_to_neutral": cc["POSITIVE->NEUTRAL"], "balanced150_v3_negative_to_positive": cc["NEGATIVE->POSITIVE"],
        "balanced150_v3_positive_to_negative": cc["POSITIVE->NEGATIVE"],
        "balanced150_v3_neutral_to_negative_share": rs["NEUTRAL->NEGATIVE"], "balanced150_v3_neutral_to_positive_share": rs["NEUTRAL->POSITIVE"],
        "balanced150_v3_neutral_recall": b3["per_class"]["NEUTRAL"]["recall"], "balanced150_v3_neutral_precision": b3["per_class"]["NEUTRAL"]["precision"],
        "balanced150_v3_negative_precision": b3["per_class"]["NEGATIVE"]["precision"],
        "balanced150_v3_predicted_negative": b3["prediction_distribution"]["counts"]["NEGATIVE"],
        "balanced150_v3_neutral_errors_to_negative_minus_negative_errors_to_neutral": cc["NEUTRAL->NEGATIVE"] - cc["NEGATIVE->NEUTRAL"],
        "balanced150_v3_neutral_main_destination": max(("POSITIVE", "NEGATIVE", "UNPARSED"), key=lambda c: cc[f"NEUTRAL->{c}"]),
        "interval_method": "Wilson score 95% interval, [low, high] as fractions",
        "first100_v1_accuracy_wilson95": wilson(v1["correct"], v1["n_rows"]),
        "first100_v3_accuracy_wilson95": wilson(f3["correct"], f3["n_rows"]),
        "balanced150_v3_accuracy_wilson95": wilson(b3["correct"], b3["n_rows"]),
        "balanced150_v3_neutral_recall_wilson95": wilson(b3["per_class"]["NEUTRAL"]["correct"], 50),
        "balanced150_v3_neutral_to_negative_share_wilson95": wilson(cc["NEUTRAL->NEGATIVE"], 50),
        "balanced150_v3_neutral_to_positive_share_wilson95": wilson(cc["NEUTRAL->POSITIVE"], 50),
    }
    pools = Counter(truth_of(r["rating"], "three") for r in filerows if (r.get("text") or "").strip())
    tot = sum(pools.values())
    w = {c: pools[c] / tot for c in ("NEGATIVE", "NEUTRAL", "POSITIVE")}
    L = b3["labels"]
    j = {(t, p): w[t] * rs[f"{t}->{p}"] for t in L for p in L}
    pm = {p: sum(j[(t, p)] for t in L) for p in L}
    mine.update({
        "population_pool_sizes": {c: pools[c] for c in ("NEGATIVE", "NEUTRAL", "POSITIVE")}, "population_weights": w,
        "balanced150_v3_population_weighted_accuracy": sum(j[(t, t)] for t in L),
        "balanced150_v3_population_weighted_precision": {p: j[(p, p)] / pm[p] for p in L},
        "balanced150_v3_population_weighted_share_of_negative_predictions_from_neutral": j[("NEUTRAL", "NEGATIVE")] / pm["NEGATIVE"],
        "balanced150_v3_population_weighted_share_of_neutral_predictions_from_positive": j[("POSITIVE", "NEUTRAL")] / pm["NEUTRAL"],
        "balanced150_v3_share_of_negative_predictions_from_neutral": cc["NEUTRAL->NEGATIVE"] / b3["prediction_distribution"]["counts"]["NEGATIVE"],
        "balanced_accuracy_balanced150_v3_minus_first100_v3": b3["balanced_accuracy"] - f3["balanced_accuracy"],
        "first100_v3_accuracy_expected_from_balanced150_v3_recalls": sum(f3["per_class"][k]["support"] * b3["per_class"][k]["recall"] for k in L) / f3["n_rows"],
        "first100_v3_neutral_support": f3["per_class"]["NEUTRAL"]["support"],
        "first100_v3_balanced_accuracy_if_one_more_neutral_right": (f3["per_class"]["POSITIVE"]["recall"] + f3["per_class"]["NEGATIVE"]["recall"]
                                                                     + (f3["per_class"]["NEUTRAL"]["correct"] + 1) / f3["per_class"]["NEUTRAL"]["support"]) / 3,
    })
    for run in ("first100_v2", "first100_v3", "balanced150_v3"):
        e = E[run]
        mine.update({
            f"{run}_emotion_agreement_all_rows": e["agreement_rate_all_rows"],
            f"{run}_emotion_agreement_excluding_none_and_tie": e["agreement_rate_excluding_none_and_tie"],
            f"{run}_emotion_constant_baseline_emotion": e["constant_baseline_emotion"],
            f"{run}_emotion_constant_baseline_all_rows": e["constant_baseline_rate_all_rows"],
            f"{run}_emotion_llm_minus_constant_all_rows": e["llm_minus_constant_rate_all_rows"],
            f"{run}_emotion_llm_minus_constant_excluding_none_and_tie": e["llm_minus_constant_rate_excluding_none_and_tie"],
            f"{run}_emotion_best_constant_emotion": e["best_constant_baseline_emotion"],
            f"{run}_emotion_best_constant_all_rows": e["best_constant_baseline_rate_all_rows"],
            f"{run}_emotion_best_constant_excluding_none_and_tie": e["best_constant_baseline_rate_excluding_none_and_tie"],
            f"{run}_emotion_llm_minus_best_constant_all_rows": e["llm_minus_best_constant_rate_all_rows"],
            f"{run}_emotion_llm_minus_best_constant_excluding_none_and_tie": e["llm_minus_best_constant_rate_excluding_none_and_tie"],
        })
    saved = json.loads((ROOT / "runs" / "comparisons.json").read_text())
    saved_cmp = {k: v for k, v in saved.items() if k not in ("note", "sources", "population_weighting_note")}
    deep_compare(mine, saved_cmp, "comparisons.json")
    return mine


# ---------------- 5. dashboard ----------------
def fixed1(x):
    return str(Decimal(x).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def fmt(v, f):
    if f == "pct":
        return fixed1(v * 100) + "%"
    if f == "count":
        return f"{int(Decimal(v).quantize(Decimal('1'), rounding=ROUND_HALF_UP)):,}"
    if f == "pp":
        return ("−" if v < 0 else "+") + fixed1(abs(v * 100)) + " pts"
    if f == "text":
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
    raise ValueError(f)


def get(obj, path):
    for k in path.split("."):
        obj = obj[k]
    return obj


def audit_dashboard(DIST, M, E, C, META):
    mine_files = {"runs/rating_distribution.json": DIST, "runs/comparisons.json": C}
    for r in RUNS:
        mine_files[f"runs/{r}/metrics.json"] = M[r]
        mine_files[f"runs/{r}/run_meta.json"] = META[r]
        if E.get(r):
            mine_files[f"runs/{r}/emotion_metrics.json"] = E[r]
    page_path = ROOT / "dashboard" / "index.html"
    htm = page_path.read_text(encoding="utf-8")
    emb = json.loads(re.search(r'<script id="dashboard-data" type="application/json">(.*?)</script>', htm, re.S).group(1).replace("<\\/", "</"))
    chk(emb["rating_distribution"] == json.loads((ROOT / "runs/rating_distribution.json").read_text()), "embedded rating_distribution != file (stale build)")
    chk(emb["comparisons"] == json.loads((ROOT / "runs/comparisons.json").read_text()), "embedded comparisons != file (stale build)")
    chk([x["run"] for x in emb["runs"]] == RUNS, f"embedded runs {[x['run'] for x in emb['runs']]} != {RUNS}")
    for x in emb["runs"]:
        chk(x["metrics"] == json.loads((ROOT / "runs" / x["run"] / "metrics.json").read_text()), f"{x['run']}: embedded metrics stale")
        if "emotion_metrics" in x:
            chk(x["emotion_metrics"] == json.loads((ROOT / "runs" / x["run"] / "emotion_metrics.json").read_text()), f"{x['run']}: embedded emotion_metrics stale")
        preds = [json.loads(l) for l in open(ROOT / "runs" / x["run"] / "predictions.jsonl", encoding="utf-8")]
        chk([rw["review_id"] for rw in x["rows"]] == [p["review_id"] for p in preds], f"{x['run']}: embedded rows differ")
        chk(all(rw[k] == p[k] for rw, p in zip(x["rows"], preds) for k in rw), f"{x['run']}: embedded row fields differ")

    summary = {}
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page(viewport={"width": 1440, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.goto(page_path.resolve().as_uri())
        pg.wait_for_load_state("load")
        for vw, run in [(v, r) for v in (1440, 400) for r in RUNS]:
            pg.set_viewport_size({"width": vw, "height": 900})
            pg.click(f'[data-run-tab="{run}"]')
            chk(pg.get_attribute("body", "data-run") == run, f"tab {run} not selected")
            nums = pg.eval_on_selector_all("[data-metric]:not([data-value])", """els => els.map(e => ({
                metric: e.dataset.metric, raw: e.dataset.raw, source: e.dataset.source, format: e.dataset.format,
                run: e.dataset.run, text: e.textContent, visible: e.getClientRects().length > 0 }))""")
            fields = set()
            for it in nums:
                w = f"[{run} @{vw}px] number {it['source']}"
                if it["raw"] is None or it["source"] is None:
                    chk(False, f"{w}: missing data-raw or data-source")
                    continue
                f, _, path = it["source"].partition("#")
                chk(path == it["metric"], f"{w}: data-metric {it['metric']} != source field")
                chk(f in mine_files, f"{w}: source file is not one of the audited files")
                if f not in mine_files:
                    continue
                if f.endswith("run_meta.json") or f.endswith("comparisons.json") or f.endswith("rating_distribution.json"):
                    pass
                chk(f in (f"runs/{run}/metrics.json", f"runs/{run}/run_meta.json", f"runs/{run}/emotion_metrics.json",
                          "runs/rating_distribution.json", "runs/comparisons.json"), f"{w}: source belongs to another run")
                try:
                    val = get(mine_files[f], path) if not f.endswith("run_meta.json") else get(META[run], path)
                except (KeyError, TypeError):
                    chk(False, f"{w}: field not in recomputed data")
                    continue
                chk(same(json.loads(it["raw"]), val), f"{w}: data-raw {it['raw']} != recomputed {val!r}")
                chk(it["text"] == fmt(val, it["format"]), f"{w}: shows '{it['text']}', rule gives '{fmt(val, it['format'])}'")
                fields.add(it["source"])
            marks = pg.evaluate("""() => [...document.querySelectorAll('[data-value]')].map(e => {
                const r = e.getBoundingClientRect();
                const track = e.parentElement; const tr = track.getBoundingClientRect();
                const cs = getComputedStyle(e);
                // visible label: a rendered [data-raw] descendant of the mark or of its nearest row container
                const row = e.closest('.hbar, .gbar, .cbar, .cell') || e;
                const labels = [...row.querySelectorAll('[data-raw]')].filter(s => s.getClientRects().length > 0
                    && getComputedStyle(s).visibility !== 'hidden' && s.getBoundingClientRect().width > 0)
                    .map(s => ({metric: s.dataset.metric, raw: s.dataset.raw, text: s.textContent, source: s.dataset.source}));
                return {run: e.dataset.run, metric: e.dataset.metric, value: e.dataset.value, label: e.dataset.label,
                        w: r.width, h: r.height, trackW: tr.width, cls: e.className, visible: cs.visibility !== 'hidden' && cs.display !== 'none',
                        gap: parseFloat(getComputedStyle(track).columnGap) || 0,
                        siblings: [...track.children].map(c => c.dataset.value), labels};
            })""")
            n_marks = 0
            for mk in marks:
                n_marks += 1
                w = f"[{run} @{vw}px] mark {mk['metric']} ({mk['label']})"
                chk(all(mk[k] not in (None, "") for k in ("run", "metric", "value", "label")), f"{w}: missing attribute")
                if mk["run"] == "__file__":
                    src, path = DIST, mk["metric"]
                elif mk["metric"].startswith("emotion."):
                    src, path = E[mk["run"]], mk["metric"][len("emotion."):]
                else:
                    src, path = M.get(mk["run"]), mk["metric"]
                chk(mk["run"] in (run, "__file__"), f"{w}: data-run is not the selected run")
                try:
                    true = get(src, path)
                except (KeyError, TypeError):
                    chk(False, f"{w}: no recomputed field")
                    continue
                v = float(mk["value"])
                chk(v == float(true), f"{w}: data-value {mk['value']} != recomputed {true}")
                if v > 0:
                    chk(mk["visible"] and mk["w"] >= 2 and mk["h"] >= 2, f"{w}: value {v} renders {mk['w']:.2f}x{mk['h']:.2f}px")
                    want_text = fmt(true, "count")
                    ok = any(l["text"] == want_text and same(json.loads(l["raw"]), true)
                             and l["metric"] == path for l in mk["labels"])
                    chk(ok, f"{w}: no visible label showing {want_text} next to it (labels: {[(l['metric'], l['text']) for l in mk['labels']]})")
                    # length encodes the value (no collapse, no overflow)
                    if "bar" in mk["cls"].split():
                        if path.startswith("rating_counts."):
                            exp = DIST["rating_share"][path.split(".")[1]]
                        elif path.startswith("sample_rating_counts."):
                            exp = M[run]["sample_rating_share"][path.split(".")[1]]
                        elif path.startswith(("truth_distribution", "prediction_distribution")):
                            m = M[run]
                            mx = max(1, *[max(m["truth_distribution"]["counts"].get(c, 0), m["prediction_distribution"]["counts"].get(c, 0)) for c in m["confusion_matrix"]["columns"]])
                            exp = true / mx
                        else:
                            e = E[run]
                            mx = max(1, *e["llm_emotion_counts"].values(), *e["nrc_emotion_counts"].values())
                            exp = true / mx
                        want_px = max(exp * mk["trackW"], 2)
                        chk(abs(mk["w"] - want_px) <= 1.0, f"{w}: bar {mk['w']:.2f}px, value implies {want_px:.2f}px of {mk['trackW']:.1f}px track")
                    elif "seg" in mk["cls"].split():
                        vals = [float(s) for s in mk["siblings"]]
                        free = mk["trackW"] - mk["gap"] * (len(vals) - 1)
                        want_px = max(free * v / sum(vals), 2)
                        chk(abs(mk["w"] - want_px) <= 1.5, f"{w}: segment {mk['w']:.2f}px, value implies {want_px:.2f}px")
            # untagged digits outside the review table / tabs / tooltip
            untagged = pg.evaluate("""() => { const out = [], wk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                for (let n = wk.nextNode(); n; n = wk.nextNode()) { const p = n.parentElement;
                  if (!p || p.closest('#review-table, script, style, #tip, [data-raw], #run-tabs, select, option')) continue;
                  if (p.getClientRects().length === 0) continue;
                  if (/\\d/.test(n.textContent)) out.push(n.textContent.trim()); }
                return [...new Set(out)]; }""")
            summary[(run, vw)] = {"numbers": len(nums), "distinct_sources": len(fields), "marks": n_marks, "untagged_digit_text": untagged}
            print(f"[{run} @{vw}px] dashboard: {len(nums)} tagged numbers ({len(fields)} distinct fields), {n_marks} marks; untagged digit text: {untagged}")
        chk(not errs, f"console/page errors: {errs}")
        br.close()
    return summary


# ---------------- 6. written numbers ----------------
def audit_written(DIST, M):
    issues = (ROOT / "ISSUES.md").read_text(encoding="utf-8")
    progress = (ROOT / "PROGRESS.md").read_text(encoding="utf-8")
    s7 = issues.split("## Step 7")[1].split("- **[Step 6]")[0]
    p7 = progress.split("## Step 7 status")[1].split("## Step 6 status")[0]
    claims = [
        ("ISSUES: whole file 152,410 rows", "152,410" in s7, fmt(DIST["row_count"], "count") == "152,410"),
        ("ISSUES: 5★ 84.1%", "5★ 84.1%" in s7, fmt(DIST["rating_share"]["5"], "pct") == "84.1%"),
        ("ISSUES: 2★ 1.2%", "2★ 1.2%" in s7, fmt(DIST["rating_share"]["2"], "pct") == "1.2%"),
        ("ISSUES: 2★ smallest whole-file class (\"small value such as 2★ at 1.2%\")", "2★ at 1.2%" in s7, min(DIST["rating_counts"], key=DIST["rating_counts"].get) == "2"),
        ("ISSUES: batch_100 91% 5★", "91% 5★" in s7, all(M[r]["sample_rating_counts"]["5"] == 91 and M[r]["n_rows"] == 100 for r in ("first100_v1", "first100_v2", "first100_v3"))),
        ("ISSUES: balanced sample drops 4★ entirely", "drops 4★ entirely" in s7, M["balanced150_v3"]["sample_rating_counts"]["4"] == 0),
        ("ISSUES: NEUTRAL 50 stars vs 23 model", "NEUTRAL is 50 by the stars vs 23 by the model" in s7,
         M["balanced150_v3"]["truth_distribution"]["counts"]["NEUTRAL"] == 50 and M["balanced150_v3"]["prediction_distribution"]["counts"]["NEUTRAL"] == 23),
        ("ISSUES: NEGATIVE 50 vs 70", "NEGATIVE 50 vs 70" in s7,
         M["balanced150_v3"]["truth_distribution"]["counts"]["NEGATIVE"] == 50 and M["balanced150_v3"]["prediction_distribution"]["counts"]["NEGATIVE"] == 70),
        ("ISSUES: \"· 2 wrong\" example exists (balanced POSITIVE wrong 2)", "· 2 wrong" in s7, M["balanced150_v3"]["per_class"]["POSITIVE"]["wrong"] == 2),
    ]
    vtxt = (ROOT / "reviews" / "step7_verify_dashboard.txt").read_text()
    last = re.search(r"([\d,]+) checks, (\d+) failures", vtxt)
    claims.append(("ISSUES/PROGRESS: 4,404 checks, 0 failures (matches reviews/step7_verify_dashboard.txt)",
                   "4,404 checks, 0 failures" in s7 and "4,404 checks" in p7, last and last.group(1) == "4404" and last.group(2) == "0"))
    for name, present, correct in claims:
        chk(present, f"written claim not found verbatim: {name}")
        chk(bool(correct), f"written claim wrong: {name}")
        print(f"[written] {name}: present={present} correct={bool(correct)}")


def main():
    filerows = read_file()
    DIST = audit_distribution(filerows)
    lex, lexmeta = load_lexicon()
    M, E, META = {}, {}, {}
    for run in RUNS:
        M[run], preds, META[run] = audit_metrics(run, filerows)
        E[run] = audit_emotions(run, preds, lex, lexmeta)
    C = audit_comparisons(M, E, filerows)
    summary = audit_dashboard(DIST, M, E, C, META)
    audit_written(DIST, M)
    print(f"\n{N_CHECKS[0]} checks, {len(PROBLEMS)} mismatches")
    for p in PROBLEMS:
        print("  -", p)


if __name__ == "__main__":
    main()
