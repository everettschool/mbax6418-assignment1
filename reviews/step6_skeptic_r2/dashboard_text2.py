"""Dashboard text per run with every <tbody> removed (headless Chromium, tabs clicked)."""
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[2]; OUT = Path(__file__).resolve().parent
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto((ROOT / "dashboard" / "index.html").as_uri())
    for run in ["balanced150_v3", "first100_v3", "first100_v1"]:
        pg.click(f'[data-run-tab="{run}"]'); pg.wait_for_timeout(500)
        txt = pg.evaluate("""() => { const c = document.body.cloneNode(true);
            c.querySelectorAll('tbody, script, style').forEach(e => e.remove()); return c.innerText; }""")
        (OUT / f"dashboard_{run}.txt").write_text(txt); print(run, len(txt))
    b.close()
