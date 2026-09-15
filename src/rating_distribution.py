"""Regenerate runs/rating_distribution.json: the star-rating distribution of the whole file.

Step 0 produced this file with an inline script; this is the committed generator. Existing
fields are reproduced exactly (the script refuses to write if any of them would change), and
`rating_share` (fractions of all rows) is added for the dashboard's display rule.

Usage: python src/rating_distribution.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load_data as ld  # noqa: E402

OUT = ld.ROOT / "runs" / "rating_distribution.json"


def main():
    ratings, failing = Counter(), Counter()
    n = 0
    for _, row in ld.iter_rows():
        n += 1
        r = int(row["rating"])
        ratings[r] += 1
        if not ld.is_included(row):
            failing[r] += 1
    stars = sorted(ratings)
    out = {
        "source_file": ld.DATA_PATH.name,
        "row_count": n,
        "rating_counts": {str(s): ratings[s] for s in stars},
        "rating_pct": {str(s): round(100 * ratings[s] / n, 4) for s in stars},
        "inclusion_rule": ld.INCLUSION_RULE,
        "rows_failing_inclusion": sum(failing.values()),
        "rows_failing_inclusion_by_rating": {str(s): failing[s] for s in sorted(failing)},
        "rating_share": {str(s): ratings[s] / n for s in stars},
    }
    if OUT.exists():
        old = json.loads(OUT.read_text())
        changed = [k for k in old if k != "rating_share" and old[k] != out.get(k)]
        if changed:
            raise SystemExit(f"refusing to write: existing fields would change: {changed}")
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
