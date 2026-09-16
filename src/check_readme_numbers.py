"""Check every cited number in README.md against the saved files.

Citations look like **73.3%** (balanced150_v3: accuracy). The source is:
  <run>: field            -> runs/<run>/metrics.json
  <run> emotions: field   -> runs/<run>/emotion_metrics.json
  comparisons: field      -> runs/comparisons.json
Percentages are the field value x100 to one decimal; "pts" values likewise with a sign;
anything else is compared as an integer.

Usage: python src/check_readme_numbers.py   (exit 1 on any mismatch)
"""
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CITATION = re.compile(r"\*\*(?P<value>[^*]+)\*\* \((?P<source>[a-z0-9_]+)(?P<emo> emotions)?: (?P<field>[A-Za-z0-9_.\->]+)\)")
_files = {}


def load(rel):
    if rel not in _files:
        _files[rel] = json.loads((ROOT / rel).read_text())
    return _files[rel]


def resolve(source, emotions, field):
    rel = "runs/comparisons.json" if source == "comparisons" else \
        f"runs/{source}/{'emotion_metrics' if emotions else 'metrics'}.json"
    value = load(rel)
    for key in field.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return rel, value


def fmt_pct(v):
    return str(Decimal(v * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) + "%"


def main():
    text = (ROOT / "README.md").read_text()
    failures, checked = [], 0
    for m in CITATION.finditer(text):
        shown, source, field = m["value"].strip(), m["source"], m["field"]
        if source != "comparisons" and not (ROOT / "runs" / source).is_dir():
            continue  # the citation-format example in the intro, not a citation
        rel, value = resolve(source, bool(m["emo"]), field)
        if shown.endswith("%"):
            expected = fmt_pct(value)
        elif shown.endswith("pts"):
            sign = "−" if value < 0 else "+"
            expected = sign + str(Decimal(abs(value) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) + " pts"
        else:
            expected = f"{int(value):,}"
        checked += 1
        if shown != expected:
            failures.append(f"README says {shown!r} for ({source}: {field}) but {rel} gives {expected!r}")
        else:
            print(f"OK  {shown:>10}  ({source}: {field})")

    # Percentages in the Q1-Q3 prose must repeat a value cited in the sources table.
    def norm(v):
        return v[:-3] + "%" if v.endswith(".0%") else v
    cited = {norm(m["value"].strip()) for m in CITATION.finditer(text)}
    prose = text[text.index("## Q1."):text.index("### Where these numbers come from")]
    for line in prose.splitlines():
        for pct in re.findall(r"\d+(?:\.\d+)?%", line):
            if norm(pct) not in cited:
                failures.append(f"README prose says {pct!r}, which is not cited in the sources table")

    print(f"\n{checked} citations checked, {len(failures)} problems")
    for f in failures:
        print("  FAIL", f)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
