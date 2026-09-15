# Step 7 — Product Critic review, round 2 (complete dashboard)

Scope: `dashboard/index.html`, the page as built, checked against `dashboard/template.html`. The built page is the template with only the data slot filled (prefix/suffix check: `prefix match True suffix match True`). I checked it in headless Chromium at 1440×900, 1280×800 and 400 px, on all four run tabs. Scripts, outputs, recolored copies and screenshots are in `reviews/step7_product_critic_r2/`: `probe.py` → `probe_out.txt`, `gbar.py` → `gbar_out.txt`, `dark_sober.py` → `dark_sober_out.txt`, `table_width.py` → `table_width_out.txt`, `index_dark.html`, `index_brand.html`, `index_dark_sober.html`, plus `*.png`.

## Checks that passed

**Round-1 findings.** Every round-1 finding is fixed in the page as built:
- The title and review column is fully visible at laptop width: 320 of 320 px on balanced, 342 px on the other runs.
- Heatmap text color now follows the fill's luminance. With the shipped palette the lowest cell contrast is 5.42:1.
- Color words are gone from the copy ("see key").
- The blurb is plain language: "50 drawn at random from each star class across the whole file (seed 42)".
- The verdict now names the top mistake: "Most common mistake: Neutral reviews answered Negative, 25 of 50 (50.0%)". It sits at y=352–419 on the first laptop screen.
- The all-zero Unparsed column and row are gone.
- At 400 px the tabs are one scrolling row, and the active tab stays scrolled into view.
- `color-scheme` is now in `:root`.

**Filters and live count.** 116 filter combinations checked against my own counts from `runs/*/predictions.jsonl`: `filter cases: 116, mismatches: 0`. The combinations cover result, answer key × model, all emotion groups and search, and include the empty-state message. Clicking any heatmap cell gives the matching count, and filters reset when switching runs.

**Recoloring from the one `:root` block.**
- A dark palette changes every computed color on the page: `computed colors present in both orig and dark: []`. It also switches the form controls (`colorScheme dark`, select `rgb(22, 33, 45)`).
- A light brand palette keeps every heatmap cell at 5.23:1 or better.

**Collapsed marks, page width, verifier.**
- `JS_COLLAPSE` (any value above 0 drawn under 2 px) finds nothing on 12 run×width combinations.
- Page `scrollWidth` equals the viewport at all three widths.
- No leaf text is clipped, and nothing sticks out of its card.
- Rerunning `src/verify_dashboard.py` gives `4283 checks, 0 failures / PASS`.

**Look.** The warm paper palette, the one type family, and the slate-right / amber-wrong coding across every chart hold together. Nothing looks like a default chart library (`full_balanced150_v3_1440.png`).

## Findings

MAJOR — `dashboard/template.html` `.gbar { grid-template-columns: 40px minmax(0, 1fr) 3.5ch 15ch }`, the chart "Stars' answer vs the model's answer, per class" (`renderDescribe` → `starsLine` / `modelLine`), at both laptop widths — **What is wrong:** the round-1 fix added a fixed 15ch "48 right · 9 wrong" column inside a column that is only 331 px wide. That leaves the bar track 27.7 px wide, so this chart has effectively collapsed on a laptop screen. Most marks are pinned at the 2 px `min-width` instead of drawn to scale:
- On `first100_v3`, the Stars Neutral 2, Stars Negative 5, Model Negative right 5 and wrong 2 marks all render at exactly 2 px, so 5 and 2 look the same.
- On the default balanced run, Negative "Stars 50 vs Model 70" differs by 7.9 px. The Neutral wrong 6 segment is pinned at 2 px.

This is the label/positioning collapse Step 7 warns about. The chart is meant to make over- and under-prediction visible at a glance. It passes `verify_dashboard.py` and my collapse probe only because the 2 px floor hides the problem. — **Evidence:** `.venv/bin/python reviews/step7_product_critic_r2/gbar.py`:
- `1440 balanced150_v3 {'classCol': 331.3, 'gbarTracks': [27.7, ...], 'gbarMarks': [['Stars · Positive', 50, 19.8], ['Model said Positive, right', 48, 17.3], ['Model said Positive, wrong', 9, 3.3], ['Stars · Neutral', 50, 19.8], ['Model said Neutral, right', 17, 5.1], ['Model said Neutral, wrong', 6, 2], ['Stars · Negative', 50, 19.8], ['Model said Negative, right', 45, 16.5], ['Model said Negative, wrong', 25, 9.2]] ...}`
- `1440 first100_v3 {... ['Stars · Neutral', 2, 2], ['Model said Neutral, wrong', 2, 2], ['Stars · Negative', 5, 2], ['Model said Negative, right', 5, 2], ['Model said Negative, wrong', 2, 2]]}`
- The same numbers at 1280. At 400 px the track is 156.5 px and the bars read correctly.
- Screenshot: `classblock_1440.png` shows stubs about 20–28 px long.

— **Suggested fix:**
- Move the "N right · N wrong" detail onto its own line under the Model bar, as the ≤560 px rule already does. Or give this chart the full card width: a row of its own below the two star charts, instead of a third of a 3-column grid.
- Aim for a track of at least 150 px at 1280.
- Add a check to `verify_dashboard.py` that fails when a mark's rendered width is more than 1 px off `track × value / scale max`. That catches marks pinned at the 2 px floor, not just marks under 2 px.

MINOR — `dashboard/template.html` `:root` comment `--on-fill: #ffffff; /* text on dark fills */` together with `inkCells` — **What is wrong:** readable heatmap text after a dark recolor depends on an unstated rule: `--on-fill` must be the opposite of `--ink`. `inkCells` only chooses between `--ink` and `--on-fill`. A natural dark palette keeps white "text on fills" and a light `--ink`. Then both choices are light, and the pale fills (light-blue diagonal, ochre Tie cells) carry light text well under 4.5:1. The recolor works, but readability silently breaks, and the `verify_dashboard.py` contrast assertion only runs on the shipped palette. — **Evidence:** `.venv/bin/python reviews/step7_product_critic_r2/dark_sober.py` (only the `:root` block edited: dark surfaces, `--ink #ececec`, `--on-fill #ffffff`, `--hit #6c8ebf`, `--miss #e0913a`, `--lex #c9a54a`):
- `balanced150_v3 cells under 4.5:1 -> [['Stars: Positive → model: Positive', '48', 3.45], ['Stars: Neutral → model: Negative', '25', 3.59], ['Stars: Negative → model: Negative', '45', 3.57], ['Model: anger · word list: Tie', '25', 2.34], ['Model: joy · word list: Tie', '24', 2.42]]`
- Every run has 2–5 such cells.
- Screenshot: `dark_sober_sec-confusion.png` shows white "48" on light blue.

— **Suggested fix:** add a third candidate, `--paper` or a fixed near-black, to the text-color choice, so a readable one always exists. Or state the rule in the `:root` comment: "`--on-fill` must contrast with `--ink`; for dark palettes set it dark." Make the verifier's contrast check also run against a dark-recolored copy.

MINOR — `dashboard/template.html` `td.emo` (`white-space: nowrap`) and `td.emo small` (the tied-emotions list), review table, balanced run, at both laptop widths — **What is wrong:** one review whose word list ties all eight emotions has a 357 px unwrapped line. That line widens the whole last column to 381 px and pushes the table to 1204 px inside a 1056 px card. On a laptop screen the Word list column is cut off by 146 px, and nothing shows that the table scrolls sideways. The other rows in that column are mostly empty space. — **Evidence:**
- `probe_out.txt`, 1440 and 1280: `table: {'client': 1056, 'scroll': 1204, ... ['Word list', 823, 381, 235]]}`.
- `table_width.py` → `[[357, 'anger / anticipation / disgust / fear / joy / sadness / surprise / trust'], [267, 'anger / anticipation / disgust / fear / joy / surprise'], ...]`.
- The three-class and two-class runs fit exactly: `scroll 1056`.

— **Suggested fix:** let the tied list wrap (`td.emo small { white-space: normal; }` with a `max-width` of about 22ch), or show "tie (8)" with the full list in the expanded row or a `title`.

MINOR — `dashboard/template.html` `.cbar { grid-template-columns: 92px minmax(0, 1fr) 27ch }`, the "Right answers by class" card at laptop widths — **What is wrong:** the fixed 27ch text column leaves each right/wrong bar only 75 px wide, in a card about 540 px wide. The card's point is how much of each class is wrong. It works, but the bars read as small icons next to the text rather than as the chart. On the balanced run, Positive "2 wrong" is a sliver. — **Evidence:** `gbar_out.txt`: `1440 balanced150_v3 {... 'cbarTrack': 74.8 ...}` (same at 1280; 236 px at 400). Screenshot: `full_balanced150_v3_1440.png`, card to the right of the heatmap. — **Suggested fix:** put the "17 of 50 · 34.0% · 33 wrong" text on a line above or below its bar, as the ≤560 px rule already does. The track then gets about 380 px.

MINOR — review table at 400 px (`.table-wrap`, `td.review { min-width: 320px }`), secondary phone check — **What is wrong:** on a phone the first screen of the table shows only ID, Stars, Answer key and Model. The Result column is partly visible, and the title and review text are at 0 px until the reader scrolls the table sideways. — **Evidence:** `probe_out.txt` `[balanced150_v3_400] table: {'client': 332, 'scroll': 1204, ... ['Result', 315, 77, 19], ['Title and review', 392, 320, 0], ...}`. The same pattern holds on every run at 400. — **Suggested fix:** under 560 px, lay each row out as a stacked card (chips and result on one line, title and review below, emotions last), or hide the ID column and put the answer and model in one cell ("Neutral → Negative ✕").
