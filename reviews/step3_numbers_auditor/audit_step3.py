"""Independent Step 3 numbers audit. Imports nothing from src/.

1. Recomputes every metric from runs/first100_v1/predictions.jsonl (truth from rating,
   prediction re-parsed from raw_responses) and compares every leaf of metrics.json.
2. Checks dashboard/index.html is a fresh build: embedded JSON == files on disk (own
   reimplementation of the payload), and the page shell == template.html.
3. Opens the built page in headless Chromium and, from the DOM:
   - every [data-metric] number: data-source resolves to the file value == data-raw ==
     recomputed value; visible text == display rule (pct 1 dp of fraction*100, integer counts);
   - every chart mark: has data-run/data-metric/data-value/data-label; value == recomputed;
     rendered size > 0;
   - confusion-matrix DOM order: rows = truth, columns = predicted;
   - review table rows == predictions (ids, rating, truth, prediction, correct flag);
   - digits in visible text outside metric spans / review table (untagged numbers).
Usage: .venv/bin/python reviews/step3_numbers_auditor/audit_step3.py
"""
import json
import math
import re
from collections import Counter
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
RUN = "first100_v1"
RUN_DIR = ROOT / "runs" / RUN
FAILS, NOTES = [], []


def same(a, b, tol=1e-12):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b or a == b and type(a) == type(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, abs_tol=tol)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


def check(name, got, expected, quiet=False):
    ok = same(got, expected)
    if not ok or not quiet:
        e, g = repr(expected), repr(got)
        if ok and len(e) > 160:  # identical long values: print once, truncated
            print(f"OK   {name}: identical ({len(e)} chars) {e[:100]}...")
        else:
            print(f"{'OK  ' if ok else 'FAIL'} {name}: expected={e} got={g}")
    if not ok:
        FAILS.append(name)
    return ok


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    else:
        out[prefix] = obj
    return out


# ------------------------------------------------------------------ 1. recompute
preds = [json.loads(l) for l in open(RUN_DIR / "predictions.jsonl", encoding="utf-8")]
metrics = json.loads((RUN_DIR / "metrics.json").read_text())
meta = json.loads((RUN_DIR / "run_meta.json").read_text())
dist = json.loads((ROOT / "runs" / "rating_distribution.json").read_text())


def parse(raw):
    if not isinstance(raw, str):
        return None
    for line in reversed(raw.strip().splitlines()):
        m = re.fullmatch(r"LABEL=(POSITIVE|NEGATIVE)", line.strip().strip("`").strip())
        if m:
            return m.group(1)
    return None


L = ["POSITIVE", "NEGATIVE"]
C = L + ["UNPARSED"]
n = len(preds)
ids = [p["review_id"] for p in preds]
truth = {p["review_id"]: "POSITIVE" if p["rating"] >= 4 else "NEGATIVE" for p in preds}
pred = {p["review_id"]: (parse(p["raw_responses"][-1]) if p["raw_responses"] else None) or "UNPARSED" for p in preds}
print("== 1. inputs")
check("rows", n, 100)
check("unique ids", len(set(ids)), n)
check("stored truth mismatches vs rating>=4 rule", sum(p["truth"] != truth[p["review_id"]] for p in preds), 0)
check("stored prediction mismatches vs re-parse", sum(p["prediction"] != pred[p["review_id"]] for p in preds), 0)

cm = {t: {c: sum(truth[i] == t and pred[i] == c for i in ids) for c in C} for t in L}
tc = {t: sum(cm[t].values()) for t in L}
pc = {c: sum(cm[t][c] for t in L) for c in C}
correct = sum(cm[t][t] for t in L)
rec = {t: cm[t][t] / tc[t] for t in L}
prec = {t: cm[t][t] / pc[t] if pc[t] else 0.0 for t in L}
f1 = {t: 2 * prec[t] * rec[t] / (prec[t] + rec[t]) if prec[t] and rec[t] else 0.0 for t in L}
maj = max(L, key=lambda t: (tc[t], -L.index(t)))
R = {
    "run": RUN, "label_scheme": "binary", "labels": L,
    "confusion_matrix_orientation": "rows = truth (from rating), columns = predicted",
    "n_rows": n, "correct": correct, "incorrect": n - correct, "accuracy": correct / n,
    "truth_distribution": {"counts": tc, "share": {t: tc[t] / n for t in L}},
    "prediction_distribution": {"counts": pc, "share": {c: pc[c] / n for c in C}},
    "majority_class": maj, "majority_baseline_accuracy": tc[maj] / n,
    "accuracy_minus_majority_baseline": correct / n - tc[maj] / n,
    "balanced_accuracy": sum(rec.values()) / len(L), "majority_baseline_balanced_accuracy": 1 / len(L),
    "macro_f1": sum(f1.values()) / len(L),
    "per_class": {t: {"support": tc[t], "predicted": pc[t], "correct": cm[t][t], "wrong": tc[t] - cm[t][t],
                      "precision": prec[t], "precision_undefined_never_predicted": pc[t] == 0,
                      "recall": rec[t], "f1": f1[t]} for t in L},
    "confusion_matrix": {"rows": L, "columns": C, "counts": [[cm[t][c] for c in C] for t in L]},
    "confusion_cells": {f"{t}->{c}": cm[t][c] for t in L for c in C},
    "confusion_row_share": {f"{t}->{c}": cm[t][c] / tc[t] for t in L for c in C},
    "misclassified_review_ids": {f"{t}->{c}": [i for i in ids if truth[i] == t and pred[i] == c]
                                 for t in L for c in C if t != c and cm[t][c]},
    "parse_fail_count": sum(p["parse_status"] == "FAIL" for p in preds),
    "api_error_count": sum(p["parse_status"] == "API_ERROR" for p in preds),
    "unparsed_count": pc["UNPARSED"], "unparsed_share": pc["UNPARSED"] / n,
    "rows_needing_retry": sum(len(p["raw_responses"]) > 1 for p in preds),
}
RF, MF = flatten(R), flatten(metrics)
print("== 1b. metrics.json vs recomputation (every leaf)")
check("metrics.json leaf paths == recomputed leaf paths", sorted(MF), sorted(RF))
leaf_fail = 0
for k in RF:
    if not check(f"metrics#{k}", MF.get(k), RF[k], quiet=True):
        leaf_fail += 1
print(f"     {len(RF)} leaves compared, {leaf_fail} mismatches")
check("run_meta n_rows", meta["n_rows"], n)
check("run_meta parse_fail_count", meta["parse_fail_count"], R["parse_fail_count"])
check("run_meta api_error_count", meta["api_error_count"], R["api_error_count"])
check("run_meta labels", meta["labels"], L)

# ------------------------------------------------------------------ 2. freshness of built page
print("== 2. index.html freshness")
html = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
template = (ROOT / "dashboard" / "template.html").read_text(encoding="utf-8")
mo = re.search(r'<script id="dashboard-data" type="application/json">(.*?)</script>', html, re.S)
embedded = json.loads(mo.group(1).replace("<\\/", "</"))
shell = html[:mo.start(1)] + "__DASHBOARD_DATA__" + html[mo.end(1):]
check("page shell == template.html", shell == template, True)
manifest = json.loads((ROOT / "dashboard" / "manifest.json").read_text())
check("embedded title == manifest", embedded["title"], manifest["title"])
check("embedded rating_distribution == file", embedded["rating_distribution"], dist)
check("embedded runs == manifest runs", [r["run"] for r in embedded["runs"]], [r["run"] for r in manifest["runs"]])
er = embedded["runs"][0]
check("embedded metrics == metrics.json", er["metrics"], metrics)
check("embedded meta values == run_meta.json", {k: meta[k] for k in er["meta"]}, er["meta"])
emb_rows = {r["review_id"]: r for r in er["rows"]}
row_mism = [p["review_id"] for p in preds if any(p.get(k) != v for k, v in emb_rows.get(p["review_id"], {"_": 1}).items())]
check("embedded rows == predictions.jsonl (mismatching ids)", row_mism, [])
check("embedded row count", len(er["rows"]), n)

# ------------------------------------------------------------------ 3. DOM
FILES = {f"runs/{RUN}/metrics.json": metrics, f"runs/{RUN}/run_meta.json": meta}


def getpath(obj, path):
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
    return str(v) if not isinstance(v, bool) else str(v).lower()


JS_WALK = r"""() => {
  const out = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const t = w.currentNode, p = t.parentElement;
    if (!/\d/.test(t.textContent)) continue;
    if (p.closest('[data-metric][data-raw]') || p.closest('#review-table') || p.closest('script') || p.closest('#tip')) continue;
    const cs = getComputedStyle(p); if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    out.push({text: t.textContent.trim(), where: (p.closest('[id]') || {}).id || p.tagName});
  }
  return out;
}"""

print("== 3. DOM (headless Chromium)")
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors, requests = [], []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: not r.url.startswith("file:") and not r.url.startswith("data:") and requests.append(r.url))
    page.goto((ROOT / "dashboard" / "index.html").resolve().as_uri())
    page.wait_for_selector("#review-table tbody tr")
    check("console/page errors", errors, [])
    check("non-file requests", requests, [])

    nums = page.eval_on_selector_all("[data-metric][data-raw]", """els => els.map(e => ({
        metric: e.dataset.metric, raw: e.dataset.raw, source: e.dataset.source, format: e.dataset.format,
        run: e.dataset.run, text: e.textContent, vis: e.getClientRects().length > 0}))""")
    print(f"     {len(nums)} tagged metric numbers")
    bad = 0
    for i, s in enumerate(nums):
        tag = f"num[{i}] {s['source']}"
        file_, _, field = (s["source"] or "").partition("#")
        ok = check(f"{tag}: data-metric == source field", s["metric"], field, quiet=True)
        ok &= check(f"{tag}: data-run", s["run"], RUN, quiet=True)
        ok &= check(f"{tag}: source file known", file_ in FILES, True, quiet=True)
        if file_ in FILES:
            fv = getpath(FILES[file_], field)
            raw = json.loads(s["raw"])
            ok &= check(f"{tag}: data-raw == file value", raw, fv, quiet=True)
            if file_.endswith("metrics.json"):
                ok &= check(f"{tag}: data-raw == recomputed", raw, RF.get(field, KeyError), quiet=True)
            ok &= check(f"{tag}: text == display rule ({s['format']})", s["text"], fmt(raw, s["format"]), quiet=True)
            if s["format"] == "pct":
                ok &= check(f"{tag}: pct is fraction*100 1dp", bool(re.fullmatch(r"\d{1,3}\.\d%", s["text"])), True, quiet=True)
            if s["format"] == "count":
                ok &= check(f"{tag}: count is integer", bool(re.fullmatch(r"[\d,]+", s["text"])), True, quiet=True)
        ok &= check(f"{tag}: visible", s["vis"], True, quiet=True)
        bad += not ok
    print(f"     metric numbers with any failure: {bad}")
    fmts = Counter(s["format"] for s in nums)
    print("     formats:", dict(fmts), "| distinct fields:", len({s["source"] for s in nums}))
    shown = {s["metric"] for s in nums if s["source"].startswith(f"runs/{RUN}/metrics.json")}
    print("     metrics.json fields shown on page:", sorted(shown))
    # numbers shown with data-metric but missing data-raw / data-source
    partial = page.eval_on_selector_all("[data-metric]:not([data-value])", "els => els.filter(e => !e.dataset.raw || !e.dataset.source).length")
    check("[data-metric] numbers missing data-raw/data-source", partial, 0)

    marks = page.eval_on_selector_all("[data-value]", """els => els.map(e => { const r = e.getBoundingClientRect();
        return {run: e.dataset.run, metric: e.dataset.metric, value: e.dataset.value, label: e.dataset.label,
                w: r.width, h: r.height, cls: e.className}; })""")
    print(f"     {len(marks)} chart marks")
    mbad = 0
    for i, mk in enumerate(marks):
        tag = f"mark[{i}] {mk['metric']}"
        ok = check(f"{tag}: has all attrs", all(mk[k] not in (None, "") for k in ("run", "metric", "value", "label")), True, quiet=True)
        ok &= check(f"{tag}: run", mk["run"], RUN, quiet=True)
        ok &= check(f"{tag}: value == recomputed", float(mk["value"]), float(RF.get(mk["metric"], float("nan"))), quiet=True)
        ok &= check(f"{tag}: value == metrics.json", float(mk["value"]), float(MF.get(mk["metric"], float("nan"))), quiet=True)
        if float(mk["value"]) > 0:
            ok &= check(f"{tag}: rendered w,h > 0", mk["w"] > 0 and mk["h"] > 0, True, quiet=True)
        mbad += not ok
    print(f"     chart marks with any failure: {mbad}")
    mm = Counter(m["metric"].split(".")[0] for m in marks)
    print("     marks by metric group:", dict(mm))
    # stacked-bar widths proportional to counts
    for key in ["truth_distribution", "prediction_distribution"]:
        segs = [m for m in marks if m["metric"].startswith(key + ".counts.")]
        tot_w = sum(s["w"] for s in segs)
        for s in segs:
            share = float(s["value"]) / n
            print(f"     {s['metric']}: width share {s['w'] / tot_w:.3f} vs count share {share:.3f}")

    # confusion orientation from DOM order
    cells = [m["metric"].split(".", 1)[1] for m in marks if m["metric"].startswith("confusion_cells.")]
    check("confusion cells DOM order (row-major, rows=truth, cols=pred)", cells, [f"{t}->{c}" for t in L for c in C])
    heads = page.eval_on_selector_all(".cm-colhead", "els => els.map(e => e.textContent.trim())")
    rheads = page.eval_on_selector_all(".cm-rowhead .chip", "els => els.map(e => e.textContent.trim())")
    check("confusion column headers (predicted)", heads, ["Positive", "Negative", "Unparsed"])
    check("confusion row headers (truth)", rheads, ["Positive", "Negative"])
    cols = page.eval_on_selector(".cm", "e => getComputedStyle(e).gridTemplateColumns.split(' ').length")
    check("confusion grid column count (header + 3)", cols, 4)
    cell_labels = [m["label"] for m in marks if m["metric"].startswith("confusion_cells.")]
    print("     cell labels:", cell_labels)

    # review table
    trs = page.eval_on_selector_all("#review-table tbody tr", """els => els.map(e => ({id: +e.dataset.reviewId,
        correct: e.dataset.correct, truth: e.dataset.truth, pred: e.dataset.prediction, miss: e.classList.contains('is-miss'),
        cells: [...e.children].map(td => td.textContent)}))""")
    check("table row count", len(trs), n)
    check("table ids in order", [t["id"] for t in trs], ids)
    tbad = []
    for t in trs:
        i = t["id"]; p = next(x for x in preds if x["review_id"] == i)
        exp_ok = truth[i] == pred[i]
        good = (t["truth"] == truth[i] and t["pred"] == pred[i] and t["correct"] == str(exp_ok).lower()
                and t["miss"] == (not exp_ok) and t["cells"][1] == f"{int(p['rating'])}★"
                and t["cells"][2] == truth[i].capitalize() and t["cells"][3] == pred[i].capitalize()
                and t["cells"][4].endswith("Match" if exp_ok else "Miss"))
        if not good:
            tbad.append((i, t["cells"][:5]))
    check("table rows disagreeing with recomputation", tbad, [])
    check("table Miss rows == recomputed incorrect", sum(t["miss"] for t in trs), n - correct)
    check("Miss ids", sorted(t["id"] for t in trs if t["miss"]), sorted(i for v in R["misclassified_review_ids"].values() for i in v))
    cl = page.eval_on_selector("#row-count", "e => ({text: e.textContent, live: e.dataset.liveCount, metric: e.dataset.metric || null, raw: e.dataset.raw || null, source: e.dataset.source || null})")
    print("     row-count element:", cl)
    check("row-count text", cl["text"], f"Showing {n} of {n} reviews")

    # headline sentence semantics
    weakest = sorted(L, key=lambda t: (rec[t], L.index(t)))[0]
    vl = page.inner_text(".verdict-line")
    print("     verdict-line:", vl)
    check("weakest class named", f"Weakest class: {weakest.capitalize()}" in vl, True)
    print("     verdict-head:", page.inner_text("#verdict-head"))
    print("     hero:", page.inner_text("#sec-verdict .verdict > div:first-child").replace("\n", " | "))
    print("     classes:", page.inner_text("#sec-classes").replace("\n", " | "))
    print("     blurb:", page.inner_text("#run-blurb"))

    loose = page.evaluate(JS_WALK)
    print("     visible text nodes with digits outside tagged metric spans and the review table:")
    for x in loose:
        print(f"       [{x['where']}] {x['text']!r}")
    browser.close()

print()
print(f"TOTAL FAILS: {len(FAILS)}", FAILS[:40])
