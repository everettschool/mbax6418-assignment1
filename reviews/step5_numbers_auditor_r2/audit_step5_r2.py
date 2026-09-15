"""Step 5 Numbers Auditor, round 2. Independent: imports nothing from src/.

Recomputes metrics.json (v1, v2), per-row NRC fields and emotion_metrics.json (v2) from
predictions.jsonl + the NRC lexicon; compares files, the rendered dashboard DOM (Playwright
headless Chromium, data-raw / data-value), and written claims in step5_analysis.md, ISSUES.md,
PROGRESS.md. Prints FAIL lines; exit code = number of FAILs (capped at 1).
"""
import hashlib
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"
FAILS = []


def fail(msg):
    FAILS.append(msg)
    print("FAIL", msg)


def check(desc, expected, got):
    if expected == got:
        s = repr(got)
        print(f"  OK   {desc}: {s if len(s) <= 300 else s[:120] + f' ...[{len(s)} chars, equal]'}")
    else:
        fail(f"{desc}: expected={expected!r} got={got!r}")


def load_rows(run):
    return [json.loads(l) for l in open(RUNS / run / "predictions.jsonl", encoding="utf-8")]


EMO = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]

# ---------------------------------------------------------------- 1. lexicon
print("== 1. lexicon")
lexfile = ROOT / "data/nrc/NRC-Emotion-Lexicon-Wordlevel.txt"
lexmeta = json.loads((RUNS / "nrc_lexicon_meta.json").read_text())
raw = lexfile.read_bytes()
check("lexicon sha256", lexmeta["lexicon_sha256"], hashlib.sha256(raw).hexdigest())
zipf = ROOT / "data/nrc/NRC-Emotion-Lexicon.zip"
if zipf.exists():
    check("zip sha256", lexmeta["zip_sha256"], hashlib.sha256(zipf.read_bytes()).hexdigest())
words, LEX, cols = set(), {}, set()
for line in raw.decode("utf-8").splitlines():
    p = line.split("\t")
    if len(p) != 3:
        continue
    w, c, f = p[0].strip(), p[1].strip(), p[2].strip()
    if f not in ("0", "1"):
        continue
    words.add(w)
    cols.add(c)
    if f == "1" and c in EMO:
        LEX.setdefault(w, set()).add(c)
check("word_count", lexmeta["word_count"], len(words))
check("words_with_any_of_8_emotions", lexmeta["words_with_any_of_8_emotions"], len(LEX))
check("columns_found", sorted(lexmeta["columns_found"]), sorted(cols))

# ---------------------------------------------------------------- 2. per-row
STAR = re.compile(r"^\s*(one|two|three|four|five)\s+stars?\s*$", re.I)
NEG = {"not", "no", "never", "nothing", "none", "nor", "without", "t"}


def blank(s):
    return "" if STAR.match(s) else s


def entry(tok):
    if tok in LEX:
        return tok
    for suf in ("ing", "ed", "es", "s"):
        if tok.endswith(suf) and tok[: -len(suf)] in LEX:
            return tok[: -len(suf)]
    return None


def nrc(title, text):
    t = blank(title) + " " + blank(text)
    t = html.unescape(re.sub(r"<br\s*/?>", " ", t, flags=re.I))
    toks = re.findall(r"[a-z]+", t.lower())
    sc = dict.fromkeys(EMO, 0)
    hits, negs = [], []
    for i, tok in enumerate(toks):
        e = entry(tok)
        if not e:
            continue
        for x in LEX[e]:
            sc[x] += 1
        hits.append([tok, e, [x for x in EMO if x in LEX[e]]])
        prev = [p for p in toks[max(0, i - 3):i] if p in NEG]
        if prev:
            negs.append([prev[-1], tok])
    top = max(sc.values())
    tied = [e for e in EMO if sc[e] == top] if top else []
    lab = "NONE" if not top else ("TIE" if len(tied) > 1 else tied[0])
    return dict(nrc_emotion=lab, nrc_tied=tied if lab == "TIE" else [], nrc_scores=sc, nrc_hits=hits,
                nrc_token_count=len(toks), nrc_emotion_tiebreak=tied[0] if tied else "NONE",
                nrc_negated_hits=negs, _tokens=toks)


def parse(raws, emotion):
    pat = (re.compile(r"^LABEL=(POSITIVE|NEGATIVE);EMOTION=(" + "|".join(EMO) + r")$") if emotion
           else re.compile(r"^LABEL=(POSITIVE|NEGATIVE)$"))
    raw = raws[-1] if raws else None
    if not isinstance(raw, str):
        return None, None
    for line in reversed(raw.strip().splitlines()):
        line = line.strip()
        if re.match(r"^`{3,}[a-zA-Z]*$", line):
            continue
        m = pat.match(line.strip("`").strip())
        if m:
            return m.group(1), (m.group(2) if emotion else None)
    return None, None


print("== 2. per-row fields")
V1, V2 = load_rows("first100_v1"), load_rows("first100_v2")
mism = Counter()
for run, rows, emo in (("v1", V1, False), ("v2", V2, True)):
    for r in rows:
        truth = "POSITIVE" if r["rating"] >= 4 else "NEGATIVE"
        lab, em = parse(r["raw_responses"], emo)
        if r["truth"] != truth: mism[f"{run}.truth"] += 1
        if r["prediction"] != (lab or "UNPARSED"): mism[f"{run}.prediction"] += 1
        if r.get("llm_emotion") != em: mism[f"{run}.llm_emotion"] += 1
for r in V2:
    mine = nrc(r["title"], r["text"])
    r["_mine"] = mine
    for k in ["nrc_emotion", "nrc_tied", "nrc_scores", "nrc_hits", "nrc_token_count", "nrc_emotion_tiebreak",
              "nrc_negated_hits"]:
        if r.get(k) != mine[k]:
            mism[f"v2.{k}"] += 1
            if mism[f"v2.{k}"] <= 3:
                print(f"    diff id {r['review_id']} {k}: stored={r.get(k)!r} mine={mine[k]!r}")
    agree = r["llm_emotion"] is not None and r["llm_emotion"] == mine["nrc_emotion"]
    if r["emotion_agree"] != agree: mism["v2.emotion_agree"] += 1
check("per-row mismatches (truth, prediction, llm_emotion, all nrc_* fields, emotion_agree)", {}, dict(mism))

# ---------------------------------------------------------------- 3. metrics
LAB = ["POSITIVE", "NEGATIVE"]


def sent_metrics(run, rows):
    n = len(rows)
    COLS = LAB + ["UNPARSED"]
    cells = {f"{a}->{b}": sum(r["truth"] == a and r["prediction"] == b for r in rows) for a in LAB for b in COLS}
    tc = {l: sum(r["truth"] == l for r in rows) for l in LAB}
    pc = {c: sum(r["prediction"] == c for r in rows) for c in COLS}
    correct = sum(r["truth"] == r["prediction"] for r in rows)
    maj = max(LAB, key=lambda l: (tc[l], -LAB.index(l)))
    per = {}
    for l in LAB:
        c = cells[f"{l}->{l}"]
        prec = c / pc[l] if pc[l] else None
        rec = c / tc[l]
        f1 = 2 * prec * rec / (prec + rec) if prec and rec else 0.0
        per[l] = dict(support=tc[l], predicted=pc[l], correct=c, wrong=tc[l] - c, precision=prec,
                      precision_undefined_never_predicted=pc[l] == 0, recall=rec, f1=f1)
    mis = {}
    for a in LAB:
        for b in COLS:
            ids = [r["review_id"] for r in rows if r["truth"] == a and r["prediction"] == b and a != b]
            if ids:
                mis[f"{a}->{b}"] = ids
    fails = sum(r["parse_status"] == "FAIL" for r in rows)
    apierr = sum(r["parse_status"] == "API_ERROR" for r in rows)
    unp = pc["UNPARSED"]
    return {
        "run": run, "label_scheme": "binary", "labels": LAB,
        "confusion_matrix_orientation": "rows = truth (from rating), columns = predicted",
        "n_rows": n, "correct": correct, "incorrect": n - correct, "accuracy": correct / n,
        "truth_distribution": {"counts": tc, "share": {l: tc[l] / n for l in LAB}},
        "prediction_distribution": {"counts": pc, "share": {c: pc[c] / n for c in COLS}},
        "majority_class": maj, "majority_baseline_accuracy": tc[maj] / n,
        "accuracy_minus_majority_baseline": correct / n - tc[maj] / n,
        "balanced_accuracy": sum(per[l]["recall"] for l in LAB) / len(LAB),
        "majority_baseline_balanced_accuracy": 1 / len(LAB),
        "macro_f1": sum(per[l]["f1"] for l in LAB) / len(LAB),
        "per_class": per,
        "confusion_matrix": {"rows": LAB, "columns": COLS, "counts": [[cells[f"{a}->{b}"] for b in COLS] for a in LAB]},
        "confusion_cells": cells,
        "confusion_row_share": {k: v / tc[k.split("->")[0]] for k, v in cells.items()},
        "misclassified_review_ids": mis,
        "parse_fail_count": fails, "api_error_count": apierr, "unparsed_count": unp, "unparsed_share": unp / n,
        "rows_needing_retry": fails + apierr,
    }


def emo_metrics(run, rows):
    n = len(rows)
    for r in rows:
        r["_nrc"] = r["_mine"]["nrc_emotion"]
        r["_agree"] = r["llm_emotion"] is not None and r["llm_emotion"] == r["_nrc"]
    LC, NC = EMO + ["UNPARSED"], EMO + ["TIE", "NONE"]
    llm = Counter(r["llm_emotion"] or "UNPARSED" for r in rows)
    nc = Counter(r["_nrc"] for r in rows)

    def grp(sub, key):
        a = sum(key(r) for r in sub)
        return {"n": len(sub), "agree": a, "rate": a / len(sub) if sub else None}

    S_all, S_en = rows, [r for r in rows if r["_nrc"] != "NONE"]
    S_ent = [r for r in rows if r["_nrc"] not in ("NONE", "TIE")]
    ag = lambda r: r["_agree"]
    const = max(EMO, key=lambda e: (llm[e], -EMO.index(e)))
    cg = lambda r: r["_nrc"] == const
    ties = [r for r in rows if r["_nrc"] == "TIE"]
    A = {"all_rows": grp(S_all, ag), "excluding_none": grp(S_en, ag), "excluding_none_and_tie": grp(S_ent, ag)}
    C = {"all_rows": grp(S_all, cg), "excluding_none": grp(S_en, cg), "excluding_none_and_tie": grp(S_ent, cg)}
    tb = lambda r: r["llm_emotion"] is not None and r["llm_emotion"] == r["_mine"]["nrc_emotion_tiebreak"]
    seen, uniq = set(), []
    for r in rows:
        if (r["title"], r["text"]) not in seen:
            seen.add((r["title"], r["text"]))
            uniq.append(r)
    cross = {f"{a}->{b}": sum((r["llm_emotion"] or "UNPARSED") == a and r["_nrc"] == b for r in rows) for a in LC for b in NC}
    in_tie = sum(r["llm_emotion"] in r["_mine"]["nrc_tied"] for r in ties)
    return {
        "run": run,
        "lexicon": {k: lexmeta[k] for k in ("source", "download_url", "lexicon_sha256", "word_count",
                                            "words_with_any_of_8_emotions", "citation")},
        "n_rows": n,
        "crosstab_orientation": "rows = LLM emotion, columns = NRC word-list emotion",
        "llm_emotion_counts": {c: llm[c] for c in LC}, "llm_emotion_share": {c: llm[c] / n for c in LC},
        "nrc_emotion_counts": {c: nc[c] for c in NC}, "nrc_emotion_share": {c: nc[c] / n for c in NC},
        "agreement": A,
        "agreement_rate_all_rows": A["all_rows"]["rate"],
        "agreement_rate_excluding_none": A["excluding_none"]["rate"],
        "agreement_rate_excluding_none_and_tie": A["excluding_none_and_tie"]["rate"],
        "tie_rows": len(ties), "tie_rows_llm_emotion_in_tied_set": in_tie,
        "tie_rows_llm_emotion_in_tied_set_rate": in_tie / len(ties), "none_rows": nc["NONE"],
        "constant_baseline_emotion": const, "constant_baseline": C,
        "constant_baseline_rate_all_rows": C["all_rows"]["rate"],
        "constant_baseline_rate_excluding_none": C["excluding_none"]["rate"],
        "constant_baseline_rate_excluding_none_and_tie": C["excluding_none_and_tie"]["rate"],
        "llm_minus_constant_rate_all_rows": A["all_rows"]["rate"] - C["all_rows"]["rate"],
        "llm_minus_constant_rate_excluding_none_and_tie": A["excluding_none_and_tie"]["rate"] - C["excluding_none_and_tie"]["rate"],
        "tie_rows_constant_in_tied_set": sum(const in r["_mine"]["nrc_tied"] for r in ties),
        "agreement_llm_not_constant": {
            "all_rows": grp([r for r in rows if r["llm_emotion"] != const], ag),
            "excluding_none_and_tie": grp([r for r in S_ent if r["llm_emotion"] != const], ag)},
        "agreement_tiebreak": {"all_rows": grp(S_all, tb), "excluding_none": grp(S_en, tb)},
        "unique_title_text": {"n": len(uniq), "agree": sum(ag(r) for r in uniq),
                              "tie": sum(r["_nrc"] == "TIE" for r in uniq), "none": sum(r["_nrc"] == "NONE" for r in uniq)},
        "negation": {"rows_with_negated_hits": sum(bool(r["_mine"]["nrc_negated_hits"]) for r in rows),
                     "negated_hits_total": sum(len(r["_mine"]["nrc_negated_hits"]) for r in rows)},
        "crosstab": {"rows": LC, "columns": NC, "counts": [[cross[f"{a}->{b}"] for b in NC] for a in LC]},
        "crosstab_cells": cross,
        "divergent_review_ids": [r["review_id"] for r in rows if r["_nrc"] not in ("NONE", "TIE") and not r["_agree"]],
    }


TEXT_ONLY = {"method", "constant_baseline_note", "tiebreak_rule", "rule"}


def leaves(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from leaves(v, f"{prefix}.{k}" if prefix else k)
    else:
        yield prefix, obj


def get(obj, path):
    for k in path.split("."):
        if isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            return KeyError
    return obj


def same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-12
    return a == b


print("== 3. metrics recomputation")
RECOMP = {"first100_v1": {"metrics.json": sent_metrics("first100_v1", V1)},
          "first100_v2": {"metrics.json": sent_metrics("first100_v2", V2), "emotion_metrics.json": emo_metrics("first100_v2", V2)}}
FILES = {}
for run, d in RECOMP.items():
    for fname, mine in d.items():
        stored = json.loads((RUNS / run / fname).read_text())
        FILES[f"runs/{run}/{fname}"] = stored
        nleaf, bad, skipped = 0, [], []
        for path, v in leaves(stored):
            if path.split(".")[-1] in TEXT_ONLY:
                skipped.append(path)
                continue
            nleaf += 1
            m = get(mine, path)
            if m is KeyError:
                bad.append((path, v, "NOT RECOMPUTED"))
            elif not same(v, m):
                bad.append((path, v, m))
        for path, v in leaves(mine):  # also: anything recomputed but missing from file
            if get(stored, path) is KeyError:
                bad.append((path, "MISSING IN FILE", v))
        print(f"  {run}/{fname}: {nleaf} leaves compared, {len(skipped)} prose leaves skipped {skipped}")
        check(f"{run}/{fname} leaf mismatches", [], bad)
FILES["runs/first100_v1/run_meta.json"] = json.loads((RUNS / "first100_v1/run_meta.json").read_text())
FILES["runs/first100_v2/run_meta.json"] = json.loads((RUNS / "first100_v2/run_meta.json").read_text())
FILES["runs/rating_distribution.json"] = json.loads((RUNS / "rating_distribution.json").read_text())
M2 = RECOMP["first100_v2"]["emotion_metrics.json"]
meta2 = FILES["runs/first100_v2/run_meta.json"]
check("v2 run_meta api_call_count + cache_hits == rows; cache hits == from_cache rows",
      (100, meta2["cache_hits"]), (meta2["api_call_count"] + meta2["cache_hits"], sum(r["from_cache"] for r in V2)))
check("v1 vs v2 sentiment flips", [], [r1["review_id"] for r1, r2 in zip(V1, V2) if r1["prediction"] != r2["prediction"]])

# ---------------------------------------------------------------- 4. dashboard DOM
print("== 4. dashboard DOM")
from playwright.sync_api import sync_playwright  # noqa: E402


def fmt(v, f):
    if f == "pct":
        return f"{v * 100:.1f}%"
    if f == "count":
        return f"{v:,}"
    if f == "pp":
        return ("+" if v >= 0 else "−") + f"{abs(v * 100):.1f} pts"
    return str(v)


def expected_format(path, v, file):
    """Expected display format from the FILE value's type (JSON 0.0 is a rate, 0 is a count)."""
    last = path.split(".")[-1]
    if isinstance(v, (bool, str, list)):
        return {"text"}
    if "run_meta" in file:  # settings such as temperature / seed, not metrics
        return {"text", "count"}
    if "minus" in last:
        return {"pp"}
    if isinstance(v, int):
        return {"count"}
    return {"pct"}


JS_METRICS = """() => [...document.querySelectorAll('[data-raw]')].map(e => ({
  metric: e.dataset.metric, raw: e.dataset.raw, source: e.dataset.source, format: e.dataset.format,
  run: e.dataset.run, text: e.textContent, visible: e.checkVisibility()}))"""
JS_MARKS = """() => [...document.querySelectorAll('[data-value]')].map(e => { const b = e.getBoundingClientRect();
  return {run: e.dataset.run, metric: e.dataset.metric, value: e.dataset.value, label: e.dataset.label,
  width: b.width, height: b.height, style: e.getAttribute('style') || '', visible: e.checkVisibility(),
  cls: e.className, sec: e.closest('section') ? e.closest('section').id : null}; })"""
JS_UNTAGGED = """() => { const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n; while ((n = w.nextNode())) { const p = n.parentElement; if (!p || !/\\d/.test(n.textContent)) continue;
  if (p.closest('[data-raw]') || p.closest('#review-table') || p.closest('script') || !p.checkVisibility()) continue;
  out.push(n.textContent.trim().slice(0, 80)); } return out; }"""

with sync_playwright() as pw:
    br = pw.chromium.launch()
    page = br.new_page(viewport={"width": 1440, "height": 900})
    errors, requests = [], []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda q: not q.url.startswith(("file:", "data:")) and requests.append(q.url))
    page.goto((ROOT / "dashboard/index.html").resolve().as_uri())
    page.wait_for_selector("[data-run-tab]")
    # embedded payload vs files
    payload = json.loads(page.evaluate("() => document.querySelector('script[type=\"application/json\"]').textContent"))
    for run in payload["runs"]:
        name = run["run"]
        check(f"embedded {name} metrics == file", FILES[f"runs/{name}/metrics.json"], run["metrics"])
        if "emotion_metrics" in run:
            check(f"embedded {name} emotion_metrics == file", FILES[f"runs/{name}/emotion_metrics.json"], run["emotion_metrics"])
        rows = load_rows(name)
        check(f"embedded {name} rows == predictions projection", True,
              all(all(er[k] == pr[k] for k in er) for er, pr in zip(run["rows"], rows)) and len(run["rows"]) == len(rows))
    check("embedded run list", ["first100_v1", "first100_v2"], [r["run"] for r in payload["runs"]])

    for runname in ["first100_v1", "first100_v2"]:
        print(f"  -- tab {runname}")
        page.click(f'[data-run-tab="{runname}"]')
        page.wait_for_timeout(300)
        mets = [m for m in page.evaluate(JS_METRICS) if m["visible"]]
        bad = []
        for m in mets:
            file, _, field = m["source"].partition("#")
            if file not in FILES:
                bad.append((m["metric"], "unknown source", m["source"]))
                continue
            fv = get(FILES[file], field)
            raw = json.loads(m["raw"])
            if field != m["metric"]:
                bad.append((m["metric"], "metric != source field", field))
            if m["run"] != runname or (runname not in file and "rating_distribution" not in file):
                bad.append((m["metric"], "wrong run", m["run"], file))
            if fv is KeyError or not same(fv, raw):
                bad.append((m["metric"], "data-raw != file", raw, fv))
            if not same(raw, get(RECOMP[runname].get(file.split("/")[-1], {}), field)) and "run_meta" not in file \
                    and "rating_distribution" not in file:
                bad.append((m["metric"], "data-raw != recomputation", raw))
            ef = expected_format(field, fv, file)
            if m["format"] not in ef:
                bad.append((m["metric"], "data-format", m["format"], "expected", ef))
            if m["text"] != fmt(raw, m["format"]):
                bad.append((m["metric"], "text", m["text"], "expected", fmt(raw, m["format"])))
        nsrc = Counter(m["source"].split("#")[0] for m in mets)
        print(f"     {len(mets)} visible data-raw numbers by source: {dict(nsrc)}")
        check(f"{runname} metric-span failures", [], bad)

        marks = [k for k in page.evaluate(JS_MARKS) if k["visible"]]
        badm = []
        em = FILES.get(f"runs/{runname}/emotion_metrics.json")
        for k in marks:
            path = k["metric"]
            if path.startswith("emotion."):
                fv, mine = get(em, path[8:]), get(M2, path[8:])
            elif k["sec"] and "rating" in (k["sec"] or ""):
                fv = mine = get(FILES["runs/rating_distribution.json"], path)
            else:
                fv, mine = get(FILES[f"runs/{runname}/metrics.json"], path), get(RECOMP[runname]["metrics.json"], path)
            if k["run"] != runname:
                badm.append((path, "run", k["run"]))
            if fv is KeyError or str(fv) != k["value"]:
                badm.append((path, "data-value != file", k["value"], fv))
            if mine is not KeyError and not same(fv, mine):
                badm.append((path, "file != recomputation", fv, mine))
            if fv not in (0, KeyError) and (k["width"] <= 0.5 or k["height"] <= 0.5):
                badm.append((path, "collapsed mark", k["width"], k["height"]))
            if not k["label"]:
                badm.append((path, "empty data-label"))
            if path.startswith("emotion.") and "crosstab_cells" in path:
                a, b = path.split(".", 2)[2].split("->")
                nm = lambda x: {"UNPARSED": "Unparsed", "TIE": "Tie", "NONE": "None"}.get(x, x)
                if k["label"] != f"Model: {nm(a)} · word list: {nm(b)}":
                    badm.append((path, "label", k["label"]))
            if path.startswith("emotion.") and "_emotion_counts" in path:
                mx = max(max(em["llm_emotion_counts"].values()), max(em["nrc_emotion_counts"].values()))
                w = re.search(r"width:\s*([\d.]+)%", k["style"])
                if not w or abs(float(w.group(1)) - 100 * fv / mx) > 0.006:
                    badm.append((path, "bar width style", k["style"], 100 * fv / mx))
        kinds = Counter(k["metric"].split(".")[1] if k["metric"].startswith("emotion.") else k["metric"].split(".")[0] for k in marks)
        print(f"     {len(marks)} visible chart marks: {dict(kinds)}")
        check(f"{runname} chart-mark failures", [], badm)
        if runname == "first100_v2":
            ncross = sum("crosstab_cells" in k["metric"] for k in marks)
            check("cross-tab cells rendered", 90, ncross)
            heads = page.evaluate("() => [...document.querySelectorAll('.xt-head')].map(e => [e.textContent, e.title])")
            rowh = page.evaluate("() => [...document.querySelectorAll('.xt-rowhead')].map(e => e.textContent)")
            print("     xt col heads:", heads)
            print("     xt row heads:", rowh)
            order = page.evaluate("() => [...document.querySelectorAll('.xt [data-metric]')].filter(e=>e.dataset.value!==undefined).map(e => e.dataset.metric)")
            exp = [f"emotion.crosstab_cells.{a}->{b}" for a in M2["crosstab"]["rows"] for b in M2["crosstab"]["columns"]]
            check("cross-tab DOM order rows=LLM, cols=NRC", exp, order)
            lines = page.evaluate("""() => [...document.querySelectorAll('.xt-head')].map(e => { const r = document.createRange();
              r.selectNodeContents(e); const tops = new Set([...r.getClientRects()].map(x => Math.round(x.top)));
              return [e.textContent, tops.size, e.scrollWidth > e.clientWidth + 1]; })""")
            print("     xt header [text, line boxes, overflows]:", lines)
            check("cross-tab column headers on more than one line or overflowing", [], [l for l in lines if l[1] > 1 or l[2]])
            tiles = page.evaluate("() => [...document.querySelectorAll('.emo-tiles .tile')].map(t => t.innerText.replace(/\\s+/g,' '))")
            print("     emotion tiles:", tiles)
            ctx = page.evaluate("() => document.querySelector('.emo-context').innerText")
            print("     context line:", ctx)
            # review table emotion cells
            trs = page.evaluate("""() => [...document.querySelectorAll('#review-table tbody tr')].map(tr => ({
              id: +tr.dataset.reviewId, emo: tr.dataset.emo, cells: [...tr.querySelectorAll('td.emo')].map(td => td.innerText)}))""")
            byid = {r["review_id"]: r for r in V2}
            badt = []
            for t in trs:
                r = byid[t["id"]]
                g = "agree" if r["_agree"] else "tie" if r["_nrc"] == "TIE" else "none" if r["_nrc"] == "NONE" else "differ"
                if t["emo"] != g:
                    badt.append((t["id"], "data-emo", t["emo"], g))
                if t["cells"][0].strip() != (r["llm_emotion"] or "—"):
                    badt.append((t["id"], "llm cell", t["cells"][0]))
                exp2 = r["_nrc"].lower()
                if not t["cells"][1].strip().startswith(exp2):
                    badt.append((t["id"], "nrc cell", t["cells"][1]))
                if r["_nrc"] == "TIE" and " / ".join(r["_mine"]["nrc_tied"]) not in t["cells"][1]:
                    badt.append((t["id"], "tied list", t["cells"][1]))
            check("review table: 100 rows, emotion cells/data-emo vs recomputation", (100, []), (len(trs), badt))
            for opt, expn in [("agree", 20), ("differ", 18), ("tie", 47), ("none", 15), ("all", 100)]:
                mine_n = {"agree": sum(r["_agree"] for r in V2), "differ": len(M2["divergent_review_ids"]),
                          "tie": M2["tie_rows"], "none": M2["none_rows"], "all": 100}[opt]
                page.select_option("#f-emo", opt)
                page.wait_for_timeout(100)
                live = page.evaluate("() => [document.querySelector('#shown-count').dataset.liveCount, document.querySelector('#shown-count').textContent, [...document.querySelectorAll('#review-table tbody tr')].filter(t => t.checkVisibility()).length]")
                check(f"f-emo={opt} live count / text / visible rows", (str(mine_n), str(mine_n), mine_n), tuple(live))
        unt = page.evaluate(JS_UNTAGGED)
        print(f"     untagged visible digit text ({len(unt)}): {sorted(set(unt))}")
    check("console/page errors", [], errors)
    check("non-file network requests", [], requests)
    br.close()

# ---------------------------------------------------------------- 5. written claims
print("== 5. written claims")
E = json.loads((RUNS / "first100_v2/emotion_metrics.json").read_text())
byid = {r["review_id"]: r for r in V2}
pct = lambda a, n: f"{100 * a / n:.1f}%"
A = M2["agreement"]; C = M2["constant_baseline"]
check("agreement 20/100 20/85 20/38 ; rates", ((20, 100), (20, 85), (20, 38), "20.0%", "23.5%", "52.6%"),
      tuple((A[k]["agree"], A[k]["n"]) for k in ("all_rows", "excluding_none", "excluding_none_and_tie"))
      + tuple(pct(A[k]["agree"], A[k]["n"]) for k in ("all_rows", "excluding_none", "excluding_none_and_tie")))
check("constant joy 22/100 22/85 22/38 ; rates", ("joy", (22, 100), (22, 85), (22, 38), "22.0%", "25.9%", "57.9%"),
      (M2["constant_baseline_emotion"],) + tuple((C[k]["agree"], C[k]["n"]) for k in ("all_rows", "excluding_none", "excluding_none_and_tie"))
      + tuple(pct(C[k]["agree"], C[k]["n"]) for k in ("all_rows", "excluding_none", "excluding_none_and_tie")))
check("LLM minus constant −2.0 / −5.3 pts", ("−2.0 pts", "−5.3 pts"),
      (fmt(M2["llm_minus_constant_rate_all_rows"], "pp"), fmt(M2["llm_minus_constant_rate_excluding_none_and_tie"], "pp")))
nj = M2["agreement_llm_not_constant"]
check("non-joy agree 1/20 (5.0%), 1/11 (9.1%)", ((1, 20, "5.0%"), (1, 11, "9.1%")),
      tuple((nj[k]["agree"], nj[k]["n"], pct(nj[k]["agree"], nj[k]["n"])) for k in ("all_rows", "excluding_none_and_tie")))
check("ties 47, LLM in tied 45, joy in tied 45, NONE 15", (47, 45, 45, 15),
      (M2["tie_rows"], M2["tie_rows_llm_emotion_in_tied_set"], M2["tie_rows_constant_in_tied_set"], M2["none_rows"]))
tb = M2["agreement_tiebreak"]
check("tiebreak 23/100 23.0%, 23/85 27.1%", ((23, 100, "23.0%"), (23, 85, "27.1%")),
      tuple((tb[k]["agree"], tb[k]["n"], pct(tb[k]["agree"], tb[k]["n"])) for k in ("all_rows", "excluding_none")))
dup = [r["review_id"] for r in V2 if r["title"].lower() == "good product"]
check("duplicate Good Product ids 20-28, all TIE", (list(range(20, 29)), True), (dup, all(byid[i]["_nrc"] == "TIE" for i in dup)))
check("unique title+text 93 / agree 20 / TIE 40 / NONE 15", {"n": 93, "agree": 20, "tie": 40, "none": 15}, M2["unique_title_text"])
check("LLM counts", {"joy": 80, "trust": 9, "anger": 7, "anticipation": 3, "disgust": 1, "fear": 0, "sadness": 0, "surprise": 0, "UNPARSED": 0}, M2["llm_emotion_counts"])
check("NRC counts", {"TIE": 47, "joy": 22, "NONE": 15, "anticipation": 14, "sadness": 1, "trust": 1, "anger": 0, "fear": 0, "disgust": 0, "surprise": 0}, M2["nrc_emotion_counts"])
check("LLM anger ids and truth", [(4, "NEGATIVE"), (15, "NEGATIVE"), (17, "POSITIVE"), (32, "NEGATIVE"), (51, "NEGATIVE"), (63, "NEGATIVE"), (91, "NEGATIVE")],
      [(r["review_id"], r["truth"]) for r in V2 if r["llm_emotion"] == "anger"])
check("17 rating 5", 5.0, byid[17]["rating"])
claimed_cells = {"joy->joy": 19, "joy->TIE": 44, "joy->NONE": 9, "joy->anticipation": 8, "anger->anticipation": 3, "anger->joy": 1,
                 "anger->sadness": 1, "anger->trust": 1, "anger->NONE": 1, "trust->NONE": 5, "trust->anticipation": 2, "trust->joy": 1,
                 "trust->TIE": 1, "anticipation->TIE": 2, "anticipation->anticipation": 1, "disgust->joy": 1}
check("non-zero cross-tab cells", claimed_cells, {k: v for k, v in M2["crosstab_cells"].items() if v})
check("divergent 18", 18, len(M2["divergent_review_ids"]))


def hitlist(i):
    return [(h[0], h[1]) for h in byid[i]["_mine"]["nrc_hits"]]


def nz(i):
    return {k: v for k, v in byid[i]["_mine"]["nrc_scores"].items() if v}


check("51 scores / hits", ({"anticipation": 3, "joy": 2, "surprise": 2, "trust": 1}, [("gift", "gift"), ("monetary", "monetary"), ("cheer", "cheer")]), (nz(51), hitlist(51)))
check("51 cheer tags (ISSUES says 'cheer = joy/trust')", ["anticipation", "joy", "surprise", "trust"], sorted(LEX["cheer"]))
check("32 scores / hits", ({"sadness": 2, "anger": 1, "trust": 1}, sorted([("mistake", "mistake"), ("mistake", "mistake"), ("hit", "hit"), ("credit", "credit")])), (nz(32), sorted(hitlist(32))))
check("32 title Mistake", "Mistake", byid[32]["title"])
check("63 scores", {"trust": 6, "anticipation": 3, "fear": 2, "joy": 2, "sadness": 2, "surprise": 1}, nz(63))
h63 = Counter(e for _, e in hitlist(63))
check("63 hits include credit x2, transaction, provide, problem, difficult, lost", True,
      h63["credit"] >= 2 and all(h63[w] for w in ["transaction", "provide", "problem", "difficult", "lost"]))
print("     63 full hits:", [(h[0], h[1], h[2]) for h in byid[63]["_mine"]["nrc_hits"]])
check("17 scores", {"anticipation": 9, "joy": 4, "surprise": 3, "trust": 2, "anger": 1}, nz(17))
check("17 hit multiset", sorted([("gift", "gift")] * 3 + [("pretty", "pretty"), ("recipient", "recipient"), ("recipient", "recipient"),
                                  ("time", "time"), ("times", "time"), ("mail", "mail"), ("showed", "show"), ("complaint", "complaint")]), sorted(hitlist(17)))
check("17 'loved' present, not hit; love in lex; lov not", (True, False, True, False),
      ("loved" in byid[17]["_mine"]["_tokens"], any(t == "loved" for t, _ in hitlist(17)), "love" in LEX, "lov" in LEX))
check("46 scores / hits", ({"joy": 2, "anticipation": 1, "surprise": 1, "trust": 1}, [("love", "love"), ("gift", "gift"), ("show", "show")]), (nz(46), hitlist(46)))
check("46 v1+v2 prediction NEGATIVE, LLM disgust", ("NEGATIVE", "NEGATIVE", "disgust"), (V1[46]["prediction"], byid[46]["prediction"], byid[46]["llm_emotion"]))
ja = [r["review_id"] for r in V2 if r["llm_emotion"] == "joy" and r["_nrc"] == "anticipation"]
check("joy->anticipation ids", [9, 16, 41, 42, 70, 71, 93, 95], ja)
deciders, removal = {}, {}
for i in ja:
    only = [t for t, e in hitlist(i) if LEX[e] == {"anticipation"}]
    deciders[i] = sorted(set(e for t, e in hitlist(i) if LEX[e] == {"anticipation"}))
    sc = dict(byid[i]["_mine"]["nrc_scores"])
    sc["anticipation"] -= len(only)
    top = max(sc.values())
    removal[i] = [e for e in EMO if sc[e] == top] != ["anticipation"]
print("     joy->anticipation anticipation-only lexicon words per row:", deciders)
check("claimed deciding word per row (mail 9,41,42,70; time 71,93; recipient 16; store 95)",
      {9: ["mail"], 41: ["mail"], 42: ["mail"], 70: ["mail"], 71: ["time"], 93: ["time"], 16: ["recipient"], 95: ["store"]}, deciders)
check("removing anticipation-only words ends sole anticipation win in all 8", dict.fromkeys(ja, True), removal)
check("95 store twice", 2, sum(e == "store" for _, e in hitlist(95)))
check("9 only hit mail", [("mail", "mail")], hitlist(9))
check("93 hits fits->anger", True, any(t == "fits" for t, _ in hitlist(93)) and LEX.get("fits") == {"anger"})
none_ids = [r["review_id"] for r in V2 if r["_nrc"] == "NONE"]
easy_none = [i for i in none_ids if "easy" in (byid[i]["title"] + " " + byid[i]["text"]).lower()]
print("     NONE rows:", [(i, byid[i]["title"][:30], byid[i]["text"][:50]) for i in none_ids])
check("NONE rows containing 'easy' == 31,49,55,67,68,78,97,98", [31, 49, 55, 67, 68, 78, 97, 98], easy_none)
check("NONE by LLM: joy 9 trust 5 anger 1", {"joy": 9, "trust": 5, "anger": 1}, dict(Counter(byid[i]["llm_emotion"] for i in none_ids)))
check("45 NONE, 15 NONE", (True, True), (45 in none_ids, 15 in none_ids))
emoji_only = [i for i in none_ids if not re.search(r"[A-Za-z0-9]", byid[i]["title"] + byid[i]["text"])]
print("     emoji/no-letter NONE rows (ISSUES: 'emoji-only reviews (45)'):", emoji_only)
check("great/easy/works/work not in 8-emotion lexicon", (False, False, False, False), tuple(w in LEX for w in ["great", "easy", "works", "work"]))
tie_rows = [r for r in V2 if r["_nrc"] == "TIE"]
gift_all = sum(e == "gift" for r in V2 for _, e in hitlist(r["review_id"]))
gift_tie = sum(e == "gift" for r in tie_rows for _, e in hitlist(r["review_id"]))
good_tie = sum(e == "good" for r in tie_rows for _, e in hitlist(r["review_id"]))
check("gift hits 104 total, 40 in ties; good 29 in ties", (104, 40, 29), (gift_all, gift_tie, good_tie))
tie_rows_with_gift = sum(any(e == "gift" for _, e in hitlist(r["review_id"])) for r in tie_rows)
print(f"     tie rows containing a gift hit: {tie_rows_with_gift} of {len(tie_rows)}")
sets = Counter(tuple(r["_mine"]["nrc_tied"]) for r in tie_rows)
check("tied sets {ant,joy,sur} 15, {ant,joy} 14, {ant,joy,sur,trust} 13", (15, 14, 13),
      (sets[("anticipation", "joy", "surprise")], sets[("anticipation", "joy")], sets[("anticipation", "joy", "surprise", "trust")]))
check("gift-only reviews 8", 8, sum(bool(hitlist(r["review_id"])) and all(e == "gift" for _, e in hitlist(r["review_id"])) for r in V2))
check("negation 15 hits in 11 rows", {"rows_with_negated_hits": 11, "negated_hits_total": 15}, M2["negation"])
print("     negated hits with context (auditor judges whether negator scopes over hit):")
for r in V2:
    toks = r["_mine"]["_tokens"]
    for i, t in enumerate(toks):
        if entry(t) and any(p in NEG for p in toks[max(0, i - 3):i]):
            print(f"       id {r['review_id']}: '{' '.join(toks[max(0, i - 3):i + 2])}' hit={t}")
trust_ids = [r["review_id"] for r in V2 if r["llm_emotion"] == "trust"]
kw = [i for i in trust_ids if re.search(r"easy|convenien|simple|saver", (byid[i]["title"] + " " + byid[i]["text"]).lower())]
check("LLM trust rows with easy/convenient/simple/saver = 14,31,34,49,55,56,78,97", [14, 31, 34, 49, 55, 56, 78, 97], kw)
check("of those, NONE = 31,49,55,78,97", [31, 49, 55, 78, 97], [i for i in kw if byid[i]["_nrc"] == "NONE"])
check("v1/v2 errors 17,46 POS->NEG, 98 NEG->POS; parse fails", ({"POSITIVE->NEGATIVE": [17, 46], "NEGATIVE->POSITIVE": [98]}, 0),
      (RECOMP["first100_v2"]["metrics.json"]["misclassified_review_ids"], RECOMP["first100_v2"]["metrics.json"]["parse_fail_count"]))
check("PROGRESS/ISSUES lexicon counts 14,154 / 4,454", (14154, 4454), (len(words), len(LEX)))
check("PROGRESS API calls 199 == cache/api_calls_total.json", 199, json.loads((ROOT / "cache/api_calls_total.json").read_text())["total"])
vd = (ROOT / "reviews/step5_verify_dashboard.txt").read_text()
got_checks = re.search(r"(\d+) checks, (\d+) failures", vd)
prog = (ROOT / "PROGRESS.md").read_text()
claimed = re.search(r"verify_dashboard\.py` PASS ([\d,]+) checks \(`reviews/step5_verify_dashboard\.txt`\)", prog)
check("PROGRESS 'verify_dashboard.py PASS N checks' == step5_verify_dashboard.txt", got_checks.group(1),
      claimed.group(1).replace(",", "") if claimed else None)
issues = (ROOT / "ISSUES.md").read_text()
check("ISSUES.md contains stale 'agreement advantage' wording", False, "agreement advantage" in issues)
check("PROGRESS 'Current step' still says 'fixing findings'", False, "reviewer round 1 done; fixing findings" in prog)

print(f"\nTOTAL FAILS: {len(FAILS)}")
sys.exit(1 if FAILS else 0)
