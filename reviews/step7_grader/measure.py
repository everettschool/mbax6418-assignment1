"""Step 7 grader: measure descriptive-layer marks in the built page (read-only)."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "dashboard" / "index.html"
OUT = Path(__file__).resolve().parent
RUNS = ["balanced150_v3", "first100_v3", "first100_v2", "first100_v1"]

JS = """() => {
  const sec = document.getElementById('sec-describe');
  const out = {order: [...document.querySelectorAll('main section, body section')].filter(s=>!s.hidden)
      .map(s => [s.id, Math.round(s.getBoundingClientRect().top + scrollY)]), bars: []};
  sec.querySelectorAll('[data-value]').forEach(b => {
    const r = b.getBoundingClientRect(), t = b.parentElement.getBoundingClientRect();
    const row = b.closest('.hbar, .gbar');
    const labels = [...row.querySelectorAll('[data-raw]')].map(s => s.getBoundingClientRect());
    const overlap = labels.some(l => !(l.right <= r.left || l.left >= r.right || l.bottom <= r.top || l.top >= r.bottom));
    out.bars.push({metric: b.dataset.metric, run: b.dataset.run, value: +b.dataset.value, w: r.width, h: r.height,
      track: t.width, style: b.getAttribute('style'), overlap, aria: b.getAttribute('aria-label'), title: b.title,
      role: b.getAttribute('role')});
  });
  out.text = sec.innerText;
  out.classesText = document.getElementById('sec-classes').innerText;
  return out; }"""

res = {}
with sync_playwright() as p:
    br = p.chromium.launch()
    for width in (1440, 400):
        pg = br.new_page(viewport={"width": width, "height": 900})
        pg.goto(PAGE.as_uri()); pg.wait_for_load_state("load")
        for run in RUNS:
            pg.click(f'[data-run-tab="{run}"]')
            d = pg.evaluate(JS)
            res[f"{run}@{width}"] = d
            pg.locator("#sec-describe").screenshot(path=str(OUT / f"describe_{run}_{width}.png"))
            if width == 1440:
                pg.screenshot(path=str(OUT / f"full_{run}.png"), full_page=True)
        pg.close()
    pg = br.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    pg.goto(PAGE.as_uri()); pg.wait_for_load_state("load")
    pg.locator("#sec-describe").screenshot(path=str(OUT / "describe_dark.png"))
    br.close()
(OUT / "measure.json").write_text(json.dumps(res, indent=1))

for key, d in res.items():
    print("==", key, "order:", d["order"])
    tracks = {}
    for b in d["bars"]:
        grp = b["metric"].rsplit(".", 1)[0]
        tracks.setdefault(grp, set()).add(round(b["track"], 1))
        print(f"  {b['metric']:40s} v={b['value']:<7} w={b['w']:7.2f} track={b['track']:6.1f} ratio={b['w']/b['track']:.4f} "
              f"overlap={b['overlap']} aria={b['aria']!r} style={b['style']}")
    print("  track widths per chart:", {k: sorted(v) for k, v in tracks.items()})
