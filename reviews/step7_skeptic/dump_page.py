"""Dump visible text of #sec-verdict, #sec-describe, #sec-confusion, #sec-classes, #sec-emotion per run, plus mark geometry."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
runs = [r["run"] for r in json.loads((ROOT/"dashboard/manifest.json").read_text())["runs"]]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1440,"height":900})
    pg.goto((ROOT/"dashboard/index.html").resolve().as_uri())
    print("default run:", pg.get_attribute("body","data-run"), "tab order:", runs)
    for r in runs:
        pg.click(f'[data-run-tab="{r}"]')
        print("\n#####", r)
        order = pg.eval_on_selector_all("main > section, main > div, main > p", "els=>els.map(e=>e.id||e.className)")
        print("order:", order)
        for s in ["run-blurb","sec-verdict","sec-describe","sec-confusion","sec-classes","sec-emotion"]:
            el = pg.query_selector("#"+s)
            if el and el.is_visible():
                print(f"--- {s}\n" + el.inner_text())
        geo = pg.eval_on_selector_all("#sec-describe [data-value], #sec-classes [data-value]", "els=>els.map(e=>{const r=e.getBoundingClientRect();return [e.dataset.metric,e.dataset.value,Math.round(r.width*10)/10,Math.round(r.height*10)/10]})")
        print("marks:", geo)
        pg.screenshot(path=str(OUT/f"{r}_full.png"), full_page=True)
        el = pg.query_selector("#sec-describe"); el.screenshot(path=str(OUT/f"{r}_describe.png"))
    pg.set_viewport_size({"width":400,"height":900})
    for r in runs:
        pg.click(f'[data-run-tab="{r}"]')
        pg.query_selector("#sec-describe").screenshot(path=str(OUT/f"{r}_describe_400.png"))
        geo = pg.eval_on_selector_all("#sec-describe [data-value], #sec-classes [data-value]", "els=>els.map(e=>{const r=e.getBoundingClientRect();return [e.dataset.metric,e.dataset.value,Math.round(r.width*10)/10]})")
        print("400px", r, [g for g in geo if g[2] < 4])
    b.close()
