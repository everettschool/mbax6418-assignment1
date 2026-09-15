"""Verify dashboard/index.html in a real headless browser (Playwright Chromium).

For every run on the page:
  A. Metric numbers: every [data-metric][data-raw] element's data-source (file#field)
     resolves in that saved file, the file's value equals data-raw, and the visible
     text equals the display rule applied to that value.
  B. Chart marks: every [data-value] mark's value equals its field in the saved file,
     and any mark with value > 0 renders at >= 2px wide and >= 2px tall.
  C. Filters: for each filter and several combinations, the visible table rows are
     exactly the rows computed from predictions.jsonl, and the live count shows that
     number (text and data-live-count).
  D. Page health: no console errors, no non-file network requests, under 1 MB, and no
     untagged percentage outside the review table.

Usage: python src/verify_dashboard.py            (exit 1 on any failure)
"""
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "dashboard" / "index.html"
MIN_PX = 2
ENTITIES = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'", "nbsp": " "}

failures = []
checks = 0


def check(ok, message):
    global checks
    checks += 1
    if not ok:
        failures.append(message)
        print("  FAIL", message)


# ---------- display rules (mirror of FORMAT in dashboard/template.html) ----------
def js_fixed1(x):
    # Number.prototype.toFixed(1): exact binary value, ties go to the larger magnitude.
    return str(Decimal(x).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def display(value, fmt):
    if fmt == "pct":
        return js_fixed1(value * 100) + "%"
    if fmt == "count":
        return f"{int(Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP)):,}"
    if fmt == "pp":
        return ("−" if value < 0 else "+") + js_fixed1(abs(value * 100)) + " pts"
    if fmt == "text":
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    raise ValueError(fmt)


def display_text(s):
    # Mirror of displayText() in the template, used for search matching.
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)

    def sub(m):
        e = m.group(1)
        if e[0] != "#":
            return ENTITIES.get(e.lower(), m.group(0))
        try:
            return chr(int(e[2:], 16) if e[1].lower() == "x" else int(e[1:]))
        except (ValueError, OverflowError):
            return m.group(0)
    return re.sub(r"&(#x[0-9a-f]+|#\d+|[a-z]+);", sub, s, flags=re.IGNORECASE)


# ---------- saved files ----------
_files = {}


def load_file(rel):
    if rel not in _files:
        _files[rel] = json.loads((ROOT / rel).read_text())
    return _files[rel]


def resolve(source):
    rel, _, path = source.partition("#")
    value = load_file(rel)
    for key in path.split("."):
        value = value[key]
    return value


def mark_source(run, metric):
    """File#field for a chart mark (marks carry data-metric, not data-source)."""
    if run == "__file__":
        return f"runs/rating_distribution.json#{metric}"
    if metric.startswith("emotion."):
        return f"runs/{run}/emotion_metrics.json#{metric.removeprefix('emotion.')}"
    if metric.startswith("sample_rating."):
        return f"runs/{run}/metrics.json#{metric}"
    return f"runs/{run}/metrics.json#{metric}"


def predictions(run):
    return [json.loads(l) for l in open(ROOT / "runs" / run / "predictions.jsonl", encoding="utf-8")]


# ---------- checks ----------
def check_metrics(page, run):
    items = page.eval_on_selector_all("[data-metric][data-raw]", """els => els.map(e => ({
        metric: e.dataset.metric, raw: e.dataset.raw, source: e.dataset.source,
        format: e.dataset.format, run: e.dataset.run, text: e.textContent }))""")
    for it in items:
        where = f"[{run}] {it['source']}"
        try:
            value = resolve(it["source"])
        except (KeyError, FileNotFoundError, TypeError) as e:
            check(False, f"{where}: data-source does not resolve ({e!r})")
            continue
        check(it["source"].endswith("#" + it["metric"]), f"{where}: data-metric '{it['metric']}' is not the source field")
        check(json.loads(it["raw"]) == value, f"{where}: data-raw {it['raw']} != file value {value!r}")
        check(it["text"] == display(value, it["format"]),
              f"{where}: shows '{it['text']}', display rule gives '{display(value, it['format'])}'")
    return len(items)


def check_marks(page, run):
    marks = page.eval_on_selector_all("[data-value]", """els => els.map(e => {
        const r = e.getBoundingClientRect();
        return { run: e.dataset.run, metric: e.dataset.metric, value: e.dataset.value,
                 label: e.dataset.label, w: r.width, h: r.height }; })""")
    for mk in marks:
        where = f"[{run}] mark {mk['metric']} ({mk['label']})"
        check(all(mk[k] not in (None, "") for k in ("run", "metric", "value", "label")), f"{where}: missing data attribute")
        check(mk["run"] in (run, "__file__"), f"{where}: data-run '{mk['run']}' is not the selected run")
        try:
            saved = resolve(mark_source(mk["run"], mk["metric"]))
        except (KeyError, FileNotFoundError, TypeError) as e:
            check(False, f"{where}: no saved field ({e!r})")
            continue
        check(float(mk["value"]) == float(saved), f"{where}: data-value {mk['value']} != saved {saved}")
        if float(mk["value"]) > 0:
            check(mk["w"] >= MIN_PX and mk["h"] >= MIN_PX,
                  f"{where}: value {mk['value']} renders at {mk['w']:.2f}x{mk['h']:.2f}px (< {MIN_PX}px)")
    return len(marks)


def visible_ids(page):
    return page.eval_on_selector_all("#review-table tbody tr[data-review-id]",
                                     "els => els.filter(e => !e.hidden).map(e => Number(e.dataset.reviewId))")


def apply_filters(page, result="all", truth="all", pred="all", query=""):
    page.click("#f-reset")
    page.select_option("#f-result", result)
    page.select_option("#f-truth", truth)
    page.select_option("#f-pred", pred)
    page.fill("#f-search", query)


def expected_ids(rows, result="all", truth="all", pred="all", query=""):
    q = query.strip().lower()
    out = []
    for r in rows:
        ok = r["prediction"] == r["truth"]
        if result == "match" and not ok or result == "miss" and ok:
            continue
        if truth != "all" and r["truth"] != truth:
            continue
        if pred != "all" and r["prediction"] != pred:
            continue
        if q:
            hay = f"{r['title']}\n{r['text']}"
            if q not in hay.lower() and q not in display_text(hay).lower():
                continue
        out.append(r["review_id"])
    return out


def check_filters(page, run):
    rows = predictions(run)
    labels = load_file(f"runs/{run}/metrics.json")["labels"]
    columns = load_file(f"runs/{run}/metrics.json")["confusion_matrix"]["columns"]
    cases = [{}, {"result": "match"}, {"result": "miss"}]
    cases += [{"truth": t} for t in labels] + [{"pred": c} for c in columns]
    cases += [{"query": q} for q in ["gift", "SCAM", "  card ", "zzqqxx-no-match"]]
    cases += [
        {"result": "miss", "truth": labels[-1]},
        {"result": "match", "pred": labels[0]},
        {"truth": labels[0], "pred": labels[-1]},
        {"result": "miss", "query": "card"},
        {"truth": labels[-1], "pred": labels[-1], "query": "the"},
    ]
    if "NEUTRAL" in labels:
        cases += [{"truth": "NEUTRAL", "pred": "NEGATIVE"}, {"truth": "NEGATIVE", "pred": "NEUTRAL"},
                  {"truth": "NEUTRAL", "result": "miss"}]
    for case in cases:
        apply_filters(page, **case)
        want = expected_ids(rows, **case)
        got = visible_ids(page)
        shown = page.inner_text("#shown-count")
        live = page.get_attribute("#shown-count", "data-live-count")
        label = f"[{run}] filter {case or 'none'}"
        check(sorted(got) == sorted(want), f"{label}: visible ids {len(got)} != expected {len(want)}")
        check(shown == f"{len(want):,}", f"{label}: count text '{shown}' != {len(want):,}")
        check(live == str(len(want)), f"{label}: data-live-count {live} != {len(want)}")
        if not want:
            check(page.is_visible("#table-empty"), f"{label}: empty-state message not shown for 0 rows")
        print(f"  {label}: {len(want)} rows OK" if sorted(got) == sorted(want) and shown == f"{len(want):,}" else f"  {label}: see FAIL above")
    page.click("#f-reset")
    check(len(visible_ids(page)) == len(rows), f"[{run}] reset does not restore all {len(rows)} rows")
    return len(cases)


def check_untagged_percentages(page, run):
    found = page.evaluate("""() => {
        const out = [], walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        for (let n = walker.nextNode(); n; n = walker.nextNode()) {
          const p = n.parentElement;
          if (!p || p.closest("#review-table, script, style, .tip, [data-raw]")) continue;
          if (/\\d+(\\.\\d+)?\\s?%/.test(n.textContent)) out.push(n.textContent.trim());
        }
        return out; }""")
    check(not found, f"[{run}] untagged percentages on page: {found}")


def main():
    size = PAGE.stat().st_size
    check(size < 1_000_000, f"index.html is {size} bytes (>= 1 MB)")
    manifest = json.loads((ROOT / "dashboard" / "manifest.json").read_text())
    runs = [r["run"] for r in manifest["runs"]]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors, requests = [], []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: requests.append(r.url) if not r.url.startswith("file:") else None)
        page.goto(PAGE.as_uri())
        page.wait_for_load_state("load")
        print(f"browser: chromium {browser.version}; page {size:,} bytes; runs {runs}")
        for run in runs:
            page.click(f'[data-run-tab="{run}"]')
            check(page.get_attribute("body", "data-run") == run, f"tab click did not select {run}")
            n_metrics = check_metrics(page, run)
            n_marks = check_marks(page, run)
            print(f"[{run}] {n_metrics} metric numbers and {n_marks} chart marks checked")
            n_cases = check_filters(page, run)
            check_untagged_percentages(page, run)
            print(f"[{run}] {n_cases} filter cases checked")
        check(not errors, f"console errors: {errors}")
        check(not requests, f"non-file network requests: {requests}")
        browser.close()
    print(f"\n{checks} checks, {len(failures)} failures")
    print("PASS" if not failures else "FAIL")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
