"""Compute runs/<run>/metrics.json from predictions.jsonl and run_meta.json.

Rates are stored as fractions in [0, 1]; displays multiply by 100 and show one decimal.
Confusion matrix: rows = truth, columns = predicted; UNPARSED (FAIL or API_ERROR) is
its own column and always counts as wrong.

Usage: python src/score.py runs/first100_v1 [runs/... ...]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNPARSED = "UNPARSED"


def ratio(a, b):
    return a / b if b else None


def score_run(run_dir):
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run_meta.json").read_text())
    preds = [json.loads(line) for line in open(run_dir / "predictions.jsonl", encoding="utf-8")]
    labels = meta["labels"]
    columns = labels + [UNPARSED]
    n = len(preds)

    cm = {t: {c: 0 for c in columns} for t in labels}
    for p in preds:
        cm[p["truth"]][p["prediction"]] += 1
    truth_counts = {t: sum(cm[t].values()) for t in labels}
    pred_counts = {c: sum(cm[t][c] for t in labels) for c in columns}
    correct = sum(cm[t][t] for t in labels)

    per_class = {}
    for t in labels:
        tp = cm[t][t]
        precision, recall = ratio(tp, pred_counts[t]), ratio(tp, truth_counts[t])
        f1 = 2 * precision * recall / (precision + recall) if precision and recall else 0.0
        per_class[t] = {
            "support": truth_counts[t], "predicted": pred_counts[t], "correct": tp,
            "wrong": truth_counts[t] - tp,
            "precision": precision if precision is not None else 0.0,
            "precision_undefined_never_predicted": precision is None,
            "recall": recall, "f1": f1,
        }

    # Majority-class baseline: always answer the most common truth class of this sample.
    majority = max(labels, key=lambda t: (truth_counts[t], -labels.index(t)))
    accuracy = correct / n
    baseline = truth_counts[majority] / n
    recalls = [per_class[t]["recall"] for t in labels if per_class[t]["recall"] is not None]

    cells = {f"{t}->{c}": cm[t][c] for t in labels for c in columns}
    row_share = {f"{t}->{c}": ratio(cm[t][c], truth_counts[t]) for t in labels for c in columns}
    wrong_ids = {f"{t}->{c}": [p["review_id"] for p in preds if p["truth"] == t and p["prediction"] == c]
                 for t in labels for c in columns if t != c and cm[t][c]}

    metrics = {
        "run": meta["run"],
        "label_scheme": meta["label_scheme"],
        "labels": labels,
        "confusion_matrix_orientation": "rows = truth (from rating), columns = predicted",
        "n_rows": n,
        "correct": correct,
        "incorrect": n - correct,
        "accuracy": accuracy,
        "truth_distribution": {"counts": truth_counts, "share": {t: truth_counts[t] / n for t in labels}},
        "prediction_distribution": {"counts": pred_counts, "share": {c: pred_counts[c] / n for c in columns}},
        "majority_class": majority,
        "majority_baseline_accuracy": baseline,
        "accuracy_minus_majority_baseline": accuracy - baseline,
        "balanced_accuracy": sum(recalls) / len(recalls),
        "majority_baseline_balanced_accuracy": 1 / len(labels),
        "macro_f1": sum(per_class[t]["f1"] for t in labels) / len(labels),
        "per_class": per_class,
        "confusion_matrix": {"rows": labels, "columns": columns, "counts": [[cm[t][c] for c in columns] for t in labels]},
        "confusion_cells": cells,
        "confusion_row_share": row_share,
        "misclassified_review_ids": wrong_ids,
        "parse_fail_count": sum(p["parse_status"] == "FAIL" for p in preds),
        "api_error_count": sum(p["parse_status"] == "API_ERROR" for p in preds),
        "unparsed_count": pred_counts[UNPARSED],
        "unparsed_share": pred_counts[UNPARSED] / n,
        "rows_needing_retry": sum(len(p["raw_responses"]) > 1 for p in preds),
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    for d in sys.argv[1:]:
        m = score_run(d)
        print(f"{m['run']}: accuracy {100 * m['accuracy']:.1f}% ({m['correct']}/{m['n_rows']}); "
              f"majority baseline {100 * m['majority_baseline_accuracy']:.1f}% ({m['majority_class']}); "
              f"balanced accuracy {100 * m['balanced_accuracy']:.1f}%; unparsed {m['unparsed_count']}")
        print("  truth counts:", m["truth_distribution"]["counts"], "| predicted counts:", m["prediction_distribution"]["counts"])
        print("  confusion (rows=truth):", m["confusion_cells"])
