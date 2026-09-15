"""Independent Step 5 numbers audit. Imports nothing from src/.

1. Lexicon: sha256 vs runs/nrc_lexicon_meta.json; word_count, words_with_any_of_8_emotions.
2. Per row (first100_v2): own NRC implementation of the documented method -> nrc_emotion,
   nrc_tied, nrc_scores, nrc_hits, nrc_token_count, emotion_agree; LLM emotion and sentiment
   re-parsed from raw_responses. Compared to the stored fields.
3. metrics.json (v1, v2) and emotion_metrics.json (v2): every leaf vs recomputation.
4. v1 vs v2 comparison claims; run_meta api_call_count/cache_hits.
5. Built dashboard in headless Chromium, both run tabs: every [data-metric][data-raw] number
   (source file value == data-raw == recomputed; text == display rule), every chart mark
   (attrs, value == file == recomputed, size > 0, bar width proportional), cross-tab DOM order,
   review-table emotion cells, emotion filter live counts, untagged digits.
6. Written claims in reviews/step5_analysis.md and ISSUES.md Step 5 entries.
Usage: .venv/bin/python reviews/step5_numbers_auditor/audit_step5.py
"""
import hashlib
import html
import json
import math
import re
from collections import Counter
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FAILS = []
EMO = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]


def same(a, b, tol=1e-12):
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) == type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, abs_tol=tol)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


def check(name, got, expected, quiet=False):
    ok = same(got, expected)
    if not ok or not quiet:
        e, g = repr(expected), repr(got)
        if ok and len(e) > 160:
            print(f"OK   {name}: identical ({len(e)} chars)")
        else:
            print(f"{'OK  ' if ok else 'FAIL'} {name}: expected={e} got={g}")
    if not ok:
        FAILS.append(name)
    return ok


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict) and obj:
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    else:
        out[prefix] = obj
    return out


def load(run):
    d = ROOT / "runs" / run
    preds = [json.loads(l) for l in open(d / "predictions.jsonl", encoding="utf-8")]
    return d, preds, json.loads((d / "metrics.json").read_text()), json.loads((d / "run_meta.json").read_text())


# ------------------------------------------------------------------ 1. lexicon
print("== 1. lexicon")
lex_meta = json.loads((ROOT / "runs" / "nrc_lexicon_meta.json").read_text())
raw_lex = (ROOT / "data" / "nrc" / "NRC-Emotion-Lexicon-Wordlevel.txt").read_bytes()
check("lexicon sha256", hashlib.sha256(raw_lex).hexdigest(), lex_meta["lexicon_sha256"])
all_words, LEX = set(), {}
for line in raw_lex.decode("utf-8").splitlines():
    p = line.rstrip("\r\n").split("\t")
    if len(p) != 3:
        continue
    all_words.add(p[0])
    if p[2] == "1" and p[1] in EMO:
        LEX.setdefault(p[0], set()).add(p[1])
check("word_count", len(all_words), lex_meta["word_count"])
check("words_with_any_of_8_emotions", len(LEX), lex_meta["words_with_any_of_8_emotions"])

# ------------------------------------------------------------------ 2. per-row recomputation
STAR = re.compile(r"\s*(one|two|three|four|five)\s+stars?\s*", re.I)


def blank(s):
    return "" if STAR.fullmatch(s) else s


def nrc(title, text):
    s = blank(title) + " " + blank(text)
    s = html.unescape(s.replace("<br />", " "))
    toks = re.findall(r"[a-z]+", s.lower())
    scores = dict.fromkeys(EMO, 0)
    hits = []
    for t in toks:
        w = t if t in LEX else None
        if w is None:
            for suf in ("ing", "ed", "es", "s"):
                if t.endswith(suf) and t[: -len(suf)] in LEX:
                    w = t[: -len(suf)]
                    break
        if w is None:
            continue
        for e in LEX[w]:
            scores[e] += 1
        hits.append([t, w, sorted(LEX[w])])
    top = max(scores.values())
    tied = [e for e in EMO if scores[e] == top]
    lab = "NONE" if top == 0 else ("TIE" if len(tied) > 1 else tied[0])
    return {"nrc_emotion": lab, "nrc_tied": tied if lab == "TIE" else [], "nrc_scores": scores,
            "nrc_hits": hits, "nrc_token_count": len(toks)}


def parse(raw, emotion):
    if not isinstance(raw, str):
        return None, None
    pat = r"LABEL=(POSITIVE|NEGATIVE);EMOTION=(" + "|".join(EMO) + ")" if emotion else r"LABEL=(POSITIVE|NEGATIVE)()"
    m = re.fullmatch(pat, raw.strip())
    return (m.group(1), m.group(2) or None) if m else (None, None)


print("== 2. per-row NRC + LLM emotion (first100_v2)")
d2, P2, M2, meta2 = load("first100_v2")
d1, P1, M1, meta1 = load("first100_v1")
EM2 = json.loads((d2 / "emotion_metrics.json").read_text())
REC = {}
bad_rows = Counter()
for p in P2:
    r = nrc(p["title"], p["text"])
    lab, emo = parse(p["raw_responses"][-1] if p["raw_responses"] else None, True)
    r["prediction"] = lab or "UNPARSED"
    r["llm_emotion"] = emo
    r["emotion_agree"] = emo is not None and emo == r["nrc_emotion"]
    REC[p["review_id"]] = r
    for k, v in r.items():
        if not same(p.get(k), v):
            bad_rows[k] += 1
            if bad_rows[k] <= 3:
                print(f"     row {p['review_id']} {k}: stored={p.get(k)!r} recomputed={v!r}")
check("rows", len(P2), 100)
check("per-row field mismatches (stored vs independent)", dict(bad_rows), {})
check("stored truth == rating>=4 rule", sum(p["truth"] != ("POSITIVE" if p["rating"] >= 4 else "NEGATIVE") for p in P2), 0)

# ------------------------------------------------------------------ 3. metrics recomputation


def sentiment_metrics(run, preds, emotion):
    L, C = ["POSITIVE", "NEGATIVE"], ["POSITIVE", "NEGATIVE", "UNPARSED"]
    ids = [p["review_id"] for p in preds]
    truth = {p["review_id"]: "POSITIVE" if p["rating"] >= 4 else "NEGATIVE" for p in preds}
    pred = {p["review_id"]: parse(p["raw_responses"][-1] if p["raw_responses"] else None, emotion)[0] or "UNPARSED" for p in preds}
    n = len(preds)
    cm = {t: {c: sum(truth[i] == t and pred[i] == c for i in ids) for c in C} for t in L}
    tc = {t: sum(cm[t].values()) for t in L}
    pc = {c: sum(cm[t][c] for t in L) for c in C}
    cor = sum(cm[t][t] for t in L)
    rec = {t: cm[t][t] / tc[t] for t in L}
    prec = {t: cm[t][t] / pc[t] if pc[t] else 0.0 for t in L}
    f1 = {t: 2 * prec[t] * rec[t] / (prec[t] + rec[t]) if prec[t] and rec[t] else 0.0 for t in L}
    maj = max(L, key=lambda t: (tc[t], -L.index(t)))
    return pred, {
        "run": run, "label_scheme": "binary", "labels": L,
        "confusion_matrix_orientation": "rows = truth (from rating), columns = predicted",
        "n_rows": n, "correct": cor, "incorrect": n - cor, "accuracy": cor / n,
        "truth_distribution": {"counts": tc, "share": {t: tc[t] / n for t in L}},
        "prediction_distribution": {"counts": pc, "share": {c: pc[c] / n for c in C}},
        "majority_class": maj, "majority_baseline_accuracy": tc[maj] / n,
        "accuracy_minus_majority_baseline": cor / n - tc[maj] / n,
        "balanced_accuracy": sum(rec.values()) / 2, "majority_baseline_balanced_accuracy": 0.5,
        "macro_f1": sum(f1.values()) / 2,
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


def compare_leaves(name, file_obj, rec_obj):
    F, R = flatten(file_obj), flatten(rec_obj)
    check(f"{name}: leaf paths", sorted(F), sorted(R), quiet=True)
    nb = sum(not check(f"{name}#{k}", F.get(k), R[k], quiet=True) for k in R)
    print(f"     {name}: {len(R)} leaves compared, {nb} mismatches")
    return R


print("== 3. metrics recomputation")
pred1, R1 = sentiment_metrics("first100_v1", P1, False)
pred2, R2 = sentiment_metrics("first100_v2", P2, True)
RF1 = compare_leaves("v1 metrics.json", M1, R1)
RF2 = compare_leaves("v2 metrics.json", M2, R2)
check("v2 stored prediction == reparse", sum(p["prediction"] != pred2[p["review_id"]] for p in P2), 0)

n = len(P2)
rows = [dict(review_id=p["review_id"], **REC[p["review_id"]]) for p in P2]
LC, NC = EMO + ["UNPARSED"], EMO + ["TIE", "NONE"]
xt = {a: {b: 0 for b in NC} for a in LC}
for r in rows:
    xt[r["llm_emotion"] or "UNPARSED"][r["nrc_emotion"]] += 1


def sub(f):
    s = [r for r in rows if f(r)]
    a = sum(r["emotion_agree"] for r in s)
    return {"n": len(s), "agree": a, "rate": a / len(s) if s else None}


ties = [r for r in rows if r["nrc_emotion"] == "TIE"]
lin = sum(r["llm_emotion"] in r["nrc_tied"] for r in ties)
llm_c = Counter(r["llm_emotion"] or "UNPARSED" for r in rows)
nrc_c = Counter(r["nrc_emotion"] for r in rows)
ag = {"all_rows": sub(lambda r: True), "excluding_none": sub(lambda r: r["nrc_emotion"] != "NONE"),
      "excluding_none_and_tie": sub(lambda r: r["nrc_emotion"] not in ("NONE", "TIE"))}
REM = {
    "run": "first100_v2",
    "lexicon": {"source": lex_meta["source"], "download_url": lex_meta["download_url"],
                "lexicon_sha256": hashlib.sha256(raw_lex).hexdigest(), "word_count": len(all_words),
                "words_with_any_of_8_emotions": len(LEX), "citation": lex_meta["citation"]},
    "method": EM2["method"], "n_rows": n,
    "crosstab_orientation": "rows = LLM emotion, columns = NRC word-list emotion",
    "llm_emotion_counts": {c: llm_c[c] for c in LC}, "llm_emotion_share": {c: llm_c[c] / n for c in LC},
    "nrc_emotion_counts": {c: nrc_c[c] for c in NC}, "nrc_emotion_share": {c: nrc_c[c] / n for c in NC},
    "agreement": ag,
    "agreement_rate_all_rows": ag["all_rows"]["rate"], "agreement_rate_excluding_none": ag["excluding_none"]["rate"],
    "agreement_rate_excluding_none_and_tie": ag["excluding_none_and_tie"]["rate"],
    "tie_rows": len(ties), "tie_rows_llm_emotion_in_tied_set": lin, "tie_rows_llm_emotion_in_tied_set_rate": lin / len(ties),
    "none_rows": nrc_c["NONE"],
    "crosstab": {"rows": LC, "columns": NC, "counts": [[xt[a][b] for b in NC] for a in LC]},
    "crosstab_cells": {f"{a}->{b}": xt[a][b] for a in LC for b in NC},
    "divergent_review_ids": [r["review_id"] for r in rows if r["nrc_emotion"] not in ("NONE", "TIE") and not r["emotion_agree"]],
}
REMF = compare_leaves("v2 emotion_metrics.json", EM2, REM)

# ------------------------------------------------------------------ 4. v1 vs v2
print("== 4. v1 vs v2")
check("v1/v2 same review ids in order", [p["review_id"] for p in P1], [p["review_id"] for p in P2])
diff = [i for i in pred1 if pred1[i] != pred2[i]]
check("sentiment predictions differing v1 vs v2", diff, [])
check("misclassified ids v1 == v2", R1["misclassified_review_ids"], R2["misclassified_review_ids"])
print("     misclassified:", R2["misclassified_review_ids"])
fc = sum(bool(p.get("from_cache")) for p in P2)
check("v2 cache hits (rows from_cache)", fc, meta2["cache_hits"])
check("v2 api calls == sum of raw_responses from non-cache rows", sum(len(p["raw_responses"]) for p in P2 if not p.get("from_cache")), meta2["api_call_count"])
check("ISSUES '90 API calls + 10 cache hits'", (meta2["api_call_count"], meta2["cache_hits"]), (90, 10))
check("run_meta v2 counters", (meta2["parse_fail_count"], meta2["api_error_count"], meta2["rows_needing_retry"], meta2["n_rows"]),
      (R2["parse_fail_count"], R2["api_error_count"], R2["rows_needing_retry"], n))
blanked = sum(bool(STAR.fullmatch(p["title"]) or STAR.fullmatch(p["text"])) for p in P2)
check("ISSUES/verify_leak '4 rows had a star-phrase title/text blanked'", blanked, 4)

# ------------------------------------------------------------------ 5. DOM
print("== 5. dashboard DOM (headless Chromium)")
htmls = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
template = (ROOT / "dashboard" / "template.html").read_text(encoding="utf-8")
mo = re.search(r'<script id="dashboard-data" type="application/json">(.*?)</script>', htmls, re.S)
emb = json.loads(mo.group(1).replace("<\\/", "</"))
check("page shell == template.html", htmls[:mo.start(1)] + "__DASHBOARD_DATA__" + htmls[mo.end(1):] == template, True)
check("embedded runs", [r["run"] for r in emb["runs"]], ["first100_v1", "first100_v2"])
check("embedded v1 metrics == file", emb["runs"][0]["metrics"], M1)
check("embedded v2 metrics == file", emb["runs"][1]["metrics"], M2)
check("embedded v2 emotion_metrics == file", emb["runs"][1].get("emotion_metrics"), EM2)
check("v1 has no emotion_metrics embedded", "emotion_metrics" in emb["runs"][0], False)
for er, P in ((emb["runs"][0], P1), (emb["runs"][1], P2)):
    mism = [p["review_id"] for p, e in zip(P, er["rows"]) if any(not same(p.get(k), v) for k, v in e.items())]
    check(f"embedded rows == predictions.jsonl ({er['run']})", (len(er["rows"]), mism), (100, []))

FILES = {"runs/first100_v1/metrics.json": (M1, RF1), "runs/first100_v1/run_meta.json": (meta1, None),
         "runs/first100_v2/metrics.json": (M2, RF2), "runs/first100_v2/run_meta.json": (meta2, None),
         "runs/first100_v2/emotion_metrics.json": (EM2, REMF)}


def getpath(o, path):
    for k in path.split("."):
        if not isinstance(o, dict) or k not in o:
            return KeyError
        o = o[k]
    return o


def fmt(v, f):
    if f == "pct":
        return f"{v * 100:.1f}%"
    if f == "count":
        return f"{round(v):,}"
    if f == "pp":
        return ("−" if v < 0 else "+") + f"{abs(v * 100):.1f} pts"
    return str(v).lower() if isinstance(v, bool) else str(v)


JS_WALK = r"""() => { const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) { const t = w.currentNode, p = t.parentElement;
    if (!/\d/.test(t.textContent)) continue;
    if (p.closest('[data-metric][data-raw]') || p.closest('#review-table') || p.closest('script') || p.closest('#tip') || p.closest('[hidden]')) continue;
    if (!p.getClientRects().length) continue;
    out.push({text: t.textContent.trim(), where: (p.closest('[id]') || {}).id || p.tagName}); }
  return out; }"""

with sync_playwright() as pw:
    br = pw.chromium.launch()
    page = br.new_page(viewport={"width": 1440, "height": 900})
    errs, reqs = [], []
    page.on("console", lambda m: m.type == "error" and errs.append(m.text))
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("request", lambda r: not r.url.startswith(("file:", "data:")) and reqs.append(r.url))
    page.goto((ROOT / "dashboard" / "index.html").resolve().as_uri())
    page.wait_for_selector("#review-table tbody tr")
    for RUN, RF, P in (("first100_v1", RF1, P1), ("first100_v2", RF2, P2)):
        print(f"  -- tab {RUN}")
        page.click(f'[data-run-tab="{RUN}"]')
        page.wait_for_timeout(300)
        check(f"{RUN}: tab selected", page.get_attribute(f'[data-run-tab="{RUN}"]', "aria-selected"), "true")
        nums = page.eval_on_selector_all("[data-metric][data-raw]", """els => els.map(e => ({metric: e.dataset.metric,
            raw: e.dataset.raw, source: e.dataset.source, format: e.dataset.format, run: e.dataset.run,
            text: e.textContent, vis: e.getClientRects().length > 0 && !e.closest('[hidden]')}))""")
        nums = [s for s in nums if s["vis"]]
        bad = 0
        for i, s in enumerate(nums):
            tag = f"{RUN} num[{i}] {s['source']}"
            f_, _, field = (s["source"] or "").partition("#")
            ok = check(f"{tag}: data-metric == source field", s["metric"], field, quiet=True)
            ok &= check(f"{tag}: data-run", s["run"], RUN, quiet=True)
            ok &= check(f"{tag}: source file belongs to run", f_.startswith(f"runs/{RUN}/") and f_ in FILES, True, quiet=True)
            if f_ in FILES:
                fobj, rec = FILES[f_]
                raw = json.loads(s["raw"])
                ok &= check(f"{tag}: data-raw == file", raw, getpath(fobj, field), quiet=True)
                if rec is not None:
                    ok &= check(f"{tag}: data-raw == recomputed", raw, rec.get(field, KeyError), quiet=True)
                ok &= check(f"{tag}: text == display rule", s["text"], fmt(raw, s["format"]), quiet=True)
                if s["format"] == "pct":
                    ok &= check(f"{tag}: pct 1dp", bool(re.fullmatch(r"\d{1,3}\.\d%", s["text"])), True, quiet=True)
                if s["format"] == "count":
                    ok &= check(f"{tag}: integer", bool(re.fullmatch(r"[\d,]+", s["text"])), True, quiet=True)
            bad += not ok
        print(f"     {len(nums)} visible tagged numbers, {bad} with a failure; by file:",
              dict(Counter(s["source"].partition("#")[0] for s in nums)))
        partial = page.eval_on_selector_all("[data-metric]:not([data-value])", "els => els.filter(e => !e.dataset.raw || !e.dataset.source).length")
        check(f"{RUN}: [data-metric] numbers missing data-raw/data-source", partial, 0)

        marks = page.eval_on_selector_all("[data-value]", """els => els.map(e => { const r = e.getBoundingClientRect();
            const t = e.parentElement.getBoundingClientRect();
            return {run: e.dataset.run, metric: e.dataset.metric, value: e.dataset.value, label: e.dataset.label,
                    w: r.width, h: r.height, tw: t.width, vis: !e.closest('[hidden]')}; })""")
        marks = [m for m in marks if m["vis"]]
        mbad = 0
        for i, mk in enumerate(marks):
            tag = f"{RUN} mark[{i}] {mk['metric']}"
            ok = check(f"{tag}: attrs", all(mk[k] not in (None, "") for k in ("run", "metric", "value", "label")), True, quiet=True)
            ok &= check(f"{tag}: run", mk["run"], RUN, quiet=True)
            if mk["metric"].startswith("emotion."):
                fld = mk["metric"][len("emotion."):]
                fv, rv = (getpath(EM2, fld), REMF.get(fld, KeyError)) if RUN == "first100_v2" else (KeyError, KeyError)
            else:
                fv, rv = getpath(M1 if RUN == "first100_v1" else M2, mk["metric"]), RF.get(mk["metric"], KeyError)
            ok &= check(f"{tag}: value == file", float(mk["value"]), float(fv) if fv is not KeyError else float("nan"), quiet=True)
            ok &= check(f"{tag}: value == recomputed", float(mk["value"]), float(rv) if rv is not KeyError else float("nan"), quiet=True)
            if float(mk["value"]) > 0:
                ok &= check(f"{tag}: rendered size > 0", mk["w"] > 0 and mk["h"] > 0, True, quiet=True)
            mbad += not ok
        print(f"     {len(marks)} visible chart marks, {mbad} with a failure; groups:",
              dict(Counter(m["metric"].rsplit(".", 1)[0] if m["metric"].startswith("emotion.") else m["metric"].split(".")[0] for m in marks)))
        emo_sec_hidden = page.eval_on_selector("#sec-emotion", "e => e.hidden")
        check(f"{RUN}: emotion section hidden?", emo_sec_hidden, RUN == "first100_v1")
        if RUN == "first100_v2":
            bars = [m for m in marks if m["metric"].startswith(("emotion.llm_emotion_counts", "emotion.nrc_emotion_counts"))]
            mx = max(max(REM["llm_emotion_counts"].values()), max(REM["nrc_emotion_counts"].values()))
            exp_bars = sorted(f"emotion.{f}.{k}" for f in ("llm_emotion_counts", "nrc_emotion_counts") for k, v in REM[f].items() if v > 0)
            check("emotion bars present for every non-zero count", sorted(b["metric"] for b in bars), exp_bars)
            worst = max(abs(b["w"] / b["tw"] - float(b["value"]) / mx) for b in bars)
            check("emotion bar width/track == value/max (max abs error <= 0.01)", worst <= 0.01, True)
            print(f"     emotion bar width error max {worst:.4f}; min bar width px {min(b['w'] for b in bars):.1f}")
            cells = [m["metric"][len("emotion.crosstab_cells."):] for m in marks if m["metric"].startswith("emotion.crosstab_cells.")]
            check("cross-tab DOM order (rows=LLM, cols=NRC)", cells, [f"{a}->{b}" for a in LC for b in NC])
            ch = page.eval_on_selector_all(".xt-head", "els => els.map(e => e.textContent.trim())")
            rh = page.eval_on_selector_all(".xt-rowhead", "els => els.map(e => e.textContent.trim())")
            nm = lambda k: {"UNPARSED": "Unparsed", "TIE": "Tie", "NONE": "None"}.get(k, k)
            check("cross-tab column headers", ch, [nm(c) for c in NC])
            check("cross-tab row headers", rh, [nm(c) for c in LC])
            cl = [m["label"] for m in marks if m["metric"].startswith("emotion.crosstab_cells.")]
            check("cross-tab cell labels", cl, [f"Model: {nm(a)} · word list: {nm(b)}" for a in LC for b in NC])
            tiles = page.eval_on_selector_all("#sec-emotion .tile", "els => els.map(e => e.innerText.replace(/\\n/g,' | '))")
            print("     emotion tiles:", tiles)
            trs = page.eval_on_selector_all("#review-table tbody tr", """els => els.map(e => ({id: +e.dataset.reviewId, emo: e.dataset.emo,
                cells: [...e.children].map(td => td.innerText)}))""")
            tb = []
            for t in trs:
                r = REC[t["id"]]
                grp = "agree" if r["emotion_agree"] else {"TIE": "tie", "NONE": "none"}.get(r["nrc_emotion"], "differ")
                exp5 = r["llm_emotion"] or "—"
                c6 = t["cells"][6].split("\n")[0].strip()
                exp6 = {"TIE": "tie", "NONE": "none"}.get(r["nrc_emotion"], r["nrc_emotion"])
                tied_ok = r["nrc_emotion"] != "TIE" or " / ".join(r["nrc_tied"]) in t["cells"][6]
                same_ok = ("same as model" in t["cells"][6]) == r["emotion_agree"]
                if not (t["emo"] == grp and t["cells"][5].strip() == exp5 and c6 == exp6 and tied_ok and same_ok):
                    tb.append((t["id"], t["cells"][5:7], grp))
            check("review table emotion cells vs recomputation", (len(trs), tb), (100, []))
            exp_counts = Counter("agree" if r["emotion_agree"] else {"TIE": "tie", "NONE": "none"}.get(r["nrc_emotion"], "differ") for r in rows)
            for opt in ("agree", "differ", "tie", "none", "all"):
                page.select_option("#f-emo", opt)
                live = page.eval_on_selector("#shown-count", "e => [e.textContent, e.dataset.liveCount]")
                vis = page.eval_on_selector_all("#review-table tbody tr", "els => els.filter(e => !e.hidden).map(e => +e.dataset.reviewId)")
                exp = n if opt == "all" else exp_counts[opt]
                check(f"f-emo={opt}: live count == visible rows == recomputed", (live[0], int(live[1]), len(vis)), (str(exp), exp, exp))
                if opt == "differ":
                    check("f-emo=differ ids == divergent_review_ids", vis, REM["divergent_review_ids"])
        loose = page.evaluate(JS_WALK)
        print(f"     untagged visible digit text ({len(loose)}):", [(x["where"], x["text"][:60]) for x in loose])
    check("console/page errors", errs, [])
    check("non-file requests", reqs, [])
    br.close()

# ------------------------------------------------------------------ 6. written claims
print("== 6. written claims (step5_analysis.md, ISSUES.md)")
by = {p["review_id"]: p for p in P2}
c = lambda name, got, exp: check("claim: " + name, got, exp)
c("agreement all 20/100 20.0%", (ag["all_rows"]["agree"], ag["all_rows"]["n"], f"{100 * ag['all_rows']['rate']:.1f}"), (20, 100, "20.0"))
c("excl NONE 20/85 23.5%", (ag["excluding_none"]["agree"], ag["excluding_none"]["n"], f"{100 * ag['excluding_none']['rate']:.1f}"), (20, 85, "23.5"))
c("excl NONE+TIE 20/38 52.6%", (ag["excluding_none_and_tie"]["agree"], ag["excluding_none_and_tie"]["n"], f"{100 * ag['excluding_none_and_tie']['rate']:.1f}"), (20, 38, "52.6"))
c("no single answer 62 = TIE 47 + NONE 15", (nrc_c["TIE"] + nrc_c["NONE"], nrc_c["TIE"], nrc_c["NONE"]), (62, 47, 15))
c("45 of 47 ties, 95.7%", (lin, len(ties), f"{100 * lin / len(ties):.1f}"), (45, 47, "95.7"))
c("LLM counts", {k: v for k, v in llm_c.items()}, {"joy": 80, "trust": 9, "anger": 7, "anticipation": 3, "disgust": 1})
c("NRC counts", dict(nrc_c), {"TIE": 47, "joy": 22, "NONE": 15, "anticipation": 14, "sadness": 1, "trust": 1})
nz = {k: v for k, v in REM["crosstab_cells"].items() if v}
c("non-zero cross-tab cells", nz, {"joy->joy": 19, "joy->TIE": 44, "joy->NONE": 9, "joy->anticipation": 8,
                                   "anger->anticipation": 3, "anger->joy": 1, "anger->sadness": 1, "anger->trust": 1, "anger->NONE": 1,
                                   "trust->NONE": 5, "trust->anticipation": 2, "trust->joy": 1, "trust->TIE": 1,
                                   "anticipation->TIE": 2, "anticipation->anticipation": 1, "disgust->joy": 1})
c("divergent 18 rows", len(REM["divergent_review_ids"]), 18)
anger = [(i, by[i]["truth"], by[i]["rating"]) for i in by if REC[i]["llm_emotion"] == "anger"]
print("     LLM anger rows (id, truth, rating):", anger)
c("'all 7 anger rows NEGATIVE-truth or complaint' -> NEGATIVE-truth count", sum(t == "NEGATIVE" for _, t, _ in anger), 6)


def nzs(i):
    return {k: v for k, v in REC[i]["nrc_scores"].items() if v}


def hitc(i):
    return Counter((h[0], h[1], tuple(h[2])) for h in REC[i]["nrc_hits"])


c("51 LLM anger / NRC anticipation", (REC[51]["llm_emotion"], REC[51]["nrc_emotion"]), ("anger", "anticipation"))
c("51 scores", nzs(51), {"anticipation": 3, "joy": 2, "surprise": 2, "trust": 1})
print("     51 hits:", dict(hitc(51)))
c("32 LLM anger / NRC sadness", (REC[32]["llm_emotion"], REC[32]["nrc_emotion"]), ("anger", "sadness"))
c("32 scores", nzs(32), {"sadness": 2, "anger": 1, "trust": 1})
print("     32 hits:", dict(hitc(32)))
c("63 LLM anger / NRC trust", (REC[63]["llm_emotion"], REC[63]["nrc_emotion"]), ("anger", "trust"))
c("63 scores", nzs(63), {"trust": 6, "anticipation": 3, "fear": 2, "joy": 2, "sadness": 2, "surprise": 1})
print("     63 hits:", dict(hitc(63)))
c("17 LLM anger / NRC anticipation", (REC[17]["llm_emotion"], REC[17]["nrc_emotion"]), ("anger", "anticipation"))
c("17 scores", nzs(17), {"anticipation": 9, "joy": 4, "surprise": 3, "trust": 2, "anger": 1})
print("     17 hits:", dict(hitc(17)))
c("17 hits exactly = claimed list 'gift x3, recipient x2, time, times->time, mail; complaint'",
  sorted(h[1] for h in REC[17]["nrc_hits"]), sorted(["gift"] * 3 + ["recipient"] * 2 + ["time", "time", "mail", "complaint"]))
c("17 anticipation from claimed topic words only (gift3+recipient2+time2+mail1)", 3 + 2 + 2 + 1, REC[17]["nrc_scores"]["anticipation"])
c("17 'loved' in text, not in hits", ("loved" in by[17]["text"], any(h[0] == "loved" for h in REC[17]["nrc_hits"])), (True, False))
c("46 LLM disgust / NRC joy; sentiment mislabeled NEGATIVE", (REC[46]["llm_emotion"], REC[46]["nrc_emotion"], pred2[46]), ("disgust", "joy", "NEGATIVE"))
c("46 scores", nzs(46), {"joy": 2, "anticipation": 1, "surprise": 1, "trust": 1})
print("     46 hits:", dict(hitc(46)))
c("93 LLM joy / NRC anticipation", (REC[93]["llm_emotion"], REC[93]["nrc_emotion"]), ("joy", "anticipation"))
c("93 scores", nzs(93), {"anticipation": 4, "joy": 3, "surprise": 2, "anger": 1, "trust": 1})
print("     93 hits:", dict(hitc(93)))
c("93 in divergent list, and all 6 cited", all(i in REM["divergent_review_ids"] for i in (51, 32, 63, 17, 46, 93)), True)
none_ids = [r["review_id"] for r in rows if r["nrc_emotion"] == "NONE"]
easy = [i for i in none_ids if re.search(r"\beasy\b", (by[i]["title"] + " " + by[i]["text"]).lower())]
print("     NONE ids:", none_ids)
print("     NONE rows with 'easy':", easy, [(i, by[i]["title"], by[i]["text"][:50]) for i in easy])
c("8 'easy' NONE rows = 31,49,55,67,68,78,97,98", sorted(easy), [31, 49, 55, 67, 68, 78, 97, 98])
c("45 emoji-only; 15 'Card did not work!!!!'", (by[45]["title"], by[45]["text"], REC[45]["nrc_emotion"], by[15]["text"], REC[15]["nrc_emotion"]),
  ("👍", "👍", "NONE", "Card did not work!!!!", "NONE"))
print("     review 15 title:", repr(by[15]["title"]), "blanked:", bool(STAR.fullmatch(by[15]["title"])))
c("NONE column: LLM joy 9, trust 5, anger 1", dict(Counter(REC[i]["llm_emotion"] for i in none_ids)), {"joy": 9, "trust": 5, "anger": 1})
gift_all = sum(h[1] == "gift" for r in rows for h in r["nrc_hits"])
gift_tok = sum(h[0] == "gift" for r in rows for h in r["nrc_hits"])
gift_tie = sum(h[1] == "gift" for r in ties for h in r["nrc_hits"])
good_tie = sum(h[1] == "good" for r in ties for h in r["nrc_hits"])
print(f"     gift hits (lexicon word) all={gift_all} (token 'gift' only={gift_tok}); in ties={gift_tie}; good in ties={good_tie}")
c("'gift' hit 104 times", gift_all, 104)
c("'gift' 40 times inside tie rows", gift_tie, 40)
c("'good' 29 times inside tie rows", good_tie, 29)
ts = Counter(tuple(r["nrc_tied"]) for r in ties)
print("     tied sets:", ts.most_common(5))
c("tied sets {ant,joy,sur} 15, {ant,joy} 14, {ant,joy,sur,trust} 13",
  (ts[("anticipation", "joy", "surprise")], ts[("anticipation", "joy")], ts[("anticipation", "joy", "surprise", "trust")]), (15, 14, 13))
c("8 reviews have 'gift' as only hit word", sum(1 for r in rows if r["nrc_hits"] and {h[1] for h in r["nrc_hits"]} == {"gift"}), 8)
c("lexicon 14,154 / 4,454", (len(all_words), len(LEX)), (14154, 4454))
c("batch 93% positive", R2["truth_distribution"]["share"]["POSITIVE"], 0.93)
c("review 74 'great buy' -> NONE; great/easy/works not in lexicon",
  (REC[74]["nrc_emotion"], "great" in LEX, "easy" in LEX, "works" in LEX, "work" in LEX), ("NONE", False, False, False, False))
c("hit/fits/credit/cheer tags", (sorted(LEX["hit"]), sorted(LEX["fits"]), sorted(LEX["credit"]), sorted(LEX["cheer"])),
  (["anger"], ["anger"], ["trust"], ["anticipation", "joy", "surprise", "trust"]))

print()
print(f"TOTAL FAILS: {len(FAILS)}", FAILS[:60])
