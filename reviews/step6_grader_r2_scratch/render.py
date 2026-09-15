import pathlib
from playwright.sync_api import sync_playwright
root = pathlib.Path(__file__).resolve().parents[2]
out = pathlib.Path(__file__).parent
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1440,"height":900})
    pg.goto((root/"dashboard/index.html").as_uri())
    names = [t.get_attribute("data-run-tab") for t in pg.query_selector_all("[data-run-tab]")]
    for name in names:
        pg.click(f'[data-run-tab="{name}"]'); pg.wait_for_timeout(400)
        txt = pg.inner_text("body")
        (out/f"text_{name}.txt").write_text(txt)
        print("==", name, len(txt))
        for key in ["Stars in this sample", "precision", "Re-weighted", "worth", "matches the stars", "three classes; answer key"]:
            for line in txt.splitlines():
                if key in line: print("  ", line[:400])
    b.close()
