# Step 7 — Numbers Auditor, round 2

Scope: Step 7 "Descriptive and prediction visualizations", on the complete dashboard with four runs (balanced150_v3, first100_v3, first100_v2, first100_v1). There is no README yet. Written numbers checked: the Step 7 section of ISSUES.md and all of PROGRESS.md.

## Result

- **No BLOCKER.** Every number the page shows, and every number in `metrics.json`, `emotion_metrics.json`, `comparisons.json` and `rating_distribution.json`, equals my independent recomputation.
- **1 MAJOR.** A chart geometry problem: the paired class bars are 27.7px wide on desktop, so their lengths no longer follow the counts. The numbers printed beside them are correct.
- **2 MINOR.**

## Findings

MAJOR — `dashboard/template.html` `.gbar` grid (line 119: `grid-template-columns: 40px minmax(0, 1fr) 3.5ch 15ch`) used by `renderDescribe` → `starsLine` / `modelLine` ("Stars' answer vs the model's answer, per class"), all tabs at 1440px and 1280px — The "per class" pairs sit in a third-width column. Its fixed label columns (3.5ch count, 15ch "N right · N wrong" detail) leave a bar track of only 27.7px. One review is worth 0.30px on first100 tabs, so almost every bar falls back to the 2px `min-width`, and bar lengths stop matching the saved counts. It is the "label/positioning interaction collapses small chart elements" bug the assignment warns about. It passes `verify_dashboard.py`, which only requires ≥ 2px, a printed label and equal tracks; all three hold here. The printed numbers beside the bars are all correct.
- Evidence: `.venv/bin/python reviews/step7_numbers_auditor_r2/measure_tracks.py` (output in `measure_tracks.txt`, screenshot `describe_first100_v3_1440.png`).
  - Every run at 1440 and 1280: `gbar cols 40px 27.7031px 27.5469px 118.094px`, `sec-describe gbar: [27.7]`. At 400px the track is 156.5px and the bars are proportional.
  - first100_v3 @1440, as [metric, value, px]:
    - Stars: `truth_distribution.counts.POSITIVE 93 → 27.7`, `NEUTRAL 2 → 2`, `NEGATIVE 5 → 2`.
    - Model NEGATIVE: `per_class.NEGATIVE.correct 5 → 2` plus `predicted_wrong 2 → 2` plus the 2px gap, so the model bar draws 6px against 2px for the stars' 5. The saved counts 7 vs 5 would be 2.1px vs 1.5px. The model's 7 draws 3× the stars' 5, and Stars 2 and Stars 5 draw identically.
    - The `.split` width is set to 7.53% (2.08px), but its two 2px-minimum segments overflow it.
  - The per-class right/wrong bars are also affected: model POSITIVE `correct 90 → 23.09px` where 24.82px is proportional, because the 1 wrong answer is held at 2px. My audit flags this on first100_v3, first100_v2 and first100_v1 (`MISMATCH … seg per_class.POSITIVE.correct length`).
  - balanced150_v3 @1440: the largest model bar (70) is 27.7px and Stars 50 is 19.8px. The chart is proportional but tiny, as `describe_balanced150_v3_1440.png` shows.
- Suggested fix:
  - Give the per-class block the full row of `.describe-grid` (e.g. `grid-column: 1 / -1`), or put the "N right · N wrong" detail on its own line below the bar instead of in a 15ch column, so the track is at least ~150px at desktop widths.
  - Draw the model bar's segments inside a track whose total length is computed as `total/maxC` with the gap and minimums included, so segments cannot overflow `.split`.
  - Add a `verify_dashboard.py` check that, per `data-scale` group, bar width ÷ track width matches value ÷ scale max within 1px, unless the bar is at the 2px minimum. Also add a minimum track width, e.g. ≥ 100px.

MINOR — `PROGRESS.md` line 12 ("`verify_dashboard.py` now asserts every mark … PASS 4,404 checks (`reviews/step7_verify_dashboard.txt`)") — The bullet cites `reviews/step7_verify_dashboard.txt` as evidence for 4,404 checks, but that file now ends `4283 checks, 0 failures`. The next bullet (line 14) gives 4,283, so the stale bullet cites evidence that no longer supports it. — Evidence: audit section 7: `FAIL [PROGRESS] correct: 'PASS 4,404 checks (…step7_verify_dashboard.txt)': file's last count line is now ('4283', '0')`. Re-running `.venv/bin/python src/verify_dashboard.py | tail -3` gives `4283 checks, 0 failures / PASS`. — Suggested fix: reword line 12 as history ("first build with the new check: 4,404 checks") without citing the now-overwritten file, or cite only the current count.

MINOR — `src/nrc_emotion.py` docstring step 3 ("use the token if it is in the lexicon; otherwise strip the first of the suffixes …") — The documented rule is ambiguous, and the two readings give different saved numbers. The code's "lexicon" holds only the 4,454 words with at least one of the 8 emotions. Someone re-implementing from the docstring could reasonably read "in the lexicon" as any of the 14,154 listed words, and that changes one row in each run. On first100_v3 and first100_v2 it would change the displayed agreement from 20 of 100 to 19 of 100. Saved values follow the code, and my recomputation under the code's reading matches every field. — Evidence: `.venv/bin/python reviews/step7_numbers_auditor_r2/lexicon_reading.py`:
  `balanced150_v3 134393 saved: TIE | … any-listed-word reading: surprise | tokens differing: [('rejected', 'reject')]`
  `first100_v3 62 saved: joy | … any-listed-word reading: TIE | tokens differing: [('contents', 'content')] | llm: joy` (same row in first100_v2).
  — Suggested fix: make step 3 say "if the token is a lexicon word with at least one of the 8 emotions; otherwise strip …". The README should use the same wording when it describes the method.

## What was checked (all independent of project code)

Script: `reviews/step7_numbers_auditor_r2/audit.py`. It imports no project module. Output: `reviews/step7_numbers_auditor_r2/audit_output.txt`, reproduced in full below. Supporting scripts: `measure_tracks.py` (→ `measure_tracks.txt`, `measure_tracks.json`, `describe_*_1440.png`) and `lexicon_reading.py` (→ `lexicon_reading.txt`).

1. **Whole file**, all 152,410 lines:
   - `rating_counts`, `rating_pct` (4 d.p.), `rating_share`, the inclusion failures overall and by rating, and integral ratings all match.
   - Dataset sha256 matches.
2. **Samples**:
   - first100 runs are the first 100 included rows.
   - The balanced sample is redrawn with `random.Random(42).sample(sorted pool, 50)` per class. It equals `sample_ids.json` and the prediction ids, and pool sizes match `run_meta.json`.
   - Every prediction row's title, text and rating equal its data line.
3. **Metrics**:
   - Truth labels are recomputed from the data file's rating: three-class for v3, binary for v1/v2.
   - Predictions and LLM emotions are re-parsed from `raw_responses`.
   - Every leaf of all four `metrics.json` files is recomputed, including the new `per_class.*.predicted_wrong`, with no extra or missing keys.
   - Against git HEAD, the only changes are the `predicted_wrong` additions to `metrics.json` and `rating_share` in `rating_distribution.json`; `comparisons.json` is unchanged. This confirms ISSUES' "no existing value changed".
4. **Emotions**:
   - Lexicon sha256, 14,154 words and 4,454 emotion words verified.
   - All 8 NRC row fields recomputed for every row in 3 runs.
   - Every numeric or label field of the 3 `emotion_metrics.json` files recomputed; prose fields excluded.
5. **`comparisons.json`**: every field recomputed, including the Wilson intervals, pools and weights re-derived from the data file, re-weighted accuracy and precision, expected-from-recalls accuracy, the one-more-NEUTRAL counterfactual, and the emotion fields.
6. **Dashboard** (Playwright headless Chromium, runs selected by clicking `[data-run-tab]`, at 1440, 400 and 1280px):
   - The embedded payload equals the files on disk.
   - For every `[data-metric]` number (251 / 229 / 205 / 89 per run), `data-source` resolves to a field of that run's file, and the path equals `data-metric`. `data-raw` equals my recomputed value, and the visible text equals the display rule: `toFixed(1)` on exact binary, en-US commas, "+/− N.N pts". Wilson `.0`/`.1` indexes resolve.
   - Every chart mark (130 / 121 / 115 / 24) has all four attributes, and `data-value` equals my value under the `__file__` / `emotion.` / `metrics.json` conventions.
   - Every mark > 0 is visible, at least 2×2px, and has a visible tagged label with the same field and value in its section.
   - `data-scale` groups have equal tracks within 1px.
   - Heatmap and cross-tab text contrast is ≥ 4.5:1.
   - No sideways scroll, the live count equals `n_rows`, and there are no console errors.
   - Untagged digit text is limited to star axis labels, file paths, "Macro F1", "Prompt sha256", the scheme sentence, the live count (`#shown-count`, tagged `data-live-count`) and the literal "4★" in the no-4★ note.
7. **Written numbers**: 25 Step 7 ISSUES claims and 29 PROGRESS claims, each found verbatim and recomputed (listed in the output). Only PROGRESS "PASS 4,404 checks" fails; see the finding above.

## Project checks re-run

```
$ .venv/bin/python src/verify_leak.py        (saved: reviews/step7_numbers_auditor_r2/verify_leak.txt)
PASS runs/balanced150_v3/predictions.jsonl: 150 rows, prompt prompts/sentiment_v3.txt; 26 rows had a star-phrase title/text blanked; 3 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v1/predictions.jsonl: 100 rows, prompt prompts/sentiment_v1.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v2/predictions.jsonl: 100 rows, prompt prompts/sentiment_v2.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v3/predictions.jsonl: 100 rows, prompt prompts/sentiment_v3.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
EXIT=0

$ .venv/bin/python src/verify_dashboard.py | tail -3     (read-only; saved: reviews/step7_numbers_auditor_r2/verify_dashboard_rerun.txt)
4283 checks, 0 failures
PASS
```

## Script output

```
$ .venv/bin/python reviews/step7_numbers_auditor_r2/audit.py
== 1. whole data file
rows 152410; counts {1: 12326, 2: 1873, 3: 3271, 4: 6692, 5: 128248}; failing 49; sha e03a258ebd7b…; star-variant titles (loose not exact) all rows 103, included 103; included rows with empty title 0
== 2. samples
first100 = 0..99; pools {'POSITIVE': 134913, 'NEUTRAL': 3270, 'NEGATIVE': 14178}
== 3. per-run metrics
[balanced150_v3] 110/150; truth {'POSITIVE': 50, 'NEUTRAL': 50, 'NEGATIVE': 50}; predicted {'POSITIVE': 57, 'NEUTRAL': 23, 'NEGATIVE': 70, 'UNPARSED': 0}; per-class correct [48, 17, 45]
[first100_v3] 95/100; truth {'POSITIVE': 93, 'NEUTRAL': 2, 'NEGATIVE': 5}; predicted {'POSITIVE': 91, 'NEUTRAL': 2, 'NEGATIVE': 7, 'UNPARSED': 0}; per-class correct [90, 0, 5]
[first100_v2] 97/100; truth {'POSITIVE': 93, 'NEGATIVE': 7}; predicted {'POSITIVE': 92, 'NEGATIVE': 8, 'UNPARSED': 0}; per-class correct [91, 6]
[first100_v1] 97/100; truth {'POSITIVE': 93, 'NEGATIVE': 7}; predicted {'POSITIVE': 92, 'NEGATIVE': 8, 'UNPARSED': 0}; per-class correct [91, 6]
== 4. emotions
[balanced150_v3] agree 16/150; TIE 67; NONE 24; const anger 4; best anticipation 22; rows whose label would change if 'in the lexicon' meant any listed word: 1
[first100_v3] agree 20/100; TIE 47; NONE 15; const joy 22; best joy 22; rows whose label would change if 'in the lexicon' meant any listed word: 1
[first100_v2] agree 20/100; TIE 47; NONE 15; const joy 22; best joy 22; rows whose label would change if 'in the lexicon' meant any listed word: 1
== 5. comparisons.json
== 6. dashboard
[balanced150_v3 @1440] 251 tagged numbers, 130 marks, scale groups ['class-counts', 'emotion-counts', 'right-wrong', 'star-share']; untagged digit text: ['150', '1★', '2★', '3★', '4★', '4★ reviews.', '5★', 'Macro F1', 'Positive here means 5★ reviews only: this sample has', 'Prompt sha256', 'runs/balanced150_v3/metrics.json', 'runs/balanced150_v3/predictions.jsonl', 'three classes; answer key from the stars: 4–5★ positive, 3★ neutral, 1–2★ negative']
  FAIL [first100_v3 @1440] seg per_class.POSITIVE.correct length: w=23.09 expected 24.82
[first100_v3 @1440] 229 tagged numbers, 121 marks, scale groups ['class-counts', 'emotion-counts', 'right-wrong', 'star-share']; untagged digit text: ['100', '1★', '2★', '3★', '4★', '5★', 'Macro F1', 'Prompt sha256', 'runs/first100_v3/metrics.json', 'runs/first100_v3/predictions.jsonl', 'three classes; answer key from the stars: 4–5★ positive, 3★ neutral, 1–2★ negative']
  FAIL [first100_v2 @1440] seg per_class.POSITIVE.correct length: w=23.39 expected 25.11
[first100_v2 @1440] 205 tagged numbers, 115 marks, scale groups ['class-counts', 'emotion-counts', 'right-wrong', 'star-share']; untagged digit text: ['100', '1★', '2★', '3★', '4★', '5★', 'Macro F1', 'Prompt sha256', 'runs/first100_v2/metrics.json', 'runs/first100_v2/predictions.jsonl', 'two classes; answer key from the stars: 4–5★ positive, 1–3★ negative']
  FAIL [first100_v1 @1440] seg per_class.POSITIVE.correct length: w=23.39 expected 25.11
[first100_v1 @1440] 89 tagged numbers, 24 marks, scale groups ['class-counts', 'right-wrong', 'star-share']; untagged digit text: ['100', '1★', '2★', '3★', '4★', '5★', 'Macro F1', 'Prompt sha256', 'runs/first100_v1/metrics.json', 'runs/first100_v1/predictions.jsonl', 'two classes; answer key from the stars: 4–5★ positive, 1–3★ negative']
[balanced150_v3 @400] 251 tagged numbers, 130 marks, scale groups ['class-counts', 'emotion-counts', 'right-wrong', 'star-share']; untagged digit text: ['150', '1★', '2★', '3★', '4★', '4★ reviews.', '5★', 'Macro F1', 'Positive here means 5★ reviews only: this sample has', 'Prompt sha256', 'runs/balanced150_v3/metrics.json', 'runs/balanced150_v3/predictions.jsonl', 'three classes; answer key from the stars: 4–5★ positive, 3★ neutral, 1–2★ negative']
[first100_v3 @400] 229 tagged numbers, 121 marks, scale groups ['class-counts', 'emotion-counts', 'right-wrong', 'star-share']; untagged digit text: ['100', '1★', '2★', '3★', '4★', '5★', 'Macro F1', 'Prompt sha256', 'runs/first100_v3/metrics.json', 'runs/first100_v3/predictions.jsonl', 'three classes; answer key from the stars: 4–5★ positive, 3★ neutral, 1–2★ negative']
[first100_v2 @400] 205 tagged numbers, 115 marks, scale groups ['class-counts', 'emotion-counts', 'right-wrong', 'star-share']; untagged digit text: ['100', '1★', '2★', '3★', '4★', '5★', 'Macro F1', 'Prompt sha256', 'runs/first100_v2/metrics.json', 'runs/first100_v2/predictions.jsonl', 'two classes; answer key from the stars: 4–5★ positive, 1–3★ negative']
[first100_v1 @400] 89 tagged numbers, 24 marks, scale groups ['class-counts', 'right-wrong', 'star-share']; untagged digit text: ['100', '1★', '2★', '3★', '4★', '5★', 'Macro F1', 'Prompt sha256', 'runs/first100_v1/metrics.json', 'runs/first100_v1/predictions.jsonl', 'two classes; answer key from the stars: 4–5★ positive, 1–3★ negative']
== 7. written numbers (ISSUES.md Step 7, PROGRESS.md)
  [ISSUES] '(all 152,410 rows): 5★ 84.1% … 2★ 1.2%': present=True correct=True 
  [ISSUES] 'batch_100 (91% 5★)': present=True correct=True 
  [ISSUES] 'drops 4★ entirely': present=True correct=True 
  [ISSUES] 'NEUTRAL is 50 by the stars vs 23 by the model, and NEGATIVE 50 vs 70': present=True correct=True 
  [ISSUES] 'whole-file 2★ at 1.2%': present=True correct=True 
  [ISSUES] '("· 2 wrong")': present=True correct=True 
  [ISSUES] 'Numbers Auditor no findings (18,529 checks, 0 mismatches)': present=True correct=True 
  [ISSUES] 'Grader 1 MAJOR + 6 MINOR; Skeptic 3 MAJOR + 5 MINOR; Product Critic 2 MAJOR + 6 MINOR': present=True correct=True 
  [ISSUES] "batch_100's 91% 5★ drew 29% longer than the file's 84.1%": present=True correct=True 
  [ISSUES] '(`30px | track | 7.5ch | 6ch`)': present=True correct=True 
  [ISSUES] 'Neutral read "Stars 2 / Model 2" although 0 of those were right': present=True correct=True 
  [ISSUES] 'constant "anger" 6.8% vs the model\'s 27.1% where the word list has one winner': present=True correct=True 
  [ISSUES] 'anticipation at 37.3% on that subset': present=True correct=True 
  [ISSUES] "beside the model's 10.7% and 27.1%": present=True correct=True 
  [ISSUES] '(320 of 320px at 1440px)': present=True correct=True 
  [ISSUES] '150 reviews: 50 drawn at random from each star class across the whole file (seed 42)': present=True correct=True 
  [ISSUES] 'Neutral reviews answered Negative, 25 of 50 (50.0%)': present=True correct=True 
  [ISSUES] 'with only 2 reviews in that class, one review moves this rate a lot': present=True correct=True 
  [ISSUES] 'Re-weighted accuracy (94.1%)': present=True correct=True 
  [ISSUES] 'always answering positive would score 88.5%': present=True correct=True 
  [ISSUES] 'this sample has 0 4★ reviews': present=True correct=True 
  [ISSUES] 'between 65.7% and 79.8%': present=True correct=True 
  [ISSUES] 'Rebuild: 4,283 checks, 0 failures': present=True correct=True 
  [ISSUES] 'verdict grid 334px (one column) at 400px, two columns at 1280px': present=True correct=True 
  [ISSUES] 'under 560px they now form one horizontally scrolling row': present=True correct=True 
  [PROGRESS] 'Step 6 committed: 18a3304': present=True correct=True 
  FAIL [PROGRESS] correct: 'PASS 4,404 checks (`reviews/step7_verify_dashboard.txt`)': file's last count line is now ('4283', '0')
  [PROGRESS] 'PASS 4,404 checks (`reviews/step7_verify_dashboard.txt`)': present=True correct=False file's last count line is now ('4283', '0')
  [PROGRESS] '`reviews/step7_grader.md` (1 MAJOR, 6 MINOR), `reviews/step7_numbers_auditor.md` (no findings, 18,529 checks), `reviews/step7_skeptic.md` (3 MAJOR, 5 MINOR), `reviews/step7_product_critic.md` (2 MAJOR, 6 MINOR)': present=True correct=True 
  [PROGRESS] 'PASS 4,283 checks (`reviews/step7_verify_dashboard.txt`)': present=True correct=True 
  [PROGRESS] 'PASS 3,770 checks (`reviews/step6_verify_dashboard.txt`)': present=True correct=True 
  [PROGRESS] 'PASS 1,344 checks': present=True correct=True 
  [PROGRESS] 'PASS 294 checks': present=True correct=True 
  [PROGRESS] 'balanced150_v3 73.3% (110/150), baseline 33.3%, NEUTRAL row 17 NEUTRAL / 25 NEGATIVE / 8 POSITIVE, NEGATIVE→NEUTRAL 4, POSITIVE→NEUTRAL 2, NEGATIVE→POSITIVE 1, predicted NEGATIVE 70; recall POS 48/50, NEU 17/50, NEG 45/50': present=True correct=True 
  [PROGRESS] 'first100_v3 95.0% (95/100), baseline 93.0%, balanced acc 65.6%, truth 93/2/5, errors 46, 83 (POS→NEU), 17 (POS→NEG), 98 (NEU→POS), 91 (NEU→NEG)': present=True correct=True 
  [PROGRESS] 'Balanced sample star mix 1★43 2★7 3★50 4★0 5★50; 26 star titles blanked; 1 duplicate pair': present=True correct=True 
  [PROGRESS] 'customers\' own star mentions reached the model in 121389 (text, "5 stars") and 140676 (title, "zero stars")': present=True correct=True 
  [PROGRESS] 'Emotions balanced: agreement 16/150; LLM top emotion anger (62) → constant anger 4/150; BEST constant (new field `best_constant_baseline*`) anticipation 22/150 (14.7%), 22/59 (37.3%) → LLM −4.0 / −10.2 pts': present=True correct=True 
  [PROGRESS] 'first100_v3 emotions: 20/100 vs constant joy 22/100 (best constant also joy)': present=True correct=True 
  [PROGRESS] 'plain accuracy 65.7–79.8%, NEUTRAL→NEGATIVE share 36.6–63.4%, NEUTRAL recall 22.4–47.8%, NEUTRAL→POSITIVE 8.3–28.5%': present=True correct=True 
  [PROGRESS] 'weights 88.5/2.1/9.3%; re-weighted accuracy ~94.1%, NEUTRAL precision ~14.5%': present=True correct=True 
  [PROGRESS] 'predict 94.5% vs observed 95.0%': present=True correct=True 
  [PROGRESS] '(82.3% with one more right)': present=True correct=True 
  [PROGRESS] '4880, 22082, 32735, 51332, 53136, 60681, 111780, 147336': present=True correct=True 
  [PROGRESS] '(Fisher p 0.041 on NEUTRAL row)': present=True correct=True 
  [PROGRESS] '103 star-count title variants in file escape exact blanking': present=True correct=True 
  [PROGRESS] '(no originally empty titles in file)': present=True correct=True 
  [PROGRESS] 'accuracy 97.0% vs majority baseline 93.0%; NEGATIVE recall 6/7': present=True correct=True 
  [PROGRESS] 'sha256 `e03a258ebd7b1e2591b09862aab65d3dcde9c300744d800aa1fbaf374b7c2340`, 152,410 rows, 49 rows fail inclusion rule': present=True correct=True 
  [PROGRESS] 'batch_100 = review_ids 0–99 (0 rows excluded). Contains duplicate groups "Good Product" ×7 (20–24, 27, 28) and "Good product" ×2 (25–26) = 7 repeats': present=True correct=True 
  [PROGRESS] 'POSITIVE `#2f5aa8`, NEUTRAL `#8f8a7e`, NEGATIVE `#c8502e`, UNPARSED `#6e56b8`. Right `#3e4a57`, wrong `#d9822b`': present=True correct=True 
  [PROGRESS] 'lexicon sha256 02c66154…535a, 14,154 words, 4,454 with ≥1 of 8 emotions': present=True correct=True 
  [PROGRESS] 'sentiment identical to v1 (0 flips; errors 17, 46, 98). Emotion agreement 20/100, 20/85 excl NONE, 20/38 excl NONE+TIE; constant "joy" 22/100, 22/85, 22/38 (LLM −2.0 / −5.3 pts); LLM non-joy rows agree 1/20; TIE 47 (LLM emotion in 45, "joy" in 45; 43 → anticipation under tie-break), NONE 15; tie-break agreement 23/100 (constant joy 23/100, constant anticipation 57/100); unique rows 93 (agree 20, TIE 40, NONE 15); negation 15 hits in 11 rows': present=True correct=True 
  [PROGRESS] '442 after Step 6 runs (199 + 3 balanced preview + 147 balanced150_v3 + 93 first100_v3)': present=True correct=True 

21261 checks, 4 mismatches
MISMATCH [first100_v3 @1440] seg per_class.POSITIVE.correct length: w=23.09 expected 24.82
MISMATCH [first100_v2 @1440] seg per_class.POSITIVE.correct length: w=23.39 expected 25.11
MISMATCH [first100_v1 @1440] seg per_class.POSITIVE.correct length: w=23.39 expected 25.11
MISMATCH [PROGRESS] correct: 'PASS 4,404 checks (`reviews/step7_verify_dashboard.txt`)': file's last count line is now ('4283', '0')
```

The four "mismatches" are not value mismatches. The first three are bar-length deviations caused by the 27.7px track in the MAJOR finding. The fourth is the stale PROGRESS count in the first MINOR finding.
