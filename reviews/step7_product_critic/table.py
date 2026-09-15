from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
with sync_playwright() as p:
    b=p.chromium.launch()
    for w,h in [(1440,900),(1280,800)]:
        pg=b.new_page(viewport={"width":w,"height":h}); pg.goto((ROOT/"dashboard/index.html").as_uri())
        for run in ["balanced150_v3","first100_v3","first100_v2","first100_v1"]:
            pg.click(f'[data-run-tab="{run}"]')
            r=pg.evaluate("""()=>{const t=document.querySelector('.table-wrap');const th=[...document.querySelectorAll('#review-table th')];const rv=th[th.length-1].getBoundingClientRect();const tr=t.getBoundingClientRect();
              return {wrapClient:t.clientWidth, tableScroll:t.scrollWidth, reviewColLeft:Math.round(rv.left-tr.left), reviewColWidth:Math.round(rv.width), visibleOfReview:Math.round(Math.max(0,tr.right-rv.left))}}""")
            print(w,run,r)
        # filters persist across run switch?
        pg.click('[data-run-tab="balanced150_v3"]'); pg.select_option('#f-result','miss'); pg.click('[data-run-tab="first100_v3"]')
        print(w,"after switch f-result=",pg.eval_on_selector('#f-result','s=>s.value'),"count",pg.inner_text('#shown-count'))
        pg.close()
    b.close()
