import pathlib, json
from playwright.sync_api import sync_playwright
p = pathlib.Path("dashboard/index.html").resolve()
out = pathlib.Path("reviews/step5_grader_r2_scratch")
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width":1440,"height":900})
    errs=[]; pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
    reqs=[]; pg.on("request", lambda r: reqs.append(r.url) if not r.url.startswith("file:") else None)
    pg.goto(p.as_uri()); pg.wait_for_timeout(500)
    tabs = pg.locator("[role=tab], .tab, button").all_inner_texts()
    print("buttons:", [t for t in tabs if t.strip()][:12])
    # switch to v2 tab if needed
    for loc in pg.locator("[role=tab], button").all():
        t = loc.inner_text()
        if "emotion" in t.lower() or "v2" in t.lower():
            loc.click(); pg.wait_for_timeout(300); print("clicked", repr(t)); break
    sec = pg.locator("#sec-emotion")
    print("visible:", sec.is_visible())
    if sec.is_visible():
        sec.screenshot(path=str(out/"emotion_1440.png"))
        print(sec.inner_text()[:2500])
        # overflow check for headers
        ov = pg.evaluate("""() => [...document.querySelectorAll('#sec-emotion *')].filter(e=>e.scrollWidth>e.clientWidth+1 && getComputedStyle(e).overflow!=='visible').map(e=>e.className+':'+e.textContent.slice(0,30))""")
        print("clipped:", ov[:10])
    pg.set_viewport_size({"width":400,"height":900}); pg.wait_for_timeout(300)
    if sec.is_visible():
        sec.screenshot(path=str(out/"emotion_400.png"))
        print("page hscroll at 400:", pg.evaluate("document.documentElement.scrollWidth"), )
    print("console errors:", errs, "external requests:", reqs)
    b.close()
