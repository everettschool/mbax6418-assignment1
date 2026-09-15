"""Measure the pixel scale (px per unit) of every bar chart that claims a shared scale, per run and viewport."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[2]
runs = [r["run"] for r in json.loads((ROOT/"dashboard/manifest.json").read_text())["runs"]]
JS = """() => {
 const out = {};
 const px = (sel, valFn) => [...document.querySelectorAll(sel)].map(b => {
   const t = b.closest('.htrack'); return [b.dataset.metric, +b.dataset.value, +b.getBoundingClientRect().width.toFixed(1), +t.getBoundingClientRect().width.toFixed(1)]; });
 const blocks = document.querySelectorAll('#sec-describe .starbars');
 out.file = px('#sec-describe .starbars:nth-of-type(1) .bar');
 out.file = [...blocks[0].querySelectorAll('.bar')].map(b=>[b.dataset.metric,+b.dataset.value,+b.getBoundingClientRect().width.toFixed(1),+b.closest('.htrack').getBoundingClientRect().width.toFixed(1)]);
 out.sample = [...blocks[1].querySelectorAll('.bar')].map(b=>[b.dataset.metric,+b.dataset.value,+b.getBoundingClientRect().width.toFixed(1),+b.closest('.htrack').getBoundingClientRect().width.toFixed(1)]);
 out.paired = px('#sec-describe .grouped .bar');
 out.emo = px('#sec-emotion .pairbars .bar');
 out.cbar = [...document.querySelectorAll('#sec-classes .cbar')].map(r=>{const t=r.querySelector('.track');return [r.querySelector('.chip').textContent, +t.getBoundingClientRect().width.toFixed(1), [...t.querySelectorAll('.seg')].map(s=>[s.dataset.metric,+s.dataset.value,+s.getBoundingClientRect().width.toFixed(1)])]});
 return out; }"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1440,"height":900})
    pg.goto((ROOT/"dashboard/index.html").resolve().as_uri())
    for w in (1440, 400):
        pg.set_viewport_size({"width":w,"height":900})
        for r in runs:
            pg.click(f'[data-run-tab="{r}"]')
            o = pg.evaluate(JS)
            print(f"\n== {r} @ {w}px")
            dist = json.loads((ROOT/"runs/rating_distribution.json").read_text())
            m = json.loads((ROOT/f"runs/{r}/metrics.json").read_text())
            for name, rows, share in (("whole file", o["file"], dist["rating_share"]), ("sample", o["sample"], m["sample_rating_share"])):
                for met, v, bw, tw in rows:
                    s = share[met.split(".")[-1]]
                    print(f"  {name:10s} {met:24s} share {100*s:5.1f}%  bar {bw:6.1f}px  track {tw:6.1f}px  => px per 1% = {bw/(100*s):.2f}")
            for met, v, bw, tw in o["paired"]:
                print(f"  paired {met:42s} v={v:3g} bar {bw:6.1f} track {tw:6.1f} px/unit {bw/v:.3f}")
            for met, v, bw, tw in o["emo"]:
                print(f"  emo {met:42s} v={v:3g} bar {bw:6.1f} track {tw:6.1f} px/unit {bw/v:.3f}")
            for row in o["cbar"]:
                print("  cbar", row)
    b.close()
