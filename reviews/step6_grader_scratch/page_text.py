from playwright.sync_api import sync_playwright
from pathlib import Path
p=Path('dashboard/index.html').resolve()
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page(viewport={'width':1440,'height':900})
    pg.goto(p.as_uri()+'#run=balanced150_v3'); pg.wait_for_timeout(800)
    t=pg.inner_text('body')
    Path('reviews/step6_grader_scratch/balanced_text.txt').write_text(t)
    pg.screenshot(path='reviews/step6_grader_scratch/balanced_full.png',full_page=True)
    pg.screenshot(path='reviews/step6_grader_scratch/balanced_fold.png')
    b.close()
