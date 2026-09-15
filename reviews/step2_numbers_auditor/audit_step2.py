"""Independent Step 2 numbers audit. Does not import src/score.py (or any src module).

Recomputes every metric from runs/first100_v1/predictions.jsonl, re-derives truth from the
source ratings in data/Gift_Cards.jsonl.gz, re-parses stored raw responses, and checks
metrics.json, run_meta.json, rating_distribution.json, and the numeric/factual claims in
reviews/step2_analysis.md and ISSUES.md (Step 2 entries).
Usage: .venv/bin/python reviews/step2_numbers_auditor/audit_step2.py
"""
import gzip
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs" / "first100_v1"
FAILS = []


def check(name, got, expected, tol=1e-9):
    if isinstance(expected, float) or isinstance(got, float):
        ok = got is not None and expected is not None and math.isclose(got, expected, abs_tol=tol)
    else:
        ok = got == expected
    print(f"{'OK  ' if ok else 'FAIL'} {name}: recomputed={expected!r} reported={got!r}")
    if not ok:
        FAILS.append(name)


preds = [json.loads(l) for l in open(RUN / "predictions.jsonl", encoding="utf-8")]
metrics = json.loads((RUN / "metrics.json").read_text())
meta = json.loads((RUN / "run_meta.json").read_text())
dist = json.loads((ROOT / "runs" / "rating_distribution.json").read_text())

# ---- source file: ratings for truth, inclusion rule, batch selection, rating distribution
src_rows, rating_counts, excluded_by_rating, total, first_included = {}, Counter(), Counter(), 0, []
with gzip.open(ROOT / "data" / "Gift_Cards.jsonl.gz", "rt", encoding="utf-8") as f:
    for i, line in enumerate(f):
        row = json.loads(line)
        total += 1
        r = int(row["rating"])
        rating_counts[r] += 1
        included = bool((row.get("text") or "").strip())
        if not included:
            excluded_by_rating[r] += 1
        elif len(first_included) < 100:
            first_included.append(i)
        if i < 200:
            src_rows[i] = row

print("== selection / source integrity")
ids = [p["review_id"] for p in preds]
check("n rows", len(preds), 100)
check("review_ids unique", len(set(ids)), 100)
check("review_ids == first 100 included ids", ids, first_included)
check("run_meta dataset_row_count", meta["dataset_row_count"], total)
check("run_meta n_rows", meta["n_rows"], len(preds))
for p in preds:
    s = src_rows[p["review_id"]]
    if p["rating"] != s["rating"] or p["title"] != s["title"] or p["text"] != s["text"]:
        FAILS.append(f"row {p['review_id']} differs from source")
        print("FAIL row", p["review_id"], "differs from source")

print("== truth re-derived from source rating (>=4 POSITIVE else NEGATIVE)")
truth = {p["review_id"]: ("POSITIVE" if src_rows[p["review_id"]]["rating"] >= 4 else "NEGATIVE") for p in preds}
check("stored truth == re-derived truth (mismatch count)", sum(p["truth"] != truth[p["review_id"]] for p in preds), 0)

print("== prediction re-parsed from raw_responses (own strict parser)")
def my_parse(raw):
    if not isinstance(raw, str):
        return None
    for line in reversed(raw.strip().splitlines()):
        line = line.strip().strip("`").strip()
        m = re.fullmatch(r"LABEL=(POSITIVE|NEGATIVE)", line)
        if m:
            return m.group(1)
    return None
pred = {}
for p in preds:
    parsed = my_parse(p["raw_responses"][-1]) if p["raw_responses"] else None
    pred[p["review_id"]] = parsed or "UNPARSED"
check("stored prediction == re-parsed (mismatch count)", sum(p["prediction"] != pred[p["review_id"]] for p in preds), 0)
check("raw responses exactly 'LABEL=X' (non-exact count)", sum(p["raw_responses"] != [f"LABEL={p['prediction']}"] for p in preds), 0)

print("== metrics.json recomputation")
L, C = ["POSITIVE", "NEGATIVE"], ["POSITIVE", "NEGATIVE", "UNPARSED"]
n = len(preds)
cm = {t: {c: sum(1 for i in ids if truth[i] == t and pred[i] == c) for c in C} for t in L}
tc = {t: sum(cm[t].values()) for t in L}
pc = {c: sum(cm[t][c] for t in L) for c in C}
correct = sum(cm[t][t] for t in L)
check("n_rows", metrics["n_rows"], n)
check("correct", metrics["correct"], correct)
check("incorrect", metrics["incorrect"], n - correct)
check("accuracy", metrics["accuracy"], correct / n)
check("truth counts", metrics["truth_distribution"]["counts"], tc)
for t in L:
    check(f"truth share {t}", metrics["truth_distribution"]["share"][t], tc[t] / n)
check("prediction counts", metrics["prediction_distribution"]["counts"], pc)
for c in C:
    check(f"prediction share {c}", metrics["prediction_distribution"]["share"][c], pc[c] / n)
maj = max(L, key=lambda t: tc[t])
check("majority_class", metrics["majority_class"], maj)
check("majority_baseline_accuracy", metrics["majority_baseline_accuracy"], tc[maj] / n)
check("accuracy_minus_majority_baseline", metrics["accuracy_minus_majority_baseline"], correct / n - tc[maj] / n)
rec = {t: cm[t][t] / tc[t] for t in L}
prec = {t: cm[t][t] / pc[t] for t in L}
f1 = {t: 2 * prec[t] * rec[t] / (prec[t] + rec[t]) for t in L}
check("balanced_accuracy", metrics["balanced_accuracy"], sum(rec.values()) / 2)
check("majority_baseline_balanced_accuracy", metrics["majority_baseline_balanced_accuracy"], 0.5)
check("macro_f1", metrics["macro_f1"], sum(f1.values()) / 2)
for t in L:
    pcm = metrics["per_class"][t]
    check(f"{t} support", pcm["support"], tc[t])
    check(f"{t} predicted", pcm["predicted"], pc[t])
    check(f"{t} correct", pcm["correct"], cm[t][t])
    check(f"{t} wrong", pcm["wrong"], tc[t] - cm[t][t])
    check(f"{t} precision", pcm["precision"], prec[t])
    check(f"{t} precision_undefined flag", pcm["precision_undefined_never_predicted"], pc[t] == 0)
    check(f"{t} recall", pcm["recall"], rec[t])
    check(f"{t} f1", pcm["f1"], f1[t])
check("confusion rows", metrics["confusion_matrix"]["rows"], L)
check("confusion columns", metrics["confusion_matrix"]["columns"], C)
check("confusion counts", metrics["confusion_matrix"]["counts"], [[cm[t][c] for c in C] for t in L])
for t in L:
    for c in C:
        check(f"cell {t}->{c}", metrics["confusion_cells"][f"{t}->{c}"], cm[t][c])
        check(f"row share {t}->{c}", metrics["confusion_row_share"][f"{t}->{c}"], cm[t][c] / tc[t])
wrong = {f"{t}->{c}": [i for i in ids if truth[i] == t and pred[i] == c] for t in L for c in C if t != c and cm[t][c]}
check("misclassified_review_ids", metrics["misclassified_review_ids"], wrong)
check("parse_fail_count", metrics["parse_fail_count"], sum(p["parse_status"] == "FAIL" for p in preds))
check("api_error_count", metrics["api_error_count"], sum(p["parse_status"] == "API_ERROR" for p in preds))
check("unparsed_count", metrics["unparsed_count"], pc["UNPARSED"])
check("unparsed_share", metrics["unparsed_share"], pc["UNPARSED"] / n)
check("rows_needing_retry", metrics["rows_needing_retry"], sum(len(p["raw_responses"]) > 1 for p in preds))
extra_keys = set(metrics) - {"run", "label_scheme", "labels", "confusion_matrix_orientation", "n_rows", "correct",
    "incorrect", "accuracy", "truth_distribution", "prediction_distribution", "majority_class",
    "majority_baseline_accuracy", "accuracy_minus_majority_baseline", "balanced_accuracy",
    "majority_baseline_balanced_accuracy", "macro_f1", "per_class", "confusion_matrix", "confusion_cells",
    "confusion_row_share", "misclassified_review_ids", "parse_fail_count", "api_error_count",
    "unparsed_count", "unparsed_share", "rows_needing_retry"}
check("metrics.json keys not covered by this audit", sorted(extra_keys), [])

print("== run_meta.json")
check("run_meta parse_fail_count", meta["parse_fail_count"], metrics["parse_fail_count"])
check("run_meta api_error_count", meta["api_error_count"], metrics["api_error_count"])
check("run_meta rows_needing_retry", meta["rows_needing_retry"], metrics["rows_needing_retry"])
from_cache = sum(p["from_cache"] for p in preds)
check("run_meta cache_hits == rows from_cache", meta["cache_hits"], from_cache)
check("run_meta api_call_count == rows not from cache (0 retries)", meta["api_call_count"], n - from_cache)

print("== rating_distribution.json (recomputed from full file)")
check("row_count", dist["row_count"], total)
check("rating_counts", {int(k): v for k, v in dist["rating_counts"].items()}, dict(rating_counts))
for k, v in dist["rating_pct"].items():
    check(f"rating_pct {k}", v, round(100 * rating_counts[int(k)] / total, 4), tol=5e-5)
check("rows_failing_inclusion", dist["rows_failing_inclusion"], sum(excluded_by_rating.values()))
check("rows_failing_inclusion_by_rating", {int(k): v for k, v in dist["rows_failing_inclusion_by_rating"].items()},
      {k: excluded_by_rating.get(k, 0) for k in range(1, 6)})

print("== claims in reviews/step2_analysis.md and ISSUES.md")
check("rounded accuracy 97.0", round(100 * correct / n, 1), 97.0)
check("baseline 93.0", round(100 * tc[maj] / n, 1), 93.0)
check("gain +4.0 pp", round(100 * (correct - tc[maj]) / n, 1), 4.0)
check("balanced acc 91.8 / 0.9178", round(100 * sum(rec.values()) / 2, 1), 91.8)
check("POSITIVE recall 91/93=97.8", (cm["POSITIVE"]["POSITIVE"], tc["POSITIVE"], round(100 * rec["POSITIVE"], 1)), (91, 93, 97.8))
check("POSITIVE precision 91/92=98.9", (cm["POSITIVE"]["POSITIVE"], pc["POSITIVE"], round(100 * prec["POSITIVE"], 1)), (91, 92, 98.9))
check("NEGATIVE recall 6/7=85.7", (cm["NEGATIVE"]["NEGATIVE"], tc["NEGATIVE"], round(100 * rec["NEGATIVE"], 1)), (6, 7, 85.7))
check("NEGATIVE precision 6/8=75.0", (cm["NEGATIVE"]["NEGATIVE"], pc["NEGATIVE"], round(100 * prec["NEGATIVE"], 1)), (6, 8, 75.0))
check("NEGATIVE F1 0.800", round(f1["NEGATIVE"], 3), 0.8)
check("one review moves NEGATIVE recall 14.3 pts", round(100 / tc["NEGATIVE"], 1), 14.3)
by_id = {p["review_id"]: p for p in preds}
for rid, exp_rating, exp_truth, exp_pred in [(17, 5, "POSITIVE", "NEGATIVE"), (46, 5, "POSITIVE", "NEGATIVE"), (98, 3, "NEGATIVE", "POSITIVE")]:
    p = by_id[rid]
    check(f"id {rid} rating/truth/pred", (int(p["rating"]), truth[rid], pred[rid]), (exp_rating, exp_truth, exp_pred))
check("id 17 title", by_id[17]["title"], "No note attached to sent gift card")
print("     id 17 text:", repr(by_id[17]["text"]))
check("id 46 title/text", (by_id[46]["title"], by_id[46]["text"]), ("Love it!!", "This is an online gift card nothing to show sorry\U0001f92a"))
check("id 98 title/text", (by_id[98]["title"], by_id[98]["text"]), ("Easy to use", "Very easy to use. I wish I knew about it earlier"))
low = sorted(i for i in ids if by_id[i]["rating"] <= 2)
check("1-2 star ids in batch", low, [4, 15, 32, 51, 63])
check("1-2 star all predicted NEGATIVE", [pred[i] for i in low], ["NEGATIVE"] * 5)
three = sorted(i for i in ids if by_id[i]["rating"] == 3)
check("3 star ids in batch", three, [91, 98])
check("3 star preds (91, 98)", [pred[i] for i in three], ["NEGATIVE", "POSITIVE"])
groups = {}
for i in ids:
    groups.setdefault((by_id[i]["title"], by_id[i]["text"]), []).append(i)
dups = {k: v for k, v in groups.items() if len(v) > 1}
print("     duplicate (title,text) groups:", dups)
check("'Good Product' ids", groups.get(("Good Product", "Good Product")), [20, 21, 22, 23, 24, 27, 28])
check("'Good product' ids", groups.get(("Good product", "Good product")), [25, 26])
check("rows in duplicate groups (ISSUES: '9 of the 100')", sum(len(v) for v in dups.values()), 9)
check("rows that are repeats of an earlier row", sum(len(v) - 1 for v in dups.values()), 7)
check("cache hits = 3 preview (ids 0-2) + 7 repeats", sorted(i for i in ids if by_id[i]["from_cache"]),
      sorted([0, 1, 2] + [i for v in dups.values() for i in v[1:]]))
check("ISSUES Step 0: file share POSITIVE ~88.5%", round(100 * (rating_counts[4] + rating_counts[5]) / total, 1), 88.5)

print()
print(f"TOTAL FAILS: {len(FAILS)}", FAILS)
