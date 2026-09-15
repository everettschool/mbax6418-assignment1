# Step 6 — Numbers Auditor

Script: `reviews/step6_numbers_auditor/audit.py` (independent; imports nothing from `src/`)
Run: `.venv/bin/python reviews/step6_numbers_auditor/audit.py` → full output in `reviews/step6_numbers_auditor/audit_output.txt`
Leak check: `.venv/bin/python src/verify_leak.py` → `reviews/step6_numbers_auditor/verify_leak_output.txt`

## What was recomputed and compared
- **Dataset:** inclusion rule, the batch_100 ids, and pools and a re-draw of balanced_150 with `random.Random(42).sample(sorted ids, 50)` per class. Every saved id matches `sample_ids.json` and each run's predictions. The ratings, titles and texts in the predictions match the data file, and truth is re-derived from the rating. `rating_distribution.json` and `nrc_lexicon_meta.json` (sha, word counts) also match.
- **metrics.json, all 4 runs:** every leaf was deep-compared with my own computation of confusion, per-class P/R/F1, balanced accuracy, macro F1, baseline, shares, misclassified ids, and parse/retry counts. `prediction` and `llm_emotion` were also read back from the raw replies.
- **NRC:** own tokenizer, suffix fallback and argmax/TIE/NONE on the dataset text. Per-row `nrc_emotion`, `nrc_tied`, `nrc_scores`, token and hit counts, tiebreak and `emotion_agree` all match. Every leaf of `emotion_metrics.json` matches for `balanced150_v3`, `first100_v3` and `first100_v2`, including the constant and best-constant baselines, the cross-tab, tiebreak, unique rows, negation and divergent ids.
- **comparisons.json:** every field recomputed, including all 6 Wilson intervals.
- **Dashboard** (Playwright headless Chromium, runs selected by clicking `[data-run-tab]`):
  - Every `data-metric` element: `data-raw` equals the file field and my recomputed value, `data-source` equals this run's file#`data-metric`, and the shown text equals the display rule applied to `data-raw`.
  - Every chart mark: `data-value` equals the recomputed value, `data-run` and `data-label` are present, and marks with a value above 0 render wider and taller than 0.5 px.
  - Table rows (id, stars, truth, prediction, correct) match the predictions, and the live count equals n.
- **Written numbers:** 73 claims from `reviews/step6_analysis.md`, `ISSUES.md` (Step 6) and `PROGRESS.md`. For each one, the script checks that the exact quoted text exists in the file and that the value holds against my recomputation.

## Script output (summary; totals verbatim)
```
pools: {'NEGATIVE': 14178, 'NEUTRAL': 3270, 'POSITIVE': 134913} | excluded: 49
4-star rows in POSITIVE pool: 6691
balanced150_v3: acc 110/150 = 73.3% | baseline 33.3% | bal 73.3% | macroF1 70.4% | cells {... 'NEUTRAL->POSITIVE': 8, 'NEUTRAL->NEUTRAL': 17, 'NEUTRAL->NEGATIVE': 25, ... 'NEGATIVE->POSITIVE': 1, 'NEGATIVE->NEUTRAL': 4, 'NEGATIVE->NEGATIVE': 45 ...}
   emotion agree 16/150 (10.7%), single 16/59; const anger 4; best anticipation 22; TIE 67 NONE 24; llm-in-tie 37 const-in-tie 6
first100_v3: acc 95/100 = 95.0% | baseline 93.0% | bal 65.6% | macroF1 60.4%
   emotion agree 20/100 (20.0%), single 20/38; const joy 22; best joy 22; TIE 47 NONE 15; llm-in-tie 45 const-in-tie 45
first100_v2: acc 97/100 = 97.0% | baseline 93.0% | bal 91.8% | macroF1 89.2%
   emotion agree 20/100 (20.0%), single 20/38; const joy 22; best joy 22; TIE 47 NONE 15; llm-in-tie 45 const-in-tie 45
first100_v1: acc 97/100 = 97.0% | baseline 93.0% | bal 91.8% | macroF1 89.2%
Wilson: first100_v1 91.5–99.0%; first100_v3 88.8–97.8%; balanced150_v3 accuracy 65.7–79.8%; neutral recall 22.4–47.8%; neutral->negative 36.6–63.4%; neutral->positive 8.3–28.5%
dashboard/balanced150_v3: 215 data-metric numbers, 131 chart marks, 150 table rows
dashboard/first100_v3: 210 data-metric numbers, 122 chart marks, 100 table rows
dashboard/first100_v2: 189 data-metric numbers, 115 chart marks, 100 table rows
dashboard/first100_v1: 60 data-metric numbers, 14 chart marks, 100 table rows
written claims checked: 73; star-phrase title OR text in balanced sample: 26
balanced rows whose sent title/text contain rating/star/stars/helpful/verified: [(121389, ['stars']), (138151, ['Helpful']), (140676, ['stars'])]
TOTAL checks: 11865; FAILURES: 0
exit=0
```
The first run of the script reported 450 failures. All of them were a bug in my own script: it formatted the stars as "5.0★", but the page shows `String(5.0)` = "5★". After fixing that one comparison, the result is 0 failures.

Digits on the page outside `data-metric` (the review table body excluded):
- the class rule text "4–5★ positive, 3★ neutral, 1–2★ negative";
- the words "Macro F1" and "Prompt sha256";
- source file paths;
- the live filter count `#shown-count`, which is filter state rather than a saved metric (the "of N" beside it is bound).

None of these is an unbound metric.

verify_leak.py:
```
PASS runs/balanced150_v3/predictions.jsonl: 150 rows, prompt prompts/sentiment_v3.txt; 26 rows had a star-phrase title/text blanked; 3 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v1/predictions.jsonl: 100 rows, prompt prompts/sentiment_v1.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v2/predictions.jsonl: 100 rows, prompt prompts/sentiment_v2.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v3/predictions.jsonl: 100 rows, prompt prompts/sentiment_v3.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
exit=0
```

No metric mismatches: metrics.json, emotion_metrics.json, comparisons.json, the dashboard DOM and every Step 6 written metric agree with the independent recomputation. No BLOCKERs.

## Findings

1. MINOR — `reviews/step6_analysis.md` line 136 and `ISSUES.md` line 97 — **the count of rows where the model could read a rating-like statement is wrong (they say 1; there are 2).**
   - Review 140676 (1★) has the title "I would give this 'zero stars'". It is not a pure star phrase, so it was not blanked and was sent to the model.
   - Evidence, analysis: "**One review's own text mentions stars** (121389, …)".
   - Evidence, ISSUES: "Disclosed as one row where the model could read a rating-like statement."
   - Evidence, script: `balanced rows whose sent title/text contain rating/star/stars/helpful/verified: [(121389, ['stars']), (138151, ['Helpful']), (140676, ['stars'])]`; predictions.jsonl row 140676: `title "I would give this 'zero stars'"`, rating 1.0, prediction NEGATIVE.
   - The same scan explains verify_leak's "3 reviews use a forbidden word": 138151's title "Helpful Review" is the third.
   - Cause: the Step 6 exploration only searched the text field (`balanced150_v3 texts that mention stars …`).
   - Suggested fix: say two rows (121389 in text, 140676 in title; 140676 was predicted correctly) and note that 138151 accounts for verify_leak's third hit.

2. MINOR — `PROGRESS.md` line 9 — **the verify_dashboard check count does not match its saved log.**
   - This is a verification-log count, not a metric computed from predictions.
   - Evidence: PROGRESS says "`verify_dashboard.py` PASS 3,661 checks (`reviews/step6_verify_dashboard.txt`)", but `grep -n "checks" reviews/step6_verify_dashboard.txt` returns `114:3676 checks, 0 failures`.
   - The log was rewritten (15:19) after PROGRESS (15:18).
   - Suggested fix: update PROGRESS to 3,676, or re-run and quote whatever the final log says.

3. MINOR — `reviews/step6_analysis.md` line 118 — **the Wilson interval for plain accuracy is labelled "balanced accuracy".**
   - Evidence: "balanced accuracy of the run 65.7%–79.8% (`balanced150_v3_accuracy_wilson95`)".
   - `compare_runs.py` computes that field as `wilson95(correct, n_rows)` = Wilson(110, 150), the interval for plain accuracy.
   - The two point values coincide only because the classes are equal in size (both 73.3%), and a Wilson interval on 110/150 is not an interval for the mean of three per-class recalls.
   - Suggested fix: write "accuracy of the run 65.7%–79.8%", or compute and cite a separate balanced-accuracy interval.
