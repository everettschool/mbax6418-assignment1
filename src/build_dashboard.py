"""Build dashboard/index.html from dashboard/template.html and saved run outputs.

Every number the page shows comes from files read here (metrics.json, run_meta.json,
predictions.jsonl, rating_distribution.json). The page formats them; it never
computes a published metric of its own. Output is one self-contained file.

Usage: python src/build_dashboard.py [dashboard/manifest.json]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "dashboard"
PLACEHOLDER = "__DASHBOARD_DATA__"
MAX_BYTES = 1_000_000

# Only these fields reach the page. No endpoint URL exists in any run file; the
# endpoint is recorded as the label "course-endpoint".
PRED_FIELDS = ["review_id", "title", "text", "rating", "truth", "prediction", "parse_status",
               "verified_purchase", "helpful_vote", "llm_emotion", "nrc_emotion", "nrc_tied",
               "nrc_hits", "emotion_agree"]
META_FIELDS = ["run", "model", "endpoint", "temperature", "max_tokens", "prompt_file", "prompt_sha256",
               "label_scheme", "labels", "seed", "selection", "selection_rule", "n_rows",
               "timestamp_utc", "api_call_count", "parse_fail_count", "api_error_count",
               "dataset_sha256", "dataset_row_count", "inclusion_rule"]


def rel(path):
    return str(path.relative_to(ROOT))


def load_run(entry):
    run_dir = ROOT / "runs" / entry["run"]
    metrics = json.loads((run_dir / "metrics.json").read_text())
    meta = json.loads((run_dir / "run_meta.json").read_text())
    rows = []
    for line in open(run_dir / "predictions.jsonl", encoding="utf-8"):
        p = json.loads(line)
        rows.append({k: p[k] for k in PRED_FIELDS if k in p})
    extras = {}
    for name in ["emotion_metrics.json"]:
        if (run_dir / name).exists():
            extras[name.removesuffix(".json")] = json.loads((run_dir / name).read_text())
    return {
        **entry,
        "sources": {"metrics": rel(run_dir / "metrics.json"), "meta": rel(run_dir / "run_meta.json"),
                    "predictions": rel(run_dir / "predictions.jsonl"),
                    **{k: rel(run_dir / f"{k}.json") for k in extras}},
        "metrics": metrics,
        "meta": {k: meta[k] for k in META_FIELDS if k in meta},
        "rows": rows,
        **extras,
    }


def build(manifest_path=DASH / "manifest.json"):
    manifest = json.loads(Path(manifest_path).read_text())
    dist_path = ROOT / "runs" / "rating_distribution.json"
    payload = {
        "title": manifest["title"],
        "rating_distribution": json.loads(dist_path.read_text()),
        "rating_distribution_source": rel(dist_path),
        "runs": [load_run(e) for e in manifest["runs"]],
    }
    # Tab labels are the only hand-written run text; hold them to the run's own files.
    scheme_words = {"binary": "two classes", "three": "three classes"}
    for run in payload["runs"]:
        meta, label = run["meta"], run["label"]
        numbers = [int(n) for n in re.findall(r"\d+", label)]
        if numbers and numbers[0] != meta["n_rows"]:
            raise SystemExit(f"label '{label}' says {numbers[0]} rows; run_meta n_rows is {meta['n_rows']}")
        if scheme_words[meta["label_scheme"]] not in label:
            raise SystemExit(f"label '{label}' does not say '{scheme_words[meta['label_scheme']]}'")
    template = (DASH / "template.html").read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise SystemExit(f"template must contain {PLACEHOLDER} exactly once")
    # Inline JSON inside <script type="application/json">: escape "</" so review text
    # can never close the script element.
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = template.replace(PLACEHOLDER, data)
    # The SVG namespace identifier is a name, not a request; any other URL is refused.
    scan = template.replace("http://www.w3.org/2000/svg", "")
    for forbidden in ["http://", "https://"]:
        if forbidden in scan:
            raise SystemExit(f"template contains {forbidden}; the page must make no network requests")
    out = DASH / "index.html"
    out.write_text(html, encoding="utf-8")
    size = out.stat().st_size
    if size >= MAX_BYTES:
        raise SystemExit(f"dashboard is {size} bytes, over the 1 MB cap")
    print(f"wrote {rel(out)}: {size} bytes, runs={[r['run'] for r in payload['runs']]}")


if __name__ == "__main__":
    build(*sys.argv[1:])
