# Step 7 Grader — round 2

Scope: Step 7 on the complete built `dashboard/index.html` (all four tabs, 1440px and 400px), plus Steps 3 and 4. Scripts and evidence are in `reviews/step7_grader_r2/`:
- `measure.py` → `measure_out.txt` / `measure.json`: track widths, bar length vs. saved value, section positions, section text.
- `verify_rerun.txt`
- `mutation_zero_width_verify.txt`, `measure_mut_out.txt` (a mutated copy under `root/`)
- `predictive_interval.txt`
- screenshots `fold_*`, `describe_*`, `classes_*`, `verdict_*`

Checks that passed:
- `.venv/bin/python src/verify_dashboard.py` → `4283 checks, 0 failures / PASS`, identical to `reviews/step7_verify_dashboard.txt`. Step 4 filter and live-count cases all pass; there is no sideways scroll at 400px.
- All three Step 7 example charts are present on every tab: the star distribution for the whole file and for the sample, stars vs. model per class, and right answers per class.
- The round-1 scale MAJOR is fixed. Every `data-scale` group has one track width on every run and at both widths. Each bar is within 0.02px of its saved share or count, e.g. `scale star-share: n=9 track min/max 165.0/165.0 worst |w-expected| 0.02px`.
- Other round-1 fixes are verified on the page:
  - the model bar is split into right and wrong;
  - no Unparsed clutter;
  - every mark has an `aria-label` (`unnamed-marks=0`);
  - the review column is fully visible at 1440px (`visible: 320, width: 320`);
  - the verdict names the top confusion ("Neutral reviews answered Negative, 25 of 50 (50.0%)");
  - the 4★ note, the re-weighted baseline and the small-class caveat are shown.
- ISSUES.md has 7 `[Step 7]` entries, including a round-1 log.

Findings:

MAJOR — `dashboard/template.html` `.gbar` (line 119, `grid-template-columns: 40px minmax(0, 1fr) 3.5ch 15ch`) inside the one-third `.describe-grid` column, "Stars' answer vs the model's answer, per class", all tabs at desktop width — The fixed label columns from round 1 leave this chart's bar track only 27.7px wide at 1440px. The 15ch "N right · N wrong" column and the 84px class-name column take the rest of the space. This is the chart meant to show failures "at a glance", but on desktop its bars are thumbnail ticks, and small values sit on the 2px floor so their proportions are lost. This is the "very small chart elements … label/positioning interaction" Step 7 warns about. At 400px the same chart gets a 156.5px track and reads well, so the problem only appears on desktop.
- Evidence: `.venv/bin/python reviews/step7_grader_r2/measure.py` (1440px):
  - `balanced150_v3@1440 … scale class-counts: n=3 track min/max 27.7/27.7`, against `scale star-share … 165.0` beside it.
  - `first100_v3@1440 split Negative: total=7 w=2.1 … segs=[(5, 2), (2, 2)]`: 5 right and 2 wrong draw at the same 2px. The two 2px segments plus the 2px gap (6px) overflow the 2.1px split box.
  - `split Neutral: total=2 w=2.0 segs=[(2, 2)]`, and the Stars bars for 2 and 5 are also 2px.
  - Screenshots `reviews/step7_grader_r2/describe_first100_v3_1440.png` and `describe_balanced150_v3_1440.png` show bars of about 28px next to 165px star bars. Compare `describe_balanced150_v3_400.png`.
- Suggested fix:
  - Give this chart a wider box: let `classBlock` span the full row under the two star charts (`grid-column: 1 / -1`), or use a 1fr 1fr 1.6fr grid.
  - Or move the `.detail` text onto its own line at every width, as the ≤560px rule already does, so the track takes that space.
  - Add a `verify_dashboard.py` check that each `data-scale` group's track is at least ~100px wide.
  - Add a check that the `.split` segments plus gaps fit inside the split box.

MINOR — `src/verify_dashboard.py` `check_marks` — The guard still cannot detect the exact bug Step 7 names. It checks that each mark is at least 2px and that tracks in a group are equal, but not that a bar's length matches its value. Because `.bar` has `min-width: 2px`, a bar given zero width by mistake renders as a 2px sliver and passes.
- Evidence (mutated copy only): in `reviews/step7_grader_r2/root/dashboard/index.html` I replaced the star-bar width expression with `width:0%` (1 occurrence), then ran `root/src/verify_dashboard.py` → `4283 checks, 0 failures / PASS`, exit 0. `measure_mut.json` shows `('rating_counts.5', 128248, 2, 'width: 0%; …')`: 84.1% drawn at 2px, `worst |w-expected| 136.88px`.
- ISSUES "[Step 7] Layout-bug guard extended to labels" presents the 2px + label check as the guard.
- Suggested fix:
  - Put the intended fraction on each mark (e.g. `data-frac`) and assert `|w − max(2, frac·track)| ≤ 1px`. For split segments, allow for the flex gaps.
  - Record a mutation test like Step 4's (`reviews/step4_verify_mutation.txt`).

MINOR — `dashboard/template.html` line 421 (verdict hero) — "A fresh sample of this size would likely land between 65.7% and 79.8%" gives a Wilson 95% interval for the true agreement rate as if it predicted a fresh sample's score. A fresh sample of 150 carries its own sampling noise, so its range is wider. The page text is therefore statistically wrong, and its "Show your work" basis (`comparisons.json` `*_accuracy_wilson95`) does not support the claim as worded.
- Evidence: `reviews/step7_grader_r2/predictive_interval.txt`. With a uniform-prior Beta-binomial simulation, a fresh 150 lands in `(0.627, 0.827)`, not 65.7–79.8%. A fresh 100 for first100_v1 lands in `(0.90, 1.00)`, not the page's 91.5–99.0%.
- Suggested fix: reword to "the underlying agreement rate is likely between 65.7% and 79.8% (95% interval)". Apply the same "likely between" rewording to the confusion footnote (line 576), or label it a 95% interval for the rate.

MINOR — verdict card, `first100_v2` vs. `first100_v1` tabs — The interval line appears on one tab and not the other, although both runs have identical sentiment results (97/100, the same confusion matrix). A reader switching tabs sees an uncertainty statement vanish for the same numbers.
- Evidence: `measure.json` text, `first100_v1@1440`: "A fresh sample of this size would likely land between 91.5% and 99.0%." `first100_v2@1440` has no such line. `runs/comparisons.json` keys: `first100_v1_accuracy_wilson95`, `first100_v3_accuracy_wilson95`, `balanced150_v3_accuracy_wilson95`, and no `first100_v2_*`.
- Suggested fix: add `first100_v2_accuracy_wilson95` in `src/compare_runs.py`, or have the template use the interval for any run with the same correct/n.

MINOR — `ISSUES.md` line 153 (round-1 log) and line 151 ("Color-only legend" entry) — The log says the Grader's "6 MINOR" were "all fixed, none rejected", but lists only five Grader MINORs:
- totals (merged into the Skeptic line)
- Unparsed
- aria
- misfiled entries
- screenshot

The sixth, "Stars bars use a gray that is nearly the NEUTRAL class color" (`reviews/step7_grader.md`), is not recorded. It is in fact resolved on the page: Stars bars now use `--ref`, and model bars use right/wrong colors instead of the class color. Separately, line 151 says "The legend now uses position ('upper bar = stars, lower bar = model')", but the built legend is color swatches, "Stars' count · Model right · Model wrong" (template lines 523–526). The position wording moved to the sub-caption.
- Evidence: `grep -n "(Grader" ISSUES.md` → Step 7 bullets at lines 169–172 plus the merged totals bullet; no gray/`--ref` bullet (`grep -n -i "gray\|--ref" ISSUES.md` → only line 151).
- Suggested fix:
  - Add the missing round-1 bullet (Stars bars moved to `--ref`; model bars no longer use the class color, so the Neutral clash is gone).
  - Update line 151 to describe the current legend and caption.
  - Log this round-2 layout finding when fixed, since README Q4 is drafted from this file.

MINOR — `dashboard/screenshots/` — No final Step 7 capture exists yet; the folder holds only `drafts/`. The last drafts (`r1_*`, `r1b_*`) predate any round-2 fix, and a README screenshot is a final deliverable. PROGRESS schedules this after round 2, so it is open rather than wrong, but the Step 7 gate should not be recorded without it.
- Evidence: `ls dashboard/screenshots` → `drafts`.
- Suggested fix: after fixing the MAJOR above, delete `drafts/` and capture the 1440×900 fold, the descriptive card (balanced and first100_v3), the classes and confusion cards, and one filtered-table state into `dashboard/screenshots/`. View them before recording the gate.
