"""Write runs/comparisons.json: named cross-run numbers for the report to cite.

Every value is read from a run's metrics.json (or emotion_metrics.json) or is a simple
difference of two such values, so each number the README quotes has a field to point to.

Usage: python src/compare_runs.py
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"


def load(run, name="metrics.json"):
    path = RUNS / run / name
    return json.loads(path.read_text()) if path.exists() else None


def wilson95(k, n):
    """Wilson score 95% interval for a proportion k/n: how much a fresh sample of the same size could move it."""
    z = 1.959963984540054
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [(centre - half) / denom, (centre + half) / denom]


def main():
    v1, v3_first, v3_bal = load("first100_v1"), load("first100_v3"), load("balanced150_v3")
    e_v2, e_first, e_bal = (load(r, "emotion_metrics.json") for r in ("first100_v2", "first100_v3", "balanced150_v3"))

    def margin(m):
        return m["accuracy"] - m["majority_baseline_accuracy"]

    out = {
        "note": "Rates are fractions in [0, 1]; *_minus_* fields are differences of fractions (display as points).",
        "sources": ["runs/first100_v1/metrics.json", "runs/first100_v3/metrics.json", "runs/balanced150_v3/metrics.json",
                    "runs/first100_v2/emotion_metrics.json", "runs/first100_v3/emotion_metrics.json",
                    "runs/balanced150_v3/emotion_metrics.json"],

        # Q1, part 1: the lopsided binary run as originally scored.
        "first100_v1_accuracy": v1["accuracy"],
        "first100_v1_majority_baseline": v1["majority_baseline_accuracy"],
        "first100_v1_margin_over_baseline": margin(v1),
        "first100_v1_negative_support": v1["per_class"]["NEGATIVE"]["support"],

        # Q1, part 2: same prompt (v3), only the sampling changes.
        "first100_v3_accuracy": v3_first["accuracy"],
        "balanced150_v3_accuracy": v3_bal["accuracy"],
        "accuracy_balanced150_v3_minus_first100_v3": v3_bal["accuracy"] - v3_first["accuracy"],
        "first100_v3_majority_baseline": v3_first["majority_baseline_accuracy"],
        "balanced150_v3_majority_baseline": v3_bal["majority_baseline_accuracy"],
        "first100_v3_margin_over_baseline": margin(v3_first),
        "balanced150_v3_margin_over_baseline": margin(v3_bal),
        "first100_v3_balanced_accuracy": v3_first["balanced_accuracy"],
        "balanced150_v3_balanced_accuracy": v3_bal["balanced_accuracy"],
        "first100_v3_macro_f1": v3_first["macro_f1"],
        "balanced150_v3_macro_f1": v3_bal["macro_f1"],
        "first100_v3_truth_counts": v3_first["truth_distribution"]["counts"],
        "balanced150_v3_truth_counts": v3_bal["truth_distribution"]["counts"],
        "first100_v3_recall": {k: v["recall"] for k, v in v3_first["per_class"].items()},
        "balanced150_v3_recall": {k: v["recall"] for k, v in v3_bal["per_class"].items()},

        # Q2: where 3-star (NEUTRAL) reviews go on the balanced run, and the reverse direction.
        "balanced150_v3_neutral_to_neutral": v3_bal["confusion_cells"]["NEUTRAL->NEUTRAL"],
        "balanced150_v3_neutral_to_negative": v3_bal["confusion_cells"]["NEUTRAL->NEGATIVE"],
        "balanced150_v3_neutral_to_positive": v3_bal["confusion_cells"]["NEUTRAL->POSITIVE"],
        "balanced150_v3_negative_to_neutral": v3_bal["confusion_cells"]["NEGATIVE->NEUTRAL"],
        "balanced150_v3_positive_to_neutral": v3_bal["confusion_cells"]["POSITIVE->NEUTRAL"],
        "balanced150_v3_negative_to_positive": v3_bal["confusion_cells"]["NEGATIVE->POSITIVE"],
        "balanced150_v3_positive_to_negative": v3_bal["confusion_cells"]["POSITIVE->NEGATIVE"],
        "balanced150_v3_neutral_to_negative_share": v3_bal["confusion_row_share"]["NEUTRAL->NEGATIVE"],
        "balanced150_v3_neutral_to_positive_share": v3_bal["confusion_row_share"]["NEUTRAL->POSITIVE"],
        "balanced150_v3_neutral_recall": v3_bal["per_class"]["NEUTRAL"]["recall"],
        "balanced150_v3_neutral_precision": v3_bal["per_class"]["NEUTRAL"]["precision"],
        "balanced150_v3_negative_precision": v3_bal["per_class"]["NEGATIVE"]["precision"],
        "balanced150_v3_predicted_negative": v3_bal["prediction_distribution"]["counts"]["NEGATIVE"],
        "balanced150_v3_neutral_errors_to_negative_minus_negative_errors_to_neutral":
            v3_bal["confusion_cells"]["NEUTRAL->NEGATIVE"] - v3_bal["confusion_cells"]["NEGATIVE->NEUTRAL"],
    }
    off = {c: v3_bal["confusion_cells"][f"NEUTRAL->{c}"] for c in ("POSITIVE", "NEGATIVE", "UNPARSED")}
    out["balanced150_v3_neutral_main_destination"] = max(off, key=off.get)

    # Addition: sampling uncertainty (Wilson 95%) for the proportions the conclusions rest on.
    neutral_n = v3_bal["per_class"]["NEUTRAL"]["support"]
    out["interval_method"] = "Wilson score 95% interval, [low, high] as fractions"
    out["first100_v1_accuracy_wilson95"] = wilson95(v1["correct"], v1["n_rows"])
    out["first100_v3_accuracy_wilson95"] = wilson95(v3_first["correct"], v3_first["n_rows"])
    out["balanced150_v3_accuracy_wilson95"] = wilson95(v3_bal["correct"], v3_bal["n_rows"])
    out["balanced150_v3_neutral_recall_wilson95"] = wilson95(v3_bal["per_class"]["NEUTRAL"]["correct"], neutral_n)
    out["balanced150_v3_neutral_to_negative_share_wilson95"] = wilson95(v3_bal["confusion_cells"]["NEUTRAL->NEGATIVE"], neutral_n)
    out["balanced150_v3_neutral_to_positive_share_wilson95"] = wilson95(v3_bal["confusion_cells"]["NEUTRAL->POSITIVE"], neutral_n)

    # Addition: what the balanced run's per-class behaviour would mean on the file's real class mix.
    # Precision and plain accuracy on a 50/50/50 sample reflect the forced mix; re-weighting each
    # truth row's prediction shares by the class pool sizes gives a rough whole-file estimate.
    # Rough: off-diagonal cells are small counts, and the POSITIVE draw contains no 4-star reviews.
    sample = json.loads((RUNS / "balanced150_v3" / "sample_ids.json").read_text())
    pools = sample["selection_info"]["pool_size_by_class"]
    total = sum(pools.values())
    weights = {c: pools[c] / total for c in pools}
    labels = v3_bal["labels"]
    joint = {(t, p): weights[t] * v3_bal["confusion_row_share"][f"{t}->{p}"] for t in labels for p in labels}
    predicted_mass = {p: sum(joint[(t, p)] for t in labels) for p in labels}
    out["population_pool_sizes"] = pools
    out["population_weights"] = weights
    out["population_weighting_note"] = ("balanced150_v3 row shares weighted by the included-row pool size of each "
                                        "three-class truth label in the whole file; rough estimate, see analysis")
    out["balanced150_v3_population_weighted_accuracy"] = sum(joint[(t, t)] for t in labels)
    out["balanced150_v3_population_weighted_precision"] = {p: joint[(p, p)] / predicted_mass[p] for p in labels}
    out["balanced150_v3_population_weighted_share_of_negative_predictions_from_neutral"] = (
        joint[("NEUTRAL", "NEGATIVE")] / predicted_mass["NEGATIVE"])
    out["balanced150_v3_population_weighted_share_of_neutral_predictions_from_positive"] = (
        joint[("POSITIVE", "NEUTRAL")] / predicted_mass["NEUTRAL"])
    out["balanced150_v3_share_of_negative_predictions_from_neutral"] = (
        v3_bal["confusion_cells"]["NEUTRAL->NEGATIVE"] / v3_bal["prediction_distribution"]["counts"]["NEGATIVE"])
    out["balanced_accuracy_balanced150_v3_minus_first100_v3"] = v3_bal["balanced_accuracy"] - v3_first["balanced_accuracy"]
    # Q1 cross-check: the balanced run's per-class recalls applied to batch_100's class counts predict
    # batch_100's accuracy; if that matches, the accuracy gap is the class mix rather than the model.
    first_support = {k: v["support"] for k, v in v3_first["per_class"].items()}
    out["first100_v3_accuracy_expected_from_balanced150_v3_recalls"] = (
        sum(first_support[k] * v3_bal["per_class"][k]["recall"] for k in first_support) / v3_first["n_rows"])
    # Fragility of batch_100's balanced accuracy: its NEUTRAL recall rests on 2 reviews.
    neu = v3_first["per_class"]["NEUTRAL"]
    out["first100_v3_neutral_support"] = neu["support"]
    out["first100_v3_balanced_accuracy_if_one_more_neutral_right"] = (
        sum(v3_first["per_class"][k]["recall"] for k in first_support if k != "NEUTRAL")
        + (neu["correct"] + 1) / neu["support"]) / len(first_support)

    # Addition: sensitivity of the re-weighted accuracy to Positive recall, which carries 88.5% of the weight.
    pos = v3_bal["per_class"]["POSITIVE"]
    out["balanced150_v3_positive_recall_wilson95"] = wilson95(pos["correct"], pos["support"])
    out["balanced150_v3_population_weighted_accuracy_at_positive_recall_low"] = (
        weights["POSITIVE"] * out["balanced150_v3_positive_recall_wilson95"][0]
        + sum(weights[k] * v3_bal["per_class"][k]["recall"] for k in labels if k != "POSITIVE"))
    out["interval_confidence"] = 0.95

    # Addition: is each run's gain over "always answer the majority class" distinguishable from chance?
    # Discordant reviews: model right where the shortcut is wrong, and the reverse; exact McNemar test.
    for run in ("first100_v1", "first100_v2", "first100_v3", "balanced150_v3"):
        m = load(run)
        rows = [json.loads(line) for line in open(RUNS / run / "predictions.jsonl", encoding="utf-8")]
        majority = m["majority_class"]
        model_only = sum(r["prediction"] == r["truth"] and r["truth"] != majority for r in rows)
        shortcut_only = sum(r["prediction"] != r["truth"] and r["truth"] == majority for r in rows)
        n, k = model_only + shortcut_only, min(model_only, shortcut_only)
        p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0
        out[f"{run}_vs_majority_class"] = majority
        out[f"{run}_vs_majority_model_only_right"] = model_only
        out[f"{run}_vs_majority_shortcut_only_right"] = shortcut_only
        out[f"{run}_vs_majority_exact_mcnemar_p"] = p

    # Q3: emotion agreement beside the constant-answer baseline, per run that has emotions.
    for run, em in (("first100_v2", e_v2), ("first100_v3", e_first), ("balanced150_v3", e_bal)):
        if em is None:
            continue
        out[f"{run}_emotion_agreement_all_rows"] = em["agreement_rate_all_rows"]
        out[f"{run}_emotion_agreement_excluding_none_and_tie"] = em["agreement_rate_excluding_none_and_tie"]
        out[f"{run}_emotion_constant_baseline_emotion"] = em["constant_baseline_emotion"]
        out[f"{run}_emotion_constant_baseline_all_rows"] = em["constant_baseline_rate_all_rows"]
        out[f"{run}_emotion_llm_minus_constant_all_rows"] = em["llm_minus_constant_rate_all_rows"]
        out[f"{run}_emotion_llm_minus_constant_excluding_none_and_tie"] = em["llm_minus_constant_rate_excluding_none_and_tie"]
        out[f"{run}_emotion_best_constant_emotion"] = em["best_constant_baseline_emotion"]
        out[f"{run}_emotion_best_constant_all_rows"] = em["best_constant_baseline_rate_all_rows"]
        out[f"{run}_emotion_best_constant_excluding_none_and_tie"] = em["best_constant_baseline_rate_excluding_none_and_tie"]
        out[f"{run}_emotion_llm_minus_best_constant_all_rows"] = em["llm_minus_best_constant_rate_all_rows"]
        out[f"{run}_emotion_llm_minus_best_constant_excluding_none_and_tie"] = em["llm_minus_best_constant_rate_excluding_none_and_tie"]

    (RUNS / "comparisons.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
