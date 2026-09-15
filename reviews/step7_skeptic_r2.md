# Step 7 — Skeptic review, round 2

Scripts and output are in `reviews/step7_skeptic_r2/`:
- `dump.py` → `page_dump.txt`: visible text of every section on all 4 tabs, headless Chromium at 1440px, runs switched by clicking `[data-run-tab]`.
- `scale.py` → `scale_out.txt`: width of every `data-scale` mark and its track at 1440 and 400px.
- `tracks.py` → `tracks_out.txt`: paired-bar and right/wrong track, split and label widths at 1440, 1280 and 400px.
- `stats.py` → `stats_out.txt`: per-star outcomes, model vs always-majority discordant pairs, prediction-interval and re-weighting sensitivity.
- Screenshots: `describe_*_1440.png`, `classes_balanced150_v3_1440.png`, `*_full.png`.

Checked and found sound (no finding):
- **No new path for the rating to reach the model.** Step 7 changed `runs/*/metrics.json` (+`predicted_wrong`) and `runs/rating_distribution.json` (+`rating_share`) only. `git status --short runs prompts` shows no change to any `predictions.jsonl` or prompt.
- **No imbalance hidden behind a class-level rate.** On balanced150_v3 all 7 2★ reviews are right, and the 5 NEGATIVE misses are all 1★ (4 → NEUTRAL, 1 → POSITIVE). The per-class rates therefore hide no 2★ failure.
- **Balanced-tab claims hold.** The "most common mistake" (Neutral → Negative 25 of 50) holds against sampling noise: its interval (36.6–63.4%) does not overlap Neutral → Positive (8.3–28.5%). The emotion sentence now gives the best constant beside the model's 10.7% and 27.1%. The "Positive here means 5★ reviews only" note is correct.
- **Shared-scale star charts are fixed.** Both star charts now share one 165.05px track at 1440px, and whole-file 2★ draws at its true 2.02px.

---

MAJOR — `dashboard/template.html` CSS `.gbar` (l.119: `40px minmax(0,1fr) 3.5ch 15ch`) and `.cbar` (l.145: `92px minmax(0,1fr) 27ch`), plus the ISSUES Step 7 "Descriptive layer design" entry ("so errors that cancel in the totals are visible too") and round-1 log ("The paired class bars … and the per-class right/wrong bars got the same treatment") — What is wrong:
- The round-1 fix, fixed label columns, starves the bar tracks at every laptop width. The "Stars' answer vs the model's answer" chart, the Step 7 chart meant to show failures at a glance, gets a 27.7px track inside a 237px row. The right/wrong bars get 74.8px of a 450px row.
- On first100_v3 the stars' 2 Neutral and 5 Negative, the model's 2 Neutral and the model's 7 Negative all draw at the 2px `min-width` floor. They are the same length, so over-prediction and the 0-right Neutral split are invisible in the bars and survive only as text.
- This is the "label/positioning interaction" Step 7 warns about. The `data-scale` check passes because it only compares tracks with each other (27.7 = 27.7). The model split segments carry no `data-scale` group at all.

Evidence: `.venv/bin/python reviews/step7_skeptic_r2/tracks.py` →
- 1440 first100_v3: `{'who': 'Stars', 'gbar': 237.34, 'track': 27.7, 'stars': 2}` (Neutral, 2) · `{'who': 'Stars', … 'stars': 2}` (Negative, 5) · `{'who': 'Model', 'split': 2, 'segs': ['per_class.NEUTRAL.predicted_wrong=2:2']}` · `{'who': 'Model', 'split': 2.08, 'segs': ['per_class.NEGATIVE.correct=5:2', 'per_class.NEGATIVE.predicted_wrong=2:2']}` (two 2px segs plus a 2px gap overflow a 2.08px split).
- The same numbers at 1280px. At 400px the track is 156.45px and the same bars are 3.36 / 8.41 / 11.77px, so the chart only works on phones.
- Right/wrong bars at 1440: `'cbar': 449.91, 'track': 74.81, 'text': 255.09`. The 27ch text column is 3.4× the bar.
- Screenshots `describe_first100_v3_1440.png` (Neutral/Negative pairs are slivers) and `classes_balanced150_v3_1440.png`.

Suggested fix:
- Give the tracks a floor, e.g. `.gbar { grid-template-columns: 40px minmax(120px,1fr) 3.5ch auto }`, or move `.detail` under the bar as at ≤560px. Put `.cbar-text` on its own line, or cap it well below 27ch.
- Tag the model split segments with a `data-scale` group.
- Add a `verify_dashboard.py` assertion that every scale group's track is at least e.g. 100px, and that no two marks with different values render at the same pinned 2px width.
- Until then, drop "visible too" from ISSUES.

MAJOR — verdict line on `first100_v3`, `first100_v2`, `first100_v1` (`template.html` l.433: "Reading the reviews is worth ", `accuracy_minus_majority_baseline`, " over that shortcut.") — What is wrong: the sentence states the model beats always-Positive by +2.0 pts (v3) and +4.0 pts (v1/v2). The data cannot tell those gains from zero, and the page's own interval under the hero contradicts it. These are the lopsided runs the standing considerations say must never "look like proof the model is great."

Evidence: `.venv/bin/python reviews/step7_skeptic_r2/stats.py` →
- `first100_v3 … vs always-POSITIVE: model-only-right 5, baseline-only-right 3, exact McNemar two-sided p=0.727`.
- `first100_v2 … model-only-right 6, baseline-only-right 2 … p=0.289` (v1 identical).
- The page says "A fresh sample of this size would likely land between 88.8% and 97.8%" (v3) and "between 91.5% and 99.0%" (v1). Both ranges contain the 93.0% shortcut.

Suggested fix: replace "is worth +2.0 pts" with a tagged count sentence, e.g. "The model gets 5 non-positive reviews right that the shortcut misses, and misses 3 positive reviews the shortcut gets. On 100 mostly-positive reviews that gap is too small to tell apart from the shortcut." Save the discordant counts in `comparisons.json` so they can be tagged.

MAJOR — hero sub-line on `balanced150_v3`, `first100_v3`, `first100_v1` (`template.html` l.421: "A fresh sample of this size would likely land between …") and the confusion footnote on balanced150_v3 ("these shares could move with a fresh sample: … likely between") — What is wrong: the wording answers "would another sample change the story?" too confidently, in three ways.
1. A Wilson 95% interval is a range for the underlying rate, not for where a new sample's accuracy lands. A new sample of the same size varies about √2 more.
2. On the first100 tabs there is no sampling to repeat. The rows are the first 100 in file order (91% 5★ against the file's 84.1%), so "a fresh sample of this size" describes a design that was never used.
3. The interval appears only where `comparisons.json` happens to have a key. `first100_v2` (97/100) shows none, while `first100_v1`, with the identical 97/100, shows "91.5% and 99.0%". Two tabs with the same result therefore carry different uncertainty statements.

Evidence:
- `stats.py`: `balanced150_v3 acc 110/150 wilson 0.657-0.798; approx 95% prediction interval for a new sample of 150: 0.633-0.833`.
- `first100_v3 … wilson 0.888-0.978; … prediction interval … 0.890-1.010`.
- `page_dump.txt` l.905–912 (first100_v2 verdict: no range line) vs l.1309 (first100_v1: "between 91.5% and 99.0%").
- `grep first100_v2_accuracy_wilson95 runs/comparisons.json` → no match.

Suggested fix:
- Reword to what the interval is: "95% range for the underlying agreement rate: 65.7–79.8%". Do the same for the footnote.
- On first100 tabs, either drop the interval or say "if these 100 were a random draw, which they are not".
- Add `first100_v2_accuracy_wilson95` to `compare_runs.py`, or render the range from `metrics.json` counts for every run, so all tabs are treated alike.

MINOR — `balanced150_v3` classes card, re-weighting note ("accuracy about 94.1%, where always answering positive would score 88.5% (a rough estimate from this sample)") — What is wrong: the sentence places the model 5.6 pts above the shortcut on the real mix. That margin rests almost entirely on 48 of 50 Positive being right, and three more misses would erase it. The sample also has no 4★ reviews, which pushes the estimate up, not down. The page shows intervals elsewhere but none here, and "rough" does not say which way the estimate is biased.

Evidence: `stats.py` →
- `POS recall 48/50 wilson 0.865 0.989`
- `reweighted acc with POS recall 0.865 -> 0.8573 vs always-positive 0.8855`
- `if 4 of 50 positives missed -> 0.9057`
- `if 5 of 50 positives missed -> 0.8880`

On the page (l.158–160), the 5★-only note is a separate sentence that is not tied to the 94.1%.

Suggested fix: append "this lead rests on 2 missed positives out of 50; with 5 misses it would vanish, and 4★ reviews (absent here) would likely lower it". Or save and show the range computed from the Positive-recall interval (about 85.7–96.7%).

MINOR — verdict "Most common mistake" on `first100_v3` and `first100_v2`/`v1` (`template.html` l.412–436, ranked by raw count) — What is wrong: on a lopsided sample, ranking by count always picks an error from the majority class, so the verdict's one failure pattern is the least informative one.
- first100_v3 names "Positive reviews answered Neutral, 2 of 93 (2.2%)". Both Neutral reviews went wrong (1 → Positive, 1 → Negative, 50.0% of row each).
- v1/v2 name "Positive reviews answered Negative, 2 of 93 (2.2%)" over "Negative → Positive, 1 of 7 (14.3%)".

Evidence: `page_dump.txt` l.481 and l.916. The saved cells are in `reviews/step7_rescore.txt` (`NEUTRAL->POSITIVE': 1, 'NEUTRAL->NEGATIVE': 1`).

Suggested fix: rank by row share, breaking ties by count, or label it "most frequent mistake by count". Alternatively, skip it when the top cell is under a few percent of its row.

MINOR — emotion "For scale" sentence on `first100_v3` and `first100_v2` — What is wrong: the balanced tab now ends with "against the model's 10.7% and 27.1%". The first100 tabs give the constant's rates but never say that the constant "joy" beats the model on both subsets. The prominent tile (52.6%) therefore reads as the better number when the saved differences are negative.

Evidence: `page_dump.txt` l.683 ("22.0% of all reviews (22 of 100) and on 57.9% where it has one winner (22 of 38)"), tiles l.673–681 (20.0%, 52.6%). `comparisons.json`: `first100_v3_emotion_llm_minus_best_constant_all_rows = -0.02`, `…_excluding_none_and_tie = -0.0526`.

Suggested fix: use the same template branch on every tab, "… against the model's 20.0% and 52.6%", tagged to the tile fields.

MINOR — `PROGRESS.md` l.12 — What is wrong: it still cites "PASS 4,404 checks (`reviews/step7_verify_dashboard.txt`)", but that file now ends "4283 checks, 0 failures / PASS". A reader following the citation finds a different number. ISSUES l.150 labels 4,404 as the "first build", which is accurate.

Evidence: `tail -2 reviews/step7_verify_dashboard.txt` → `4283 checks, 0 failures` / `PASS`.

Suggested fix: mark l.12 as the pre-round-1 build, or point it at a saved copy of that log.
