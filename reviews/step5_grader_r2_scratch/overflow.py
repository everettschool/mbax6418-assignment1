import pathlib
from playwright.sync_api import sync_playwright
p = pathlib.Path("dashboard/index.html").resolve()
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width":400,"height":900})
    pg.goto(p.as_uri()); pg.wait_for_timeout(400)
    pg.get_by_text("First 100 · two classes + emotion").click(); pg.wait_for_timeout(300)
    print(pg.evaluate("""() => {
      const vw = document.documentElement.clientWidth;
      const hits = [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > vw + 1)
        .filter(e => { let a = e.parentElement; while (a) { const o = getComputedStyle(a).overflowX; if (o==='auto'||o==='scroll'||o==='hidden') return false; a = a.parentElement; } return true; });
      const top = hits.filter(e => !hits.includes(e.parentElement));
      return {vw, scrollWidth: document.documentElement.scrollWidth,
        offenders: top.slice(0,8).map(e => ({tag:e.tagName, id:e.id, cls:e.className, section:(e.closest('section')||{}).id, right:Math.round(e.getBoundingClientRect().right)}))};
    }"""))
    b.close()
