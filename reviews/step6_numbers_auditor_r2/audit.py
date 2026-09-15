"""Step 6 round-2 Numbers Auditor: independent recomputation (imports nothing from src/).

Recomputes every metric from the data file + predictions.jsonl, deep-compares metrics.json,
emotion_metrics.json, comparisons.json, rating_distribution.json, nrc_lexicon_meta.json,
reads the built dashboard DOM via Playwright, and checks quoted written claims.

Run: .venv/bin/python reviews/step6_numbers_auditor_r2/audit.py
"""
import gzip
import hashlib
import html
import json
import math
import random
import re
import statistics
import subprocess
import sys
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"
RUN_NAMES = ["balanced150_v3", "first100_v3", "first100_v2", "first100_v1"]
EMO = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]
Z = 1.959963984540054

FAILS = []
CHECKS = [0]


def check(ok, msg):
    CHECKS[0] += 1
    if not ok:
        FAILS.append(msg)
        print("  FAIL:", msg)
    return ok


def close(a, b, tol=1e-12):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b or a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
    return a == b


def deep_compare(mine, theirs, where, skip=()):
    """Every leaf of theirs must equal mine; keys on either side only are failures."""
    if isinstance(theirs, dict):
        if not check(isinstance(mine, dict), f"{where}: expected dict"):
            return
        for k in theirs:
            if k in skip:
                continue
            if not check(k in mine, f"{where}.{k}: present in file, not recomputed"):
                continue
            deep_compare(mine[k], theirs[k], f"{where}.{k}", skip)
        for k in mine:
            if k not in theirs and k not in skip:
                check(False, f"{where}.{k}: recomputed but missing in file")
    elif isinstance(theirs, list):
        if not check(isinstance(mine, list) and len(mine) == len(theirs), f"{where}: list length {len(mine) if isinstance(mine, list) else mine} vs {len(theirs)}"):
            return
        for i, (a, b) in enumerate(zip(mine, theirs)):
            deep_compare(a, b, f"{where}[{i}]", skip)
    else:
        check(close(mine, theirs), f"{where}: recomputed {mine!r} vs file {theirs!r}")


def wilson(k, n):
    p = k / n
    centre = p + Z * Z / (2 * n)
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    d = 1 + Z * Z / n
    return [(centre - half) / d, (centre + half) / d]


# ------------------------------------------------------------------ data file
print("== data file")
rows_all = []
with gzip.open(ROOT / "data" / "Gift_Cards.jsonl.gz", "rt", encoding="utf-8") as f:
    for line in f:
        rows_all.append(json.loads(line))
N_FILE = len(rows_all)
sha = hashlib.sha256((ROOT / "data" / "Gift_Cards.jsonl.gz").read_bytes()).hexdigest()


def included(r):
    return bool((r.get("text") or "").strip())


def three(rating):
    return "POSITIVE" if rating >= 4 else ("NEUTRAL" if rating == 3 else "NEGATIVE")


def binary(rating):
    return "POSITIVE" if rating >= 4 else "NEGATIVE"


inc_ids = [i for i, r in enumerate(rows_all) if included(r)]
excluded = N_FILE - len(inc_ids)
pools = {"NEGATIVE": [], "NEUTRAL": [], "POSITIVE": []}
for i in inc_ids:
    pools[three(rows_all[i]["rating"])].append(i)
pool_sizes = {c: len(v) for c, v in pools.items()}
print("rows", N_FILE, "excluded", excluded, "pools", pool_sizes, "sha ok", sha == json.load(open(RUNS / "balanced150_v3/run_meta.json"))["dataset_sha256"])

rd = json.load(open(RUNS / "rating_distribution.json"))
rc = Counter(str(int(r["rating"])) for r in rows_all)
exc_by = Counter(str(int(r["rating"])) for r in rows_all if not included(r))
deep_compare({"source_file": "Gift_Cards.jsonl.gz", "row_count": N_FILE,
              "rating_counts": {s: rc[s] for s in "12345"},
              "rating_pct": {s: round(100 * rc[s] / N_FILE, 4) for s in "12345"},
              "inclusion_rule": rd["inclusion_rule"], "rows_failing_inclusion": excluded,
              "rows_failing_inclusion_by_rating": {s: exc_by[s] for s in "12345"}}, rd, "rating_distribution.json")

batch100 = inc_ids[:100]
STAR = re.compile(r"^\s*(one|two|three|four|five)\s+stars?\s*$", re.IGNORECASE)
sorted_pools = {c: sorted(v) for c, v in pools.items()}
balanced = {c: sorted(random.Random(42).sample(sorted_pools[c], 50)) for c in ["NEGATIVE", "NEUTRAL", "POSITIVE"]}
sid = json.load(open(RUNS / "balanced150_v3/sample_ids.json"))
for c in balanced:
    check(sorted(sid["by_class"][c]) == balanced[c], f"sample_ids {c} != independent redraw")
check(sid["selection_info"]["pool_size_by_class"] == pool_sizes, "sample_ids pool sizes")
check(sid["selection_info"]["rows_skipped_by_inclusion_rule"] == excluded, "sample_ids skipped")
bal_ids = sorted(sum(balanced.values(), []))
print("balanced redraw == saved:", all(sorted(sid["by_class"][c]) == balanced[c] for c in balanced),
      "| overlap with batch_100:", sorted(set(bal_ids) & set(batch100)), "| batch_100 = 0..99:", batch100 == list(range(100)))

four_in_pos = sum(1 for i in pools["POSITIVE"] if rows_all[i]["rating"] == 4)
title_star_share = {c: (sum(bool(STAR.match(rows_all[i]["title"])) for i in v), len(v)) for c, v in pools.items()}
print("4-star rows in POSITIVE pool:", four_in_pos, f"({100*four_in_pos/pool_sizes['POSITIVE']:.2f}%)")
print("star-phrase TITLE share by pool:", {c: f"{a}/{b}={100*a/b:.1f}%" for c, (a, b) in title_star_share.items()})


def star_title(i):
    return bool(STAR.match(rows_all[i]["title"]))


def star_either(i):
    return bool(STAR.match(rows_all[i]["title"]) or STAR.match(rows_all[i]["text"]))


# 1,000-seed composition
zero4 = 0
neu_titles, whole_titles, whole_either = [], [], []
for s in range(1000):
    draw = {c: random.Random(s).sample(sorted_pools[c], 50) for c in ["NEGATIVE", "NEUTRAL", "POSITIVE"]}
    zero4 += all(rows_all[i]["rating"] != 4 for i in draw["POSITIVE"])
    neu_titles.append(sum(star_title(i) for i in draw["NEUTRAL"]))
    allids = sum(draw.values(), [])
    whole_titles.append(sum(star_title(i) for i in allids))
    whole_either.append(sum(star_either(i) for i in allids))
wt = sorted(whole_titles)
seed42_neu = sum(star_title(i) for i in balanced["NEUTRAL"])
seed42_whole = sum(star_title(i) for i in bal_ids)
seed42_either = sum(star_either(i) for i in bal_ids)
print(f"seeds 0-999: zero 4-star POSITIVE draws {zero4}; NEUTRAL star titles seed42={seed42_neu} mean={statistics.mean(neu_titles):.3f} "
      f">=10: {sum(x >= 10 for x in neu_titles)}; whole-draw star titles seed42={seed42_whole} (title-or-text {seed42_either}) "
      f"median={statistics.median(whole_titles)} p5/p95 nearest-rank={wt[49]}/{wt[949]} "
      f"quantiles(inclusive)={statistics.quantiles(whole_titles, n=20, method='inclusive')[0]}/{statistics.quantiles(whole_titles, n=20, method='inclusive')[-1]}")
SEEDS = {"zero4": zero4, "neu_mean": statistics.mean(neu_titles), "neu_ge10": sum(x >= 10 for x in neu_titles),
         "median": statistics.median(whole_titles), "p5": wt[49], "p95": wt[949]}

# ------------------------------------------------------------------ lexicon
raw_lex = (ROOT / "data/nrc/NRC-Emotion-Lexicon-Wordlevel.txt").read_bytes()
lexmeta = json.load(open(RUNS / "nrc_lexicon_meta.json"))
words_all, lex = set(), {}
cols = set()
for line in raw_lex.decode("utf-8").splitlines():
    p = line.strip().split("\t")
    if len(p) != 3:
        continue
    w, col, flag = p
    words_all.add(w)
    cols.add(col)
    if flag == "1" and col in EMO:
        lex.setdefault(w, set()).add(col)
check(hashlib.sha256(raw_lex).hexdigest() == lexmeta["lexicon_sha256"], "lexicon sha")
check(len(words_all) == lexmeta["word_count"], f"lexicon word_count {len(words_all)}")
check(len(lex) == lexmeta["words_with_any_of_8_emotions"], f"lexicon words with emotions {len(lex)}")
check(sorted(cols) == lexmeta["columns_found"], "lexicon columns")
print("lexicon words", len(words_all), "with 8-emotion tags", len(lex))

NEG = {"not", "no", "never", "nothing", "none", "nor", "without", "t"}


def nrc(title, text):
    t = "" if STAR.match(title) else title
    x = "" if STAR.match(text) else text
    s = html.unescape((t + " " + x).replace("<br />", " "))
    toks = re.findall(r"[a-z]+", s.lower())
    scores = {e: 0 for e in EMO}
    hits, negated = [], []
    for i, tok in enumerate(toks):
        ent = tok if tok in lex else None
        if ent is None:
            for suf in ("ing", "ed", "es", "s"):
                if tok.endswith(suf) and tok[: -len(suf)] in lex:
                    ent = tok[: -len(suf)]
                    break
        if ent is None:
            continue
        es = sorted(lex[ent])
        for e in es:
            scores[e] += 1
        hits.append([tok, ent, es])
        prev = [w for w in toks[max(0, i - 3):i] if w in NEG]
        if prev:
            negated.append([prev[-1], tok])
    top = max(scores.values())
    tied = [e for e in EMO if scores[e] == top] if top else []
    label = "NONE" if top == 0 else ("TIE" if len(tied) > 1 else tied[0])
    return {"nrc_emotion": label, "nrc_tied": tied if label == "TIE" else [], "nrc_scores": scores, "nrc_hits": hits,
            "nrc_token_count": len(toks), "nrc_emotion_tiebreak": tied[0] if label == "TIE" else label,
            "nrc_negated_hits": negated}


# ------------------------------------------------------------------ per run
META, MY_M, MY_E, PREDS = {}, {}, {}, {}
for run in RUN_NAMES:
    print(f"== {run}")
    meta = json.load(open(RUNS / run / "run_meta.json"))
    META[run] = meta
    preds = [json.loads(l) for l in open(RUNS / run / "predictions.jsonl", encoding="utf-8")]
    PREDS[run] = preds
    scheme = meta["label_scheme"]
    labels = ["POSITIVE", "NEUTRAL", "NEGATIVE"] if scheme == "three" else ["POSITIVE", "NEGATIVE"]
    check(meta["labels"] == labels, f"{run} labels")
    truthf = three if scheme == "three" else binary
    emotion = meta["emotion_requested"]
    ids = [p["review_id"] for p in preds]
    expected_ids = bal_ids if meta["selection"] == "balanced_150" else batch100
    check(sorted(ids) == sorted(expected_ids) and len(set(ids)) == len(ids), f"{run} ids != selection")
    lab_re = "|".join(labels)
    pat = re.compile(rf"^LABEL=({lab_re});EMOTION=({'|'.join(EMO)})$" if emotion else rf"^LABEL=({lab_re})$")
    for p in preds:
        src = rows_all[p["review_id"]]
        check(p["title"] == src["title"] and p["text"] == src["text"] and p["rating"] == src["rating"], f"{run} {p['review_id']} row != data file")
        check(p["truth"] == truthf(src["rating"]), f"{run} {p['review_id']} truth")
        last = p["raw_responses"][-1] if p["raw_responses"] else None
        got = None
        if isinstance(last, str):
            for line in reversed(last.strip().splitlines()):
                line = line.strip()
                if re.match(r"^`{3,}[a-zA-Z]*$", line):
                    continue
                m = pat.match(line.strip("`").strip())
                if m:
                    got = m
                    break
        check(p["prediction"] == (got.group(1) if got else "UNPARSED"), f"{run} {p['review_id']} prediction vs raw")
        check((p["parse_status"] == "OK") == bool(got), f"{run} {p['review_id']} parse_status")
        if emotion:
            check(p["llm_emotion"] == (got.group(2) if got else None), f"{run} {p['review_id']} llm_emotion vs raw")
    n = len(preds)
    cols_ = labels + ["UNPARSED"]
    cm = {t: {c: 0 for c in cols_} for t in labels}
    for p in preds:
        cm[p["truth"]][p["prediction"]] += 1
    tc = {t: sum(cm[t].values()) for t in labels}
    pc = {c: sum(cm[t][c] for t in labels) for c in cols_}
    correct = sum(cm[t][t] for t in labels)
    per = {}
    for t in labels:
        tp = cm[t][t]
        prec = tp / pc[t] if pc[t] else None
        rec = tp / tc[t]
        f1 = 2 * prec * rec / (prec + rec) if prec and rec else 0.0
        per[t] = {"support": tc[t], "predicted": pc[t], "correct": tp, "wrong": tc[t] - tp,
                  "precision": prec if prec is not None else 0.0, "precision_undefined_never_predicted": prec is None,
                  "recall": rec, "f1": f1}
    maj = max(labels, key=lambda t: (tc[t], -labels.index(t)))
    stars = Counter(int(p["rating"]) for p in preds)
    mine = {
        "run": run, "label_scheme": scheme, "labels": labels,
        "confusion_matrix_orientation": "rows = truth (from rating), columns = predicted",
        "n_rows": n, "correct": correct, "incorrect": n - correct, "accuracy": correct / n,
        "sample_rating_counts": {str(s): stars.get(s, 0) for s in range(1, 6)},
        "sample_rating_share": {str(s): stars.get(s, 0) / n for s in range(1, 6)},
        "truth_distribution": {"counts": tc, "share": {t: tc[t] / n for t in labels}},
        "prediction_distribution": {"counts": pc, "share": {c: pc[c] / n for c in cols_}},
        "majority_class": maj, "majority_baseline_accuracy": tc[maj] / n,
        "accuracy_minus_majority_baseline": correct / n - tc[maj] / n,
        "balanced_accuracy": sum(per[t]["recall"] for t in labels) / len(labels),
        "majority_baseline_balanced_accuracy": 1 / len(labels),
        "macro_f1": sum(per[t]["f1"] for t in labels) / len(labels),
        "per_class": per,
        "confusion_matrix": {"rows": labels, "columns": cols_, "counts": [[cm[t][c] for c in cols_] for t in labels]},
        "confusion_cells": {f"{t}->{c}": cm[t][c] for t in labels for c in cols_},
        "confusion_row_share": {f"{t}->{c}": cm[t][c] / tc[t] for t in labels for c in cols_},
        "misclassified_review_ids": {f"{t}->{c}": [p["review_id"] for p in preds if p["truth"] == t and p["prediction"] == c]
                                     for t in labels for c in cols_ if t != c and cm[t][c]},
        "parse_fail_count": sum(p["parse_status"] == "FAIL" for p in preds),
        "api_error_count": sum(p["parse_status"] == "API_ERROR" for p in preds),
        "unparsed_count": pc["UNPARSED"], "unparsed_share": pc["UNPARSED"] / n,
        "rows_needing_retry": sum(len(p["raw_responses"]) > 1 for p in preds),
    }
    MY_M[run] = mine
    deep_compare(mine, json.load(open(RUNS / run / "metrics.json")), f"{run}/metrics.json")
    for k in ("n_rows", "parse_fail_count", "api_error_count", "rows_needing_retry"):
        check(meta[k] == mine[k], f"{run} run_meta {k}")
    check(meta["cache_hits"] == sum(bool(p["from_cache"]) for p in preds), f"{run} run_meta cache_hits")
    print(f"acc {correct}/{n} = {100*correct/n:.1f}% | baseline {100*tc[maj]/n:.1f}% | bal {100*mine['balanced_accuracy']:.1f}% "
          f"| macroF1 {100*mine['macro_f1']:.1f}% | truth {tc} | pred {pc} | stars {dict(sorted(stars.items()))} | cache {meta['cache_hits']} calls {meta['api_call_count']}")
    print("  cells", {k: v for k, v in mine["confusion_cells"].items() if v}, "| misclassified", mine["misclassified_review_ids"])

    if not emotion:
        check(not (RUNS / run / "emotion_metrics.json").exists(), f"{run} unexpected emotion_metrics.json")
        continue
    # ---- NRC per row
    for p in preds:
        r = nrc(p["title"], p["text"])
        r["emotion_agree"] = p["llm_emotion"] is not None and p["llm_emotion"] == r["nrc_emotion"]
        for k, v in r.items():
            check(p.get(k) == v, f"{run} {p['review_id']} {k}: recomputed {v!r} vs file {p.get(k)!r}")
        p["_n"] = r
    R = [dict(llm=p["llm_emotion"], **p["_n"], title=p["title"], text=p["text"], id=p["review_id"]) for p in preds]
    llm_cols, nrc_cols = EMO + ["UNPARSED"], EMO + ["TIE", "NONE"]
    lc = Counter(r["llm"] or "UNPARSED" for r in R)
    nc = Counter(r["nrc_emotion"] for r in R)

    def grp(rows):
        a = sum(r["emotion_agree"] for r in rows)
        return {"n": len(rows), "agree": a, "rate": a / len(rows) if rows else None}

    single = [r for r in R if r["nrc_emotion"] not in ("TIE", "NONE")]
    notnone = [r for r in R if r["nrc_emotion"] != "NONE"]
    ties = [r for r in R if r["nrc_emotion"] == "TIE"]
    const = max(EMO, key=lambda e: (lc.get(e, 0), -EMO.index(e)))
    best = max(EMO, key=lambda e: (nc.get(e, 0), -EMO.index(e)))

    def cgrp(rows, e):
        a = sum(r["nrc_emotion"] == e for r in rows)
        return {"n": len(rows), "agree": a, "rate": a / len(rows) if rows else None}

    tbc = Counter(r["nrc_emotion_tiebreak"] for r in R)
    best_tb = max(EMO, key=lambda e: (tbc.get(e, 0), -EMO.index(e)))
    seen, uniq = set(), []
    for r in R:
        if (r["title"], r["text"]) not in seen:
            seen.add((r["title"], r["text"]))
            uniq.append(r)
    tb_all = sum(r["llm"] is not None and r["llm"] == r["nrc_emotion_tiebreak"] for r in R)
    tb_nn = sum(r["llm"] == r["nrc_emotion_tiebreak"] for r in notnone)
    xt = {a: {b: 0 for b in nrc_cols} for a in llm_cols}
    for r in R:
        xt[r["llm"] or "UNPARSED"][r["nrc_emotion"]] += 1
    n = len(R)
    em = {
        "run": run,
        "lexicon": {k: lexmeta.get(k) for k in ("source", "download_url", "lexicon_sha256", "word_count", "words_with_any_of_8_emotions", "citation")},
        "n_rows": n,
        "llm_emotion_counts": {c: lc.get(c, 0) for c in llm_cols}, "llm_emotion_share": {c: lc.get(c, 0) / n for c in llm_cols},
        "nrc_emotion_counts": {c: nc.get(c, 0) for c in nrc_cols}, "nrc_emotion_share": {c: nc.get(c, 0) / n for c in nrc_cols},
        "agreement": {"all_rows": grp(R), "excluding_none": grp(notnone), "excluding_none_and_tie": grp(single)},
        "agreement_rate_all_rows": grp(R)["rate"], "agreement_rate_excluding_none": grp(notnone)["rate"],
        "agreement_rate_excluding_none_and_tie": grp(single)["rate"],
        "tie_rows": len(ties), "tie_rows_llm_emotion_in_tied_set": sum(r["llm"] in r["nrc_tied"] for r in ties),
        "tie_rows_llm_emotion_in_tied_set_rate": sum(r["llm"] in r["nrc_tied"] for r in ties) / len(ties),
        "none_rows": nc.get("NONE", 0),
        "constant_baseline_emotion": const,
        "constant_baseline": {"all_rows": cgrp(R, const), "excluding_none": cgrp(notnone, const), "excluding_none_and_tie": cgrp(single, const)},
        "constant_baseline_rate_all_rows": cgrp(R, const)["rate"], "constant_baseline_rate_excluding_none": cgrp(notnone, const)["rate"],
        "constant_baseline_rate_excluding_none_and_tie": cgrp(single, const)["rate"],
        "llm_minus_constant_rate_all_rows": grp(R)["rate"] - cgrp(R, const)["rate"],
        "llm_minus_constant_rate_excluding_none_and_tie": grp(single)["rate"] - cgrp(single, const)["rate"],
        "tie_rows_constant_in_tied_set": sum(const in r["nrc_tied"] for r in ties),
        "best_constant_baseline_emotion": best,
        "best_constant_baseline": {"all_rows": cgrp(R, best), "excluding_none": cgrp(notnone, best), "excluding_none_and_tie": cgrp(single, best)},
        "best_constant_baseline_rate_all_rows": cgrp(R, best)["rate"],
        "best_constant_baseline_rate_excluding_none_and_tie": cgrp(single, best)["rate"],
        "llm_minus_best_constant_rate_all_rows": grp(R)["rate"] - cgrp(R, best)["rate"],
        "llm_minus_best_constant_rate_excluding_none_and_tie": grp(single)["rate"] - cgrp(single, best)["rate"],
        "agreement_llm_not_constant": {"all_rows": grp([r for r in R if r["llm"] != const]),
                                       "excluding_none_and_tie": grp([r for r in single if r["llm"] != const])},
        "agreement_tiebreak": {"all_rows": {"n": n, "agree": tb_all, "rate": tb_all / n},
                               "excluding_none": {"n": len(notnone), "agree": tb_nn, "rate": tb_nn / len(notnone)}},
        "tiebreak_label_counts": {c: tbc.get(c, 0) for c in EMO + ["NONE"]},
        "tie_rows_broken_to": {e: sum(r["nrc_emotion_tiebreak"] == e for r in ties) for e in EMO},
        "tiebreak_constant_baseline": {
            "llm_most_common": {"emotion": const, "agree": tbc.get(const, 0), "rate": tbc.get(const, 0) / n},
            "best_constant": {"emotion": best_tb, "agree": tbc.get(best_tb, 0), "rate": tbc.get(best_tb, 0) / n}},
        "unique_title_text": {"n": len(uniq), "agree": sum(r["emotion_agree"] for r in uniq),
                              "tie": sum(r["nrc_emotion"] == "TIE" for r in uniq), "none": sum(r["nrc_emotion"] == "NONE" for r in uniq)},
        "negation": {"rows_with_negated_hits": sum(bool(r["nrc_negated_hits"]) for r in R),
                     "negated_hits_total": sum(len(r["nrc_negated_hits"]) for r in R)},
        "crosstab": {"rows": llm_cols, "columns": nrc_cols, "counts": [[xt[a][b] for b in nrc_cols] for a in llm_cols]},
        "crosstab_cells": {f"{a}->{b}": xt[a][b] for a in llm_cols for b in nrc_cols},
        "divergent_review_ids": [r["id"] for r in single if not r["emotion_agree"]],
    }
    MY_E[run] = em
    TEXT_ONLY = {"method", "crosstab_orientation", "constant_baseline_note", "best_constant_baseline_note", "tiebreak_rule", "rule"}
    deep_compare(em, json.load(open(RUNS / run / "emotion_metrics.json")), f"{run}/emotion_metrics.json", skip=TEXT_ONLY)
    gift_lemma = [r["id"] for r in R if r["nrc_emotion"] == "anticipation" and any(h[1] == "gift" for h in r["nrc_hits"])]
    print(f"  emotion agree {grp(R)['agree']}/{n}, single {grp(single)['agree']}/{len(single)}; const {const} {cgrp(R, const)['agree']} "
          f"(single {cgrp(single, const)['agree']}); best {best} {cgrp(R, best)['agree']} (single {cgrp(single, best)['agree']}); "
          f"TIE {len(ties)} NONE {nc.get('NONE', 0)}; llm-in-tie {em['tie_rows_llm_emotion_in_tied_set']} const-in-tie {em['tie_rows_constant_in_tied_set']}; "
          f"llm!=const {em['agreement_llm_not_constant']['all_rows']}; anticipation with 'gift' lemma hit {len(gift_lemma)}/{nc.get('anticipation', 0)}")
    by_truth = {t: dict(Counter(p["llm_emotion"] for p in preds if p["truth"] == t)) for t in labels}
    print("  LLM emotion by truth:", by_truth)
    if run == "balanced150_v3":
        nn = mine["misclassified_review_ids"]["NEUTRAL->NEGATIVE"]
        print("  NEUTRAL->NEGATIVE LLM emotions:", dict(Counter(p["llm_emotion"] for p in preds if p["review_id"] in nn)))

# ------------------------------------------------------------------ comparisons.json
print("== comparisons.json")
v1, f3, b3 = MY_M["first100_v1"], MY_M["first100_v3"], MY_M["balanced150_v3"]
C = {
    "note": None, "sources": None,
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
}
cc = b3["confusion_cells"]
for a, b in [("neutral", "NEUTRAL->NEUTRAL"), ("negative", "NEUTRAL->NEGATIVE"), ("positive", "NEUTRAL->POSITIVE")]:
    C[f"balanced150_v3_neutral_to_{a}"] = cc[b]
C["balanced150_v3_negative_to_neutral"] = cc["NEGATIVE->NEUTRAL"]
C["balanced150_v3_positive_to_neutral"] = cc["POSITIVE->NEUTRAL"]
C["balanced150_v3_negative_to_positive"] = cc["NEGATIVE->POSITIVE"]
C["balanced150_v3_positive_to_negative"] = cc["POSITIVE->NEGATIVE"]
C["balanced150_v3_neutral_to_negative_share"] = cc["NEUTRAL->NEGATIVE"] / 50
C["balanced150_v3_neutral_to_positive_share"] = cc["NEUTRAL->POSITIVE"] / 50
C["balanced150_v3_neutral_recall"] = b3["per_class"]["NEUTRAL"]["recall"]
C["balanced150_v3_neutral_precision"] = b3["per_class"]["NEUTRAL"]["precision"]
C["balanced150_v3_negative_precision"] = b3["per_class"]["NEGATIVE"]["precision"]
C["balanced150_v3_predicted_negative"] = b3["prediction_distribution"]["counts"]["NEGATIVE"]
C["balanced150_v3_neutral_errors_to_negative_minus_negative_errors_to_neutral"] = cc["NEUTRAL->NEGATIVE"] - cc["NEGATIVE->NEUTRAL"]
C["balanced150_v3_neutral_main_destination"] = max(["POSITIVE", "NEGATIVE", "UNPARSED"], key=lambda c: cc[f"NEUTRAL->{c}"])
C["interval_method"] = None
C["first100_v1_accuracy_wilson95"] = wilson(v1["correct"], 100)
C["first100_v3_accuracy_wilson95"] = wilson(f3["correct"], 100)
C["balanced150_v3_accuracy_wilson95"] = wilson(b3["correct"], 150)
C["balanced150_v3_neutral_recall_wilson95"] = wilson(cc["NEUTRAL->NEUTRAL"], 50)
C["balanced150_v3_neutral_to_negative_share_wilson95"] = wilson(cc["NEUTRAL->NEGATIVE"], 50)
C["balanced150_v3_neutral_to_positive_share_wilson95"] = wilson(cc["NEUTRAL->POSITIVE"], 50)
tot = sum(pool_sizes.values())
w = {c: pool_sizes[c] / tot for c in pool_sizes}
L3 = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
J = {(t, p): w[t] * cc[f"{t}->{p}"] / b3["truth_distribution"]["counts"][t] for t in L3 for p in L3}
col = {p: sum(J[(t, p)] for t in L3) for p in L3}
C["population_pool_sizes"] = pool_sizes
C["population_weights"] = w
C["population_weighting_note"] = None
C["balanced150_v3_population_weighted_accuracy"] = sum(J[(t, t)] for t in L3)
C["balanced150_v3_population_weighted_precision"] = {p: J[(p, p)] / col[p] for p in L3}
C["balanced150_v3_population_weighted_share_of_negative_predictions_from_neutral"] = J[("NEUTRAL", "NEGATIVE")] / col["NEGATIVE"]
C["balanced150_v3_population_weighted_share_of_neutral_predictions_from_positive"] = J[("POSITIVE", "NEUTRAL")] / col["NEUTRAL"]
C["balanced150_v3_share_of_negative_predictions_from_neutral"] = cc["NEUTRAL->NEGATIVE"] / b3["prediction_distribution"]["counts"]["NEGATIVE"]
C["balanced_accuracy_balanced150_v3_minus_first100_v3"] = b3["balanced_accuracy"] - f3["balanced_accuracy"]
for run in ("first100_v2", "first100_v3", "balanced150_v3"):
    e = MY_E[run]
    C[f"{run}_emotion_agreement_all_rows"] = e["agreement_rate_all_rows"]
    C[f"{run}_emotion_agreement_excluding_none_and_tie"] = e["agreement_rate_excluding_none_and_tie"]
    C[f"{run}_emotion_constant_baseline_emotion"] = e["constant_baseline_emotion"]
    C[f"{run}_emotion_constant_baseline_all_rows"] = e["constant_baseline_rate_all_rows"]
    C[f"{run}_emotion_llm_minus_constant_all_rows"] = e["llm_minus_constant_rate_all_rows"]
    C[f"{run}_emotion_llm_minus_constant_excluding_none_and_tie"] = e["llm_minus_constant_rate_excluding_none_and_tie"]
    C[f"{run}_emotion_best_constant_emotion"] = e["best_constant_baseline_emotion"]
    C[f"{run}_emotion_best_constant_all_rows"] = e["best_constant_baseline_rate_all_rows"]
    C[f"{run}_emotion_best_constant_excluding_none_and_tie"] = e["best_constant_baseline_rate_excluding_none_and_tie"]
    C[f"{run}_emotion_llm_minus_best_constant_all_rows"] = e["llm_minus_best_constant_rate_all_rows"]
    C[f"{run}_emotion_llm_minus_best_constant_excluding_none_and_tie"] = e["llm_minus_best_constant_rate_excluding_none_and_tie"]
CMP = json.load(open(RUNS / "comparisons.json"))
for k in ("note", "sources", "interval_method", "population_weighting_note"):
    C[k] = CMP.get(k)
deep_compare(C, CMP, "comparisons.json")
print(f"weights {w}; reweighted acc {C['balanced150_v3_population_weighted_accuracy']:.4f}; prec {C['balanced150_v3_population_weighted_precision']}")
print("Wilson:", {k: [round(100 * x, 1) for x in v] for k, v in C.items() if k.endswith("wilson95")})
MY_C = C

# ------------------------------------------------------------------ verify_leak
print("== verify_leak.py")
vl = subprocess.run([str(ROOT / ".venv/bin/python"), "src/verify_leak.py"], cwd=ROOT, capture_output=True, text=True)
print(vl.stdout.strip(), vl.stderr.strip(), f"exit={vl.returncode}")
check(vl.returncode == 0 and "FAIL" not in vl.stdout, "verify_leak.py did not pass")
bp = {p["review_id"]: p for p in PREDS["balanced150_v3"]}
FORB = re.compile(r"\b(rating|star|stars|helpful|verified)\b", re.IGNORECASE)
own = [(p["review_id"], FORB.findall(("" if STAR.match(p["title"]) else p["title"]) + "\n" + ("" if STAR.match(p["text"]) else p["text"])))
       for p in PREDS["balanced150_v3"]]
own = [x for x in own if x[1]]
print("balanced rows whose sent title/text contain forbidden words:", own)
for run in RUN_NAMES:
    print(f"  {run} star-phrase title-or-text rows: {sum(bool(STAR.match(p['title']) or STAR.match(p['text'])) for p in PREDS[run])}, "
          f"title-only: {sum(bool(STAR.match(p['title'])) for p in PREDS[run])}")

# ------------------------------------------------------------------ dashboard
print("== dashboard (Playwright headless Chromium)")
page_html = (ROOT / "dashboard/index.html").read_text(encoding="utf-8")
m = re.search(r'<script id="dashboard-data" type="application/json">(.*?)</script>', page_html, re.S)
DATA = json.loads(m.group(1).replace("<\\/", "</"))
check(DATA["comparisons"] == CMP, "embedded comparisons != runs/comparisons.json")
check(DATA["rating_distribution"] == rd, "embedded rating_distribution != file")
check([r["run"] for r in DATA["runs"]] == RUN_NAMES, f"embedded run order {[r['run'] for r in DATA['runs']]}")
for r in DATA["runs"]:
    run = r["run"]
    check(r["metrics"] == json.load(open(RUNS / run / "metrics.json")), f"{run}: embedded metrics != file (stale build)")
    if "emotion_metrics" in r:
        check(r["emotion_metrics"] == json.load(open(RUNS / run / "emotion_metrics.json")), f"{run}: embedded emotion_metrics stale")
    for k, v in r["meta"].items():
        check(META[run][k] == v, f"{run}: embedded meta {k} stale")
    check([x["review_id"] for x in r["rows"]] == [p["review_id"] for p in PREDS[run]], f"{run}: embedded rows order")
tmpl = (ROOT / "dashboard/template.html").read_text(encoding="utf-8")
check(tmpl.split("__DASHBOARD_DATA__")[0] == page_html[:len(tmpl.split("__DASHBOARD_DATA__")[0])], "index.html prefix != template")
check(page_html.endswith(tmpl.split("__DASHBOARD_DATA__")[1]), "index.html suffix != template")


def js_fixed1(x):
    return str(Decimal(x).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def js_string(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(int(v)) if float(v).is_integer() else repr(v)
    return str(v)


def fmt(format_, v):
    if format_ == "pct":
        return js_fixed1(v * 100) + "%"
    if format_ == "count":
        return f"{round(v):,}"
    if format_ == "pp":
        return ("−" if v < 0 else "+") + js_fixed1(abs(v * 100)) + " pts"
    return js_string(v)


def resolve(obj, path):
    for part in path.split("."):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            return KeyError
    return obj


JS_COLLECT = r"""() => {
  const metrics = [...document.querySelectorAll('[data-metric][data-raw]')].map(e => ({
    metric: e.dataset.metric, raw: e.dataset.raw, source: e.dataset.source, format: e.dataset.format,
    run: e.dataset.run, text: e.textContent, visible: e.checkVisibility()}));
  const marks = [...document.querySelectorAll('[data-value]')].map(e => { const b = e.getBoundingClientRect(); return {
    metric: e.dataset.metric, value: e.dataset.value, label: e.dataset.label, run: e.dataset.run,
    w: b.width, h: b.height, visible: e.checkVisibility(), hasRaw: e.hasAttribute('data-raw')}; });
  const rows = [...document.querySelectorAll('#review-table tbody tr')].map(t => ({
    id: t.dataset.reviewId, truth: t.dataset.truth, pred: t.dataset.prediction, correct: t.dataset.correct,
    stars: t.cells[1].textContent}));
  const loose = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const n = walker.currentNode, p = n.parentElement;
    if (!/\d/.test(n.nodeValue) || !p || p.closest('script,style,[data-metric],#review-table tbody')) continue;
    if (!p.checkVisibility()) continue;
    loose.push((p.id ? '#' + p.id + ' ' : '') + JSON.stringify(n.nodeValue.trim().slice(0, 90)));
  }
  const cnt = document.getElementById('shown-count');
  const missingAttrs = [...document.querySelectorAll('[data-metric]')].filter(e =>
    !(e.hasAttribute('data-value') || (e.hasAttribute('data-raw') && e.hasAttribute('data-source')))).length;
  return {metrics, marks, rows, loose, liveCount: cnt && cnt.textContent, liveData: cnt && cnt.dataset.liveCount,
          missingAttrs, text: document.body.innerText, selected: document.body.dataset.run};
}"""

from playwright.sync_api import sync_playwright  # noqa: E402

DASH_SUMMARY = {}
LOOSE = {}
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto((ROOT / "dashboard/index.html").resolve().as_uri())
    page.wait_for_selector("[data-run-tab]")
    for run in RUN_NAMES:
        page.click(f'[data-run-tab="{run}"]')
        page.wait_for_function(f"document.body.dataset.run === '{run}'")
        d = page.evaluate(JS_COLLECT)
        check(d["selected"] == run, f"dashboard selected {d['selected']} != {run}")
        check(d["missingAttrs"] == 0, f"{run}: {d['missingAttrs']} data-metric elements lack data-raw/data-source or data-value")
        for bad in ("[object", "undefined", "NaN"):
            check(bad not in d["text"], f"{run}: page text contains {bad}")
        mm, me = MY_M[run], MY_E.get(run)
        nm = 0
        text_numeric = set()
        for x in d["metrics"]:
            nm += 1
            file_, _, field = x["source"].partition("#")
            check(field == x["metric"], f"{run}: data-source field {field} != data-metric {x['metric']}")
            check(x["run"] == run, f"{run}: metric {x['metric']} data-run {x['run']}")
            raw = json.loads(x["raw"])
            if file_ == f"runs/{run}/metrics.json":
                mine = resolve(mm, field)
                filev = resolve(json.load(open(ROOT / file_)), field)
            elif file_ == f"runs/{run}/emotion_metrics.json":
                mine = resolve(me, field)
                filev = resolve(json.load(open(ROOT / file_)), field)
            elif file_ == f"runs/{run}/run_meta.json":
                filev = resolve(META[run], field)
                mine = mm[field] if field in ("n_rows", "parse_fail_count", "api_error_count") else filev
            elif file_ == "runs/comparisons.json":
                mine = resolve(MY_C, field)
                filev = resolve(CMP, field)
            else:
                check(False, f"{run}: metric {field} sourced from foreign file {file_}")
                continue
            check(mine is not KeyError, f"{run}: {x['source']} not a real field")
            check(close(raw, filev) and type(raw) is type(filev) or close(raw, filev), f"{run}: {x['source']} data-raw {raw!r} != file {filev!r}")
            check(close(raw, mine), f"{run}: {x['source']} data-raw {raw!r} != recomputed {mine!r}")
            check(x["text"] == fmt(x["format"], raw), f"{run}: {x['source']} shows {x['text']!r}, rule gives {fmt(x['format'], raw)!r}")
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                if x["format"] == "count":
                    check(float(raw).is_integer(), f"{run}: {field} non-integer shown as count")
                if x["format"] == "pct":
                    check(0 <= raw <= 1, f"{run}: {field} pct outside [0,1]")
                if x["format"] == "text":
                    text_numeric.add(field)
        for x in d["marks"]:
            check(x["run"] == run, f"{run}: mark {x['metric']} data-run {x['run']}")
            check(bool(x["label"]), f"{run}: mark {x['metric']} empty data-label")
            path = x["metric"]
            mine = resolve(me, path[len("emotion."):]) if path.startswith("emotion.") else resolve(mm, path)
            check(mine is not KeyError and x["value"] == js_string(mine), f"{run}: mark {path} data-value {x['value']} != recomputed {mine}")
            if mine not in (KeyError, 0) and x["visible"]:
                check(x["w"] > 0.5 and x["h"] > 0.5, f"{run}: mark {path} value {mine} rendered {x['w']:.2f}x{x['h']:.2f}px")
        preds = PREDS[run]
        check(len(d["rows"]) == len(preds), f"{run}: table rows {len(d['rows'])}")
        for tr, p in zip(d["rows"], preds):
            ok = p["prediction"] == p["truth"]
            check(tr["id"] == str(p["review_id"]) and tr["truth"] == p["truth"] and tr["pred"] == p["prediction"]
                  and tr["correct"] == str(ok).lower() and tr["stars"] == js_string(p["rating"]) + "★", f"{run}: table row {tr}")
        check(d["liveCount"] == f"{len(preds):,}" and d["liveData"] == str(len(preds)), f"{run}: live count {d['liveCount']}")
        LOOSE[run] = d["loose"]
        DASH_SUMMARY[run] = (nm, len(d["marks"]), len(d["rows"]), sorted(text_numeric))
        print(f"{run}: {nm} data-metric numbers, {len(d['marks'])} chart marks, {len(d['rows'])} table rows; numeric fields shown as text: {sorted(text_numeric)}")
        print("  visible digit text outside data-metric (table body excluded):", LOOSE[run])
    check(not errors, f"console/page errors: {errors}")
    browser.close()

# ------------------------------------------------------------------ written claims
print("== written claims")
AN = (ROOT / "reviews/step6_analysis.md").read_text(encoding="utf-8")
ISS = (ROOT / "ISSUES.md").read_text(encoding="utf-8")
ISS6 = ISS[ISS.index("## Step 6"):]
PRO = (ROOT / "PROGRESS.md").read_text(encoding="utf-8")
DOCS = {"analysis": AN, "ISSUES": ISS6, "PROGRESS": PRO}
NCLAIM = [0]


def p1(x):
    return js_fixed1(100 * x)


def claim(doc, quote, cond, note=""):
    NCLAIM[0] += 1
    check(quote in DOCS[doc], f"[{doc}] quote not found: {quote!r}")
    check(bool(cond), f"[{doc}] {quote!r} does not hold {note}")


b = MY_M["balanced150_v3"]
bc = b["confusion_cells"]
bpc = b["per_class"]
eb, ef, e2 = MY_E["balanced150_v3"], MY_E["first100_v3"], MY_E["first100_v2"]
mis = b["misclassified_review_ids"]
f3m = f3["misclassified_review_ids"]
bal = PREDS["balanced150_v3"]
emo_by = lambda t, e: sum(1 for p in bal if p["truth"] == t and p["llm_emotion"] == e)  # noqa: E731
f3_pos_trust = sum(1 for p in PREDS["first100_v3"] if p["truth"] == "POSITIVE" and p["llm_emotion"] == "trust")
neu_blank = [p for p in bal if p["truth"] == "NEUTRAL" and STAR.match(p["title"])]
neu_rest = [p for p in bal if p["truth"] == "NEUTRAL" and not STAR.match(p["title"])]
v1p = {p["review_id"]: p["prediction"] for p in PREDS["first100_v1"]}
moved = [(p["review_id"], v1p[p["review_id"]], p["prediction"]) for p in PREDS["first100_v3"] if p["prediction"] != v1p[p["review_id"]]]
print("v1 -> v3 moved on batch_100:", moved)
f3_nonjoy = [p for p in PREDS["first100_v3"] if p["llm_emotion"] != "joy"]
gift17 = [p["review_id"] for p in bal if p["nrc_emotion"] == "anticipation" and any(h[1] == "gift" or h[0] == "gift" for h in p["nrc_hits"])]
dup_groups = [k for k, v in Counter((p["title"], p["text"]) for p in bal).items() if v > 1]
star_pct = {c: 100 * a / bb for c, (a, bb) in title_star_share.items()}
wil = {k: [p1(x) for x in v] for k, v in MY_C.items() if k.endswith("wilson95")}
retry_rows = [(r, p["review_id"], p["raw_responses"]) for r in RUN_NAMES for p in PREDS[r] if len(p["raw_responses"]) > 1]
print("retry rows:", retry_rows, "| dup groups:", dup_groups, "| gift anticipation:", len(gift17))
halfw = {k: (float(v[1]) - float(v[0])) / 2 for k, v in wil.items()}
print("Wilson half-widths (pts):", halfw)

A = "analysis"
claim(A, "Of 50, 17 are predicted NEUTRAL, **25 are predicted NEGATIVE** and 8 POSITIVE", (bc["NEUTRAL->NEUTRAL"], bc["NEUTRAL->NEGATIVE"], bc["NEUTRAL->POSITIVE"]) == (17, 25, 8))
claim(A, "4 of 50 1–2★ reviews are predicted NEUTRAL", bc["NEGATIVE->NEUTRAL"] == 4)
claim(A, "NEGATIVE 14,178, NEUTRAL 3,270, POSITIVE 134,913", pool_sizes == {"NEGATIVE": 14178, "NEUTRAL": 3270, "POSITIVE": 134913})
claim(A, "1★ 43, 2★ 7, 3★ 50, **4★ 0**, 5★ 50", b["sample_rating_counts"] == {"1": 43, "2": 7, "3": 50, "4": 0, "5": 50})
claim(A, "Truth: POSITIVE 50 / NEUTRAL 50 / NEGATIVE 50. Predicted: POSITIVE 57 / NEUTRAL 23 / NEGATIVE 70 / UNPARSED 0.",
      b["prediction_distribution"]["counts"] == {"POSITIVE": 57, "NEUTRAL": 23, "NEGATIVE": 70, "UNPARSED": 0})
claim(A, "**Accuracy 73.3%** (110/150)", b["correct"] == 110 and p1(b["accuracy"]) == "73.3")
claim(A, "any single constant answer scores 33.3%", p1(b["majority_baseline_accuracy"]) == "33.3")
claim(A, "**Balanced accuracy 73.3%**, macro F1 70.4%.", p1(b["balanced_accuracy"]) == "73.3" and p1(b["macro_f1"]) == "70.4")
claim(A, "**Parse failures 0, API errors 0.** One row needed a retry", b["parse_fail_count"] == 0 and b["api_error_count"] == 0 and b["rows_needing_retry"] == 1)
claim(A, "| POSITIVE (50) | **48** | 2 | 0 | 0 |", b["confusion_matrix"]["counts"][0] == [48, 2, 0, 0])
claim(A, "| NEUTRAL (50)  | 8 | **17** | 25 | 0 |", b["confusion_matrix"]["counts"][1] == [8, 17, 25, 0])
claim(A, "| NEGATIVE (50) | 1 | 4 | **45** | 0 |", b["confusion_matrix"]["counts"][2] == [1, 4, 45, 0])
for k, s in [("POSITIVE", "48/50 = 96.0% | 48/57 = 84.2%"), ("NEUTRAL", "17/50 = 34.0% | 17/23 = 73.9%"), ("NEGATIVE", "45/50 = 90.0% | 45/70 = 64.3%")]:
    c_, pr_ = bpc[k], bpc[k]
    claim(A, s, s == f"{c_['correct']}/{c_['support']} = {p1(c_['recall'])}% | {c_['correct']}/{c_['predicted']} = {p1(c_['precision'])}%")
claim(A, "POSITIVE 96.0%, NEGATIVE 90.0%", True)
claim(A, "88.5% POSITIVE, 2.1% NEUTRAL, 9.3% NEGATIVE", (p1(w["POSITIVE"]), p1(w["NEUTRAL"]), p1(w["NEGATIVE"])) == ("88.5", "2.1", "9.3"))
claim(A, "Accuracy would be about 94.1%", p1(MY_C["balanced150_v3_population_weighted_accuracy"]) == "94.1")
claim(A, "NEUTRAL precision would be about **14.5%**, not 73.9%", p1(MY_C["balanced150_v3_population_weighted_precision"]["NEUTRAL"]) == "14.5")
claim(A, "About 70.6% of NEUTRAL answers", p1(MY_C["balanced150_v3_population_weighted_share_of_neutral_predictions_from_positive"]) == "70.6")
claim(A, "25 of 70 = 35.7%", p1(25 / 70) == "35.7")
claim(A, "about 11.4% re-weighted", p1(MY_C["balanced150_v3_population_weighted_share_of_negative_predictions_from_neutral"]) == "11.4")
claim(A, "2 POSITIVE→NEUTRAL", bc["POSITIVE->NEUTRAL"] == 2)
claim(A, "25 of 50 = 50.0%", bc["NEUTRAL->NEGATIVE"] == 25)
claim(A, "Wilson 95% interval 36.6%–63.4%", wil["balanced150_v3_neutral_to_negative_share_wilson95"] == ["36.6", "63.4"])
claim(A, "8 of 50 = 16.0%; interval 8.3%–28.5%", wil["balanced150_v3_neutral_to_positive_share_wilson95"] == ["8.3", "28.5"])
claim(A, "17 of 50 = 34.0%; interval 22.4%–47.8%", wil["balanced150_v3_neutral_recall_wilson95"] == ["22.4", "47.8"])
claim(A, "4–5★ → NEUTRAL: 2 of 50", bc["POSITIVE->NEUTRAL"] == 2)
claim(A, "1–2★ → POSITIVE 1; 4–5★ → NEGATIVE 0", bc["NEGATIVE->POSITIVE"] == 1 and bc["POSITIVE->NEGATIVE"] == 0)
claim(A, "exceeds NEGATIVE→NEUTRAL by 21 reviews", bc["NEUTRAL->NEGATIVE"] - bc["NEGATIVE->NEUTRAL"] == 21)
claim(A, "The LLM gave 20 of them the emotion anger, 4 sadness and 1 disgust",
      Counter(p["llm_emotion"] for p in bal if p["review_id"] in mis["NEUTRAL->NEGATIVE"]) == Counter({"anger": 20, "sadness": 4, "disgust": 1}))
groups = {"(5)": [6689, 33885, 114708, 51332, 48586], "(4)": [18646, 32735, 60681, 88199], "(3)": [53136, 60608, 129667],
          "(7)": [22082, 29467, 88606, 94255, 119458, 111827, 147336], "(2)a": [88787, 111780], "(2)b": [140179, 143371], "(2)c": [4880, 121389]}
claim(A, "**Other (2):** 4880", sorted(sum(groups.values(), [])) == sorted(mis["NEUTRAL->NEGATIVE"]), "(group ids != NEUTRAL->NEGATIVE ids)")
claim(A, "Seven of the 25 contain some praise", all(i in mis["NEUTRAL->NEGATIVE"] for i in [88787, 60608, 53136, 121389, 32735, 60681, 147336]))
claim(A, "Four had their auto-filled \"Three Stars\" title blanked for the model: 43478",
      all(bp[i]["title"] == "Three Stars" for i in [43478, 73030, 144067, 146724]) and bp[134401]["title"] == "Yas"
      and sorted([43478, 73030, 144067, 146724, 134401, 20086, 23773, 144273]) == sorted(mis["NEUTRAL->POSITIVE"]))
claim(A, "10 in the NEUTRAL draw, against a mean of 6.6 over 1,000 seeds (117 of 1,000 reach 10 or more)",
      seed42_neu == 10 and f"{SEEDS['neu_mean']:.1f}" == "6.6" and SEEDS["neu_ge10"] == 117)
claim(A, "Those 10 NEUTRAL rows scored 5 correct and 4 predicted POSITIVE; the other 40 scored 12 correct and 4 predicted POSITIVE",
      (len(neu_blank), sum(p["prediction"] == "NEUTRAL" for p in neu_blank), sum(p["prediction"] == "POSITIVE" for p in neu_blank),
       len(neu_rest), sum(p["prediction"] == "NEUTRAL" for p in neu_rest), sum(p["prediction"] == "POSITIVE" for p in neu_rest)) == (10, 5, 4, 40, 12, 4))
claim(A, "31137 (\"One Star\" blanked)", bp[31137]["title"] == "One Star" and bp[99795]["title"] == "One Star"
      and sorted([31137, 49142, 99795, 136849]) == sorted(mis["NEGATIVE->NEUTRAL"]) and sorted([12158, 43820]) == sorted(mis["POSITIVE->NEUTRAL"])
      and mis["NEGATIVE->POSITIVE"] == [116236])
claim(A, "| truth counts (POS/NEU/NEG) | 93 / 2 / 5 | 50 / 50 / 50 |", f3["truth_distribution"]["counts"] == {"POSITIVE": 93, "NEUTRAL": 2, "NEGATIVE": 5})
claim(A, "| star mix (1★/2★/3★/4★/5★) | 4 / 1 / 2 / 2 / 91 | 43 / 7 / 50 / 0 / 50 |", f3["sample_rating_counts"] == {"1": 4, "2": 1, "3": 2, "4": 2, "5": 91})
claim(A, "| accuracy | 95.0% (95/100) | 73.3% (110/150) |", f3["correct"] == 95)
claim(A, "| majority baseline | 93.0% | 33.3% |", p1(f3["majority_baseline_accuracy"]) == "93.0")
claim(A, "| balanced accuracy | 65.6% | 73.3% |", p1(f3["balanced_accuracy"]) == "65.6")
claim(A, "| macro F1 | 60.4% | 70.4% |", p1(f3["macro_f1"]) == "60.4")
claim(A, "| NEUTRAL recall | 0 of 2 | 17 of 50 |", f3["per_class"]["NEUTRAL"]["correct"] == 0)
claim(A, "| NEGATIVE recall | 5 of 5 | 45 of 50 |", f3["per_class"]["NEGATIVE"]["correct"] == 5)
claim(A, "**Accuracy falls by 21.7 points**", p1(-(b["accuracy"] - f3["accuracy"])) == "21.7")
claim(A, "93 of the 100 reviews are POSITIVE, the model gets 90 of those right", f3["per_class"]["POSITIVE"]["correct"] == 90)
claim(A, "**Balanced accuracy rises by 7.7 points**", p1(b["balanced_accuracy"] - f3["balanced_accuracy"]) == "7.7")
claim(A, "(91 → NEGATIVE, 98 → POSITIVE)", f3m.get("NEUTRAL->NEGATIVE") == [91] and f3m.get("NEUTRAL->POSITIVE") == [98])
claim(A, "only two predictions moved: 46 (NEGATIVE → NEUTRAL) and 83", moved == [(46, "NEGATIVE", "NEUTRAL"), (83, "POSITIVE", "NEUTRAL")]
      and all(rows_all[i]["rating"] == 5 for i in (46, 83)))
claim(A, "`first100_v1`: 97.0% (97/100) against a 93.0% majority baseline, with 7 NEGATIVE reviews", v1["correct"] == 97 and v1["per_class"]["NEGATIVE"]["support"] == 7)
claim(A, "it rarely answers NEUTRAL (23 times for 50 NEUTRAL reviews)", b["prediction_distribution"]["counts"]["NEUTRAL"] == 23)
claim(A, "each share could move by roughly ±13 points", all(abs(halfw[k] - 13) <= 1 for k in ["balanced150_v3_neutral_to_negative_share_wilson95", "balanced150_v3_neutral_recall_wilson95"]))
claim(A, "plain accuracy of the run 65.7%–79.8%", wil["balanced150_v3_accuracy_wilson95"] == ["65.7", "79.8"])
claim(A, "63 of 1,000 seeds also draw no 4★ reviews", SEEDS["zero4"] == 63)
claim(A, "median 21, 5th–95th percentile 14–28, against 26 for seed 42", SEEDS["median"] == 21 and (SEEDS["p5"], SEEDS["p95"]) == (14, 28) and seed42_whole == 26)
claim(A, "`first100_v3` accuracy 95.0% has interval 88.8%–97.8%; `first100_v1` 97.0% has 91.5%–99.0%",
      wil["first100_v3_accuracy_wilson95"] == ["88.8", "97.8"] and wil["first100_v1_accuracy_wilson95"] == ["91.5", "99.0"])
claim(A, "Review 4880 was the only row in any run that needed a retry", len(retry_rows) == 1 and retry_rows[0][1] == 4880
      and retry_rows[0][2] == ["LABEL=NEGATIVE;EMOTION=disappointment", "LABEL=NEGATIVE;EMOTION=sadness"])
claim(A, "16/150 = 10.7%, and on 16/59 = 27.1%", eb["agreement"]["all_rows"]["agree"] == 16 and eb["agreement"]["excluding_none_and_tie"]["n"] == 59)
claim(A, "anger (62 of 150). A constant \"anger\" agrees only 4/150 (2.7%)", eb["llm_emotion_counts"]["anger"] == 62 and eb["constant_baseline"]["all_rows"]["agree"] == 4)
claim(A, "22/150 = 14.7%, and 22/59 = 37.3%", eb["best_constant_baseline_emotion"] == "anticipation" and eb["best_constant_baseline"]["all_rows"]["agree"] == 22)
claim(A, "**The LLM is 4.0 points below it on all rows, and 10.2 points below where the word list has one winner**",
      p1(-eb["llm_minus_best_constant_rate_all_rows"]) == "4.0" and p1(-eb["llm_minus_best_constant_rate_excluding_none_and_tie"]) == "10.2")
claim(A, "tied on 67 reviews and found no emotion words in 24", eb["tie_rows"] == 67 and eb["none_rows"] == 24)
claim(A, "agreement 20/100 against a constant \"joy\" at 22/100 (−2.0 points). In the 18 reviews where the LLM did not say joy, the two methods agree 0 times.",
      ef["agreement"]["all_rows"]["agree"] == 20 and ef["constant_baseline_emotion"] == "joy" and ef["constant_baseline"]["all_rows"]["agree"] == 22
      and len(f3_nonjoy) == 18 and sum(p["emotion_agree"] for p in f3_nonjoy) == 0, f"(non-joy rows {len(f3_nonjoy)}, agree {sum(p['emotion_agree'] for p in f3_nonjoy)})")
claim(A, "the LLM never agrees with the word list more often than the best constant answer",
      all(MY_E[r]["agreement"]["all_rows"]["agree"] <= MY_E[r]["best_constant_baseline"]["all_rows"]["agree"] for r in MY_E))
claim(A, "NEGATIVE 41, NEUTRAL 21", emo_by("NEGATIVE", "anger") == 41 and emo_by("NEUTRAL", "anger") == 21 and emo_by("POSITIVE", "anger") == 0)
claim(A, "POSITIVE 10, NEUTRAL 11, NEGATIVE 1", (emo_by("POSITIVE", "trust"), emo_by("NEUTRAL", "trust"), emo_by("NEGATIVE", "trust")) == (10, 11, 1))
claim(A, "10/50 here against 9/93 on `first100_v3`", f3_pos_trust == 9)
claim(A, "in 17 of its 22 anticipation answers, \"gift\" is among the hit words", len(gift17) == 17)
claim(A, "26 of 150 titles were auto-filled star phrases", seed42_whole == 26)
claim(A, "(4 of 100 in batch_100)", sum(bool(STAR.match(p["title"])) for p in PREDS["first100_v3"]) == 4)
claim(A, "22.7% of POSITIVE, 13.1% of NEUTRAL and 5.8% of NEGATIVE", [f"{star_pct[c]:.1f}" for c in L3] == ["22.7", "13.1", "5.8"])
claim(A, "121389 (text, \"Cannot give 5 stars…\") and 140676 (title, \"I would give this 'zero stars'\", predicted NEGATIVE correctly)",
      sorted(i for i, _ in own) == [121389, 138151, 140676] and bp[140676]["prediction"] == bp[140676]["truth"] == "NEGATIVE")

I = "ISSUES"
claim(I, "Checked before first use: 0 digits, 0 of rating/star/stars/helpful/verified.",
      not re.search(r"\d", (ROOT / "prompts/sentiment_v3.txt").read_text()) and not FORB.search((ROOT / "prompts/sentiment_v3.txt").read_text()))
claim(I, "50 per class, 150 unique, no overlap with batch_100", len(set(bal_ids)) == 150 and not set(bal_ids) & set(batch100))
claim(I, "4★ reviews are 6,691 of the 134,913 POSITIVE pool (under 5%)", four_in_pos == 6691 and four_in_pos / pool_sizes["POSITIVE"] < 0.05)
claim(I, "63 of 1,000 seeds (0–999) also draw zero 4★ reviews into POSITIVE", SEEDS["zero4"] == 63)
claim(I, "so the run had 4 cache hits (3 from the preview + 1 repeat) and sent 146 rows; with one parse retry (review 4880, below) that is 147 API calls",
      META["balanced150_v3"]["cache_hits"] == 4 and sum(not p["from_cache"] for p in bal) == 146 and META["balanced150_v3"]["api_call_count"] == 147 and len(dup_groups) == 1)
claim(I, "26 of the 150 titles are star phrases (\"Five Stars\", \"One Star\"…) and were blanked for the model, against 4 of 100 in batch_100", seed42_whole == 26)
claim(I, "auto-filled star titles make up 22.7% of the POSITIVE pool, 13.1% of NEUTRAL and 5.8% of NEGATIVE", [f"{star_pct[c]:.1f}" for c in L3] == ["22.7", "13.1", "5.8"])
claim(I, "(median over 1,000 seeds 21, 5th–95th percentile 14–28)", SEEDS["median"] == 21 and (SEEDS["p5"], SEEDS["p95"]) == (14, 28))
claim(I, "Seed 42 put 10 star-phrase titles into NEUTRAL (mean 6.6 over seeds; 117 of 1,000 seeds reach 10 or more); those 10 NEUTRAL rows scored 5 correct (4 predicted POSITIVE), the other 40 scored 12 correct (24 predicted NEGATIVE).",
      sum(p["prediction"] == "NEGATIVE" for p in neu_rest) == 24)
claim(I, "`balanced150_v3` 73.3% (110/150) against a 33.3% majority baseline. NEUTRAL (3★) row: 17 predicted NEUTRAL, 25 NEGATIVE, 8 POSITIVE. Reverse direction: 4 NEGATIVE reviews predicted NEUTRAL; 2 POSITIVE predicted NEUTRAL. The model predicted NEGATIVE for 70 of 150.", True)
claim(I, "95.0% (95/100) against a 93.0% majority baseline; balanced accuracy 65.6%. Three-class truth on batch_100 is POSITIVE 93, NEUTRAL 2, NEGATIVE 5",
      f3["correct"] == 95 and p1(f3["balanced_accuracy"]) == "65.6")
claim(I, "(one predicted POSITIVE, one NEGATIVE)", f3m.get("NEUTRAL->POSITIVE") == [98] and f3m.get("NEUTRAL->NEGATIVE") == [91])
claim(I, "93 API calls, 7 cache hits (the duplicate \"Good Product\" rows again), 0 parse failures",
      META["first100_v3"]["api_call_count"] == 93 and META["first100_v3"]["cache_hits"] == 7 and f3["parse_fail_count"] == 0)
claim(I, "review 140179 (\"Disappointing\"", bp[140179]["prediction"] == bp[143371]["prediction"] == "NEGATIVE" and bp[140179]["rating"] == bp[143371]["rating"] == 3)
claim(I, "`verify_leak.py`'s \"3 reviews use a forbidden word\" on this run = these two + 138151's title \"Helpful Review\"",
      "3 reviews use a forbidden word" in vl.stdout and sorted(i for i, _ in own) == [121389, 138151, 140676])
claim(I, "Only row needing a retry in any run (`rows_needing_retry: 1`)", len(retry_rows) == 1)
claim(I, "Numbers Auditor 0 mismatches over 11,865 checks + 3 MINOR", "TOTAL checks: 11865; FAILURES: 0" in (ROOT / "reviews/step6_numbers_auditor.md").read_text())
claim(I, "Re-weighted to the file's 88.5% / 2.1% / 9.3% class mix, NEUTRAL precision would be about 14.5% and accuracy about 94.1%", True)
claim(I, "The margin comparison is replaced by balanced accuracy (65.6% → 73.3%)", True)
claim(I, "It is now reported by class: POSITIVE 10, NEUTRAL 11, NEGATIVE 1.", True)
claim(I, "four had a blanked \"Three Stars\" title: 43478", True)
claim(I, "a constant \"anger\" agrees with the word list on only 4/150, a weak bar the LLM clears easily (16/150). The word list's own most common single answer (anticipation, 22)", True)
claim(I, "(LLM emotion in 45 ties, constant \"joy\" in 45)", ef["tie_rows_llm_emotion_in_tied_set"] == 45 and ef["tie_rows_constant_in_tied_set"] == 45
      and e2["tie_rows_llm_emotion_in_tied_set"] == 45 and e2["tie_rows_constant_in_tied_set"] == 45)
claim(I, "where the LLM's emotion is in 37 of 67 ties and the constant \"anger\" in only 6", eb["tie_rows_llm_emotion_in_tied_set"] == 37 and eb["tie_rows_constant_in_tied_set"] == 6)

P = "PROGRESS"
claim(P, "balanced150_v3 73.3% (110/150), baseline 33.3%, NEUTRAL row 17 NEUTRAL / 25 NEGATIVE / 8 POSITIVE, NEGATIVE→NEUTRAL 4, POSITIVE→NEUTRAL 2, NEGATIVE→POSITIVE 1, predicted NEGATIVE 70", True)
claim(P, "recall POS 48/50, NEU 17/50, NEG 45/50", True)
claim(P, "first100_v3 95.0% (95/100), baseline 93.0%, balanced acc 65.6%, truth 93/2/5, errors 46, 83 (POS→NEU), 17 (POS→NEG), 98 (NEU→POS), 91 (NEU→NEG)",
      f3m == {"POSITIVE->NEUTRAL": [46, 83], "POSITIVE->NEGATIVE": [17], "NEUTRAL->POSITIVE": [98], "NEUTRAL->NEGATIVE": [91]})
claim(P, "Balanced sample star mix 1★43 2★7 3★50 4★0 5★50; 26 star titles blanked; 1 duplicate pair", len(dup_groups) == 1 and seed42_whole == 26)
claim(P, "Emotions balanced: agreement 16/150; LLM top emotion anger (62) → constant anger 4/150; BEST constant (new field `best_constant_baseline*`) anticipation 22/150 (14.7%), 22/59 (37.3%) → LLM −4.0 / −10.2 pts", True)
claim(P, "first100_v3 emotions: 20/100 vs constant joy 22/100 (best constant also joy)", ef["best_constant_baseline_emotion"] == "joy")
claim(P, "NEUTRAL→NEGATIVE share 36.6–63.4%, NEUTRAL recall 22.4–47.8%, NEUTRAL→POSITIVE 8.3–28.5%", True)
claim(P, "Wilson 95% (comparisons.json): balanced accuracy 65.7–79.8%", False,
      "(label: comparisons.json balanced150_v3_accuracy_wilson95 = Wilson(110,150), the interval for plain accuracy, not balanced accuracy)")
claim(P, "(weights 88.5/2.1/9.3%; re-weighted accuracy ~94.1%, NEUTRAL precision ~14.5%)", True)
claim(P, "(65.6% → 73.3%, +7.7 pts)", True)
claim(P, "(count: see last line of `reviews/step6_verify_dashboard.txt`; 3,766 at the round-1 fix build)",
      "3766 checks, 0 failures" in (ROOT / "reviews/step6_verify_dashboard.txt").read_text())
claim(P, "`reviews/step6_numbers_auditor.md` (0 mismatches / 11,865 checks, 3 MINOR)", True)
claim(P, "442 after Step 6 runs (199 + 3 balanced preview + 147 balanced150_v3 + 93 first100_v3)",
      json.load(open(ROOT / "cache/api_calls_total.json"))["total"] == 442 == 199 + 3 + 147 + 93)

print(f"written claims checked: {NCLAIM[0]}")
print(f"TOTAL checks: {CHECKS[0]}; FAILURES: {len(FAILS)}")
for f_ in FAILS:
    print("  -", f_)
sys.exit(1 if FAILS else 0)
