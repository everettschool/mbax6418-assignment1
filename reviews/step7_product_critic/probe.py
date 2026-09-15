"""Product-critic probe: screenshots, collapsed marks, filter counts, recolor test. Read-only on project files."""
import json, re, shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SRC = ROOT / "dashboard/index.html"
RUNS = ["balanced150_v3", "first100_v3", "first100_v2", "first100_v1"]

# ---- recolored copy: edit only the :root block ----
html = SRC.read_text()
m = re.search(r":root\s*\{[^}]*\}", html)
root_block = m.group(0)
NEW = {
    "--paper": "#0f1720", "--surface": "#16212d", "--surface-2": "#1f2c3a", "--ink": "#eef2f6",
    "--ink-2": "#b7c2cd", "--ink-3": "#8593a1", "--rule": "#2a3847", "--axis": "#3b4b5c", "--on-fill": "#0f1720",
    "--pos": "#00a36c", "--neu": "#e0c341", "--neg": "#ff4f79", "--unparsed": "#29b6f6",
    "--hit": "#7fd1ae", "--miss": "#ff00ff", "--llm": "#00ffff", "--lex": "#ffa500",
}
new_block = root_block
for k, v in NEW.items():
    new_block = re.sub(re.escape(k) + r":\s*#[0-9a-fA-F]{3,8}", f"{k}: {v}", new_block)
recolored = OUT / "index_recolored.html"
recolored.write_text(html.replace(root_block, new_block, 1))
print("root blocks in file:", len(re.findall(r":root\s*\{", html)))

JS_COLORS = r"""
() => {
  const hexish = new Set();
  const out = {};
  const all = [...document.querySelectorAll('*')];
  for (const e of all) {
    const cs = getComputedStyle(e);
    for (const p of ['color','backgroundColor','borderTopColor','borderBottomColor']) {
      const v = cs[p];
      if (v && v !== 'rgba(0, 0, 0, 0)') hexish.add(v);
    }
  }
  return [...hexish].sort();
}
"""

JS_COLLAPSE = r"""
() => {
  const bad = [];
  for (const e of document.querySelectorAll('[data-value]')) {
    const r = e.getBoundingClientRect();
    if (e.closest('[hidden]')) continue;
    const v = Number(e.dataset.value);
    if (v > 0 && (r.width < 2 || r.height < 2)) bad.push({metric: e.dataset.metric, v, w: r.width, h: r.height});
  }
  return bad;
}
"""

JS_OVERLAP = r"""
() => {
  // text overflowing its box horizontally (clipped labels)
  const out = [];
  for (const e of document.querySelectorAll('.tile-value, .tile-label, .cbar-text, .chip, .xt-head, .cm-colhead, .hero-value, .verdict-head, h1, .run-tab, .gbar .v, .starbars .pct')) {
    if (e.closest('[hidden]')) continue;
    if (e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible') out.push({cls: e.className, text: e.textContent.slice(0,40), sw: e.scrollWidth, cw: e.clientWidth});
  }
  return out;
}
"""

def count_rows(run, f):
    rows = [json.loads(l) for l in (ROOT / f"runs/{run}/predictions.jsonl").read_text().splitlines() if l.strip()]
    n = 0
    for r in rows:
        truth, pred = r.get("truth"), r.get("prediction")
        ok = pred == truth
        if f.get("result") == "match" and not ok: continue
        if f.get("result") == "miss" and ok: continue
        if "truth" in f and truth != f["truth"]: continue
        if "pred" in f and pred != f["pred"]: continue
        n += 1
    return n, len(rows), (list(rows[0].keys()) if rows else [])

with sync_playwright() as p:
    b = p.chromium.launch()
    for (w, h) in [(1440, 900), (1280, 800), (400, 860)]:
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.goto(SRC.as_uri())
        for run in RUNS:
            pg.click(f'[data-run-tab="{run}"]')
            pg.wait_for_timeout(150)
            pg.evaluate("window.scrollTo(0,0)")
            tag = f"{run}_{w}"
            pg.screenshot(path=str(OUT / f"fold_{tag}.png"))
            if run in ("balanced150_v3", "first100_v1") or w == 1440:
                pg.screenshot(path=str(OUT / f"full_{tag}.png"), full_page=True)
            print(tag, "collapsed:", pg.evaluate(JS_COLLAPSE), "clipped:", pg.evaluate(JS_OVERLAP),
                  "scrollW:", pg.evaluate("document.documentElement.scrollWidth"))
            # what is above the fold
            info = pg.evaluate("""() => { const r = s => { const e=document.querySelector(s); if(!e) return null; const b=e.getBoundingClientRect(); return [Math.round(b.top), Math.round(b.bottom)]; };
               return {hero: r('.hero-value'), verdictHead: r('#verdict-head'), tiles: r('.tiles'), describe: r('#sec-describe'), confusion: r('#sec-confusion'), blurb: r('#run-blurb')}; }""")
            print("   fold positions:", info)
        pg.close()

    # filter checks on laptop
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(SRC.as_uri())
    for run in RUNS:
        pg.click(f'[data-run-tab="{run}"]')
        cases = [{}, {"result": "miss"}, {"result": "match"}, {"truth": "NEUTRAL"}, {"truth": "NEUTRAL", "pred": "NEGATIVE"},
                 {"truth": "NEGATIVE", "pred": "NEUTRAL"}, {"result": "miss", "truth": "POSITIVE"}, {"pred": "UNPARSED"}]
        for f in cases:
            pg.click("#f-reset")
            ok = True
            for key, sel in (("result", "#f-result"), ("truth", "#f-truth"), ("pred", "#f-pred")):
                if key in f:
                    opts = pg.eval_on_selector(sel, "s => [...s.options].map(o=>o.value)")
                    if f[key] not in opts: ok = False; break
                    pg.select_option(sel, f[key])
            if not ok:
                print(run, f, "option not offered"); continue
            shown = int(pg.inner_text("#shown-count").replace(",", ""))
            visible = pg.evaluate("[...document.querySelectorAll('#review-table tbody tr')].filter(t=>!t.hidden).length")
            exp, total, keys = count_rows(run, f)
            print(run, f, "count", shown, "visible", visible, "expected", exp, "OK" if shown == visible == exp else "MISMATCH")
        # heatmap click -> filter
        cell = pg.query_selector('#sec-confusion .cell.clickable:not(.dark)') or pg.query_selector('#sec-confusion .cell.clickable')
        cell.click(); pg.wait_for_timeout(600)
        print(run, "cell click ->", cell.get_attribute("data-label"), cell.get_attribute("data-value"), "count", pg.inner_text("#shown-count"),
              "result sel", pg.eval_on_selector("#f-result", "s=>s.value"))
        # search then switch run: do filters persist / count reset?
        pg.fill("#f-search", "scam"); pg.wait_for_timeout(100)
        print(run, "search scam", pg.inner_text("#shown-count"), "of", pg.inner_text("#row-count"))
    # emotion filter options for runs with emotion
    pg.click('[data-run-tab="balanced150_v3"]')
    print("balanced has f-emo:", pg.query_selector("#f-emo") is not None)
    pg.close()

    # recolor test
    res = {}
    for label, path in (("orig", SRC), ("recolored", recolored)):
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.goto(path.as_uri())
        cols = set()
        for run in RUNS:
            pg.click(f'[data-run-tab="{run}"]'); pg.wait_for_timeout(100)
            cols |= set(pg.evaluate(JS_COLORS))
            # also hover color / tooltip, focus outline not captured; svg fills none
        res[label] = cols
        pg.click('[data-run-tab="balanced150_v3"]'); pg.evaluate("window.scrollTo(0,0)")
        pg.screenshot(path=str(OUT / f"recolor_{label}_full.png"), full_page=True)
        # sample specific elements
        sample = pg.evaluate("""() => { const g=(s,p)=>{const e=document.querySelector(s); return e? getComputedStyle(e)[p]:null};
          return {body:g('body','backgroundColor'), card:g('.card','backgroundColor'), h1:g('h1','color'),
            miss_cell:g('#sec-confusion .cell.clickable','backgroundColor'), seg:g('.cbar .seg','backgroundColor'),
            starbar:g('.starbars .bar','backgroundColor'), chip_dot: getComputedStyle(document.querySelector('.chip'),'::before').backgroundColor,
            select:g('#f-result','backgroundColor'), select_color:g('#f-result','color'), search_color:g('#f-search','color'),
            scrollbar:g('.table-wrap','scrollbarColor'), colorScheme:g('html','colorScheme'),
            miss_row: g('tr.is-miss td','backgroundColor'), th: g('th','backgroundColor'), tip: g('#tip','backgroundColor')}; }""")
        print(label, "sample:", sample)
        pg.close()
    orig_vals = {v.lower() for v in NEW}  # unused
    survivors = res["orig"] & res["recolored"]
    print("colors unchanged after recolor:", sorted(survivors))
    b.close()
