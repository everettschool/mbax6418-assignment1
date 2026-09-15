from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path(__file__).resolve().parent
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1440,"height":900})
    pg.goto((OUT/"index_recolored.html").as_uri())
    for run in ["balanced150_v3","first100_v1"]:
        pg.click(f'[data-run-tab="{run}"]')
        print(run, pg.evaluate("""()=>{const o=[];for(const e of document.querySelectorAll('*')){const cs=getComputedStyle(e);for(const p of ['color','backgroundColor','borderTopColor','borderBottomColor']){if(cs[p]==='rgb(0, 0, 0)')o.push(e.tagName+'.'+e.className+'#'+e.id+' '+p)}}return [...new Set(o)].slice(0,15)}"""))
    # contrast on-fill text in dark cells original page
    pg2=b.new_page(viewport={"width":1440,"height":900}); pg2.goto((OUT.parents[1]/"dashboard/index.html").as_uri())
    print(pg2.evaluate("""()=>[...document.querySelectorAll('#sec-confusion .cell')].map(c=>[c.dataset.label,c.dataset.value,getComputedStyle(c).backgroundColor,getComputedStyle(c.querySelector('.count')).color])"""))
    print(pg2.evaluate("""()=>[...document.querySelectorAll('.cbar')].map(c=>c.getBoundingClientRect().width+' '+c.querySelector('.track').getBoundingClientRect().width)"""))
    b.close()
