"""Read the built dashboard text per run by clicking tabs (headless Chromium)."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
url = (ROOT / "dashboard" / "index.html").as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(url)
    for run in ["balanced150_v3", "first100_v3"]:
        pg.click(f'[data-run-tab="{run}"]')
        pg.wait_for_timeout(400)
        # text outside the review table only
        txt = pg.evaluate("""() => {
            const clone = document.body.cloneNode(true);
            clone.querySelectorAll('table tbody tr[data-review-id]').forEach(e => e.remove());
            return clone.innerText; }""")
        (OUT / f"dashboard_{run}.txt").write_text(txt)
        print(f"== {run}: {len(txt)} chars saved")
    b.close()
