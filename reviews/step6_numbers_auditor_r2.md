# Step 6 — Numbers Auditor, round 2

Script: `reviews/step6_numbers_auditor_r2/audit.py`. It is my own implementation and imports nothing from `src/`.

Run: `.venv/bin/python reviews/step6_numbers_auditor_r2/audit.py > reviews/step6_numbers_auditor_r2/audit_output.txt`

The script's exit code is 1 only because of the PROGRESS.md label finding below. That label check is deliberately set to fail in the script, and the quote was confirmed present in PROGRESS.md.

## What was recomputed and compared
- **Data file** (`data/Gift_Cards.jsonl.gz`)
  - sha256, 152,410 rows, 49 excluded by the inclusion rule.
  - Class pools: 14,178 / 3,270 / 134,913.
  - `rating_distribution.json`: every field.
  - batch_100 = review_ids 0–99.
  - A fresh draw of balanced_150 with `random.Random(42).sample(sorted pool, 50)` equals `sample_ids.json`, including its selection_info.
  - 4★ reviews in the POSITIVE pool: 6,691.
  - Star-phrase title shares by pool.
  - The 1,000-seed composition statistics (zero-4★ draws; NEUTRAL and whole-draw star-title counts: mean, median, 5th and 95th percentile).
- **Lexicon:** sha256, 14,154 words, 4,454 with at least one of the 8 emotions, and the column list, all against `nrc_lexicon_meta.json`.
- **All 4 runs:** row by row against the data file (id set, title, text, rating), then:
  - truth re-derived from the rating;
  - `prediction`, `parse_status` and `llm_emotion` parsed again from the last raw reply;
  - every leaf of `metrics.json` deep-compared with my own computation, including `sample_rating_counts` and `sample_rating_share`;
  - the `run_meta` counts (n_rows, parse_fail, api_error, retry, cache_hits).
- **NRC, 3 emotion runs:**
  - Per row, my own tokenizer, suffix fallback and argmax/TIE/NONE reproduce `nrc_emotion`, `nrc_tied`, `nrc_scores`, `nrc_hits`, `nrc_token_count`, `nrc_emotion_tiebreak`, `nrc_negated_hits` and `emotion_agree`.
  - Every numeric leaf of `emotion_metrics.json` matches: both baselines, tie-break, unique rows, negation, crosstab and divergent ids.
- **comparisons.json:** every field recomputed from my own metrics, not from the files. That covers all 6 Wilson intervals (z = 1.959963984540054) and the population re-weighting (weights, accuracy, per-class precision, and both "share of predictions from" fields).
- **Dashboard** (Playwright headless Chromium; each run selected by clicking `[data-run-tab]`):
  - The data embedded in `index.html` equals the current run files, and the page equals the template plus that data, so it is not a stale build.
  - Every `[data-metric][data-raw]` (226 / 215 / 194 / 65 per run): `data-source` field equals `data-metric`, and the file belongs to the selected run or is `runs/comparisons.json`. `data-raw` equals the file value and my recomputed value. The text shown equals the display rule applied to `data-raw` (pct / count / pp with U+2212 / text, and JS `toFixed` half-up rounding).
  - Every chart mark (131 / 122 / 115 / 14): `data-run` is correct, `data-label` is non-empty, `data-value` equals the recomputed value (`emotion.<field>` resolved in emotion_metrics), and every visible mark with a value above 0 renders larger than 0.5 px in both dimensions.
  - Table rows (id, stars, truth, prediction, correct) match predictions.jsonl in order, and the live count equals n.
  - No "[object", "undefined" or "NaN" on the page, and no console errors.
  - Digits outside `data-metric`, table body excluded: tab labels, the class-rule text, the "1★…5★" labels next to bound counts, "Macro F1", "Prompt sha256", source paths and `#shown-count`, which is filter state. None is an unbound metric.
- **Written numbers:** 110 quoted claims from `reviews/step6_analysis.md`, the Step 6 section of `ISSUES.md` and `PROGRESS.md`. For each, the exact quote was confirmed in the file, then the value or ids were checked against my recomputation. This includes the id groupings of the 25 NEUTRAL→NEGATIVE and 8 NEUTRAL→POSITIVE rows, the v1→v3 flips, the retry row, the emotion splits by class, "gift" in 17 of the 22 anticipation answers, the seed-sensitivity figures and the API-call arithmetic (442).
- **verify_leak.py:** run inside the script. It reports PASS for all 4 runs and exits 0.

Round-1 fixes confirmed:
- 121389 and 140676 are both named, with 138151 as the third leak hit (analysis l.166 and ISSUES).
- The analysis interval is relabelled "plain accuracy" (l.135).
- PROGRESS now points to the verify_dashboard log (3766).
- All population re-weighting figures quoted in the analysis and ISSUES match.

## Script output (verbatim)
```
== data file
rows 152410 excluded 49 pools {'NEGATIVE': 14178, 'NEUTRAL': 3270, 'POSITIVE': 134913} sha ok True
balanced redraw == saved: True | overlap with batch_100: [] | batch_100 = 0..99: True
4-star rows in POSITIVE pool: 6691 (4.96%)
star-phrase TITLE share by pool: {'NEGATIVE': '823/14178=5.8%', 'NEUTRAL': '428/3270=13.1%', 'POSITIVE': '30617/134913=22.7%'}
seeds 0-999: zero 4-star POSITIVE draws 63; NEUTRAL star titles seed42=10 mean=6.613 >=10: 117; whole-draw star titles seed42=26 (title-or-text 26) median=21.0 p5/p95 nearest-rank=14/28 quantiles(inclusive)=14.0/28.0
lexicon words 14154 with 8-emotion tags 4454
== balanced150_v3
acc 110/150 = 73.3% | baseline 33.3% | bal 73.3% | macroF1 70.4% | truth {'POSITIVE': 50, 'NEUTRAL': 50, 'NEGATIVE': 50} | pred {'POSITIVE': 57, 'NEUTRAL': 23, 'NEGATIVE': 70, 'UNPARSED': 0} | stars {1: 43, 2: 7, 3: 50, 5: 50} | cache 4 calls 147
  cells {'POSITIVE->POSITIVE': 48, 'POSITIVE->NEUTRAL': 2, 'NEUTRAL->POSITIVE': 8, 'NEUTRAL->NEUTRAL': 17, 'NEUTRAL->NEGATIVE': 25, 'NEGATIVE->POSITIVE': 1, 'NEGATIVE->NEUTRAL': 4, 'NEGATIVE->NEGATIVE': 45} | misclassified {'POSITIVE->NEUTRAL': [12158, 43820], 'NEUTRAL->POSITIVE': [20086, 23773, 43478, 73030, 134401, 144067, 144273, 146724], 'NEUTRAL->NEGATIVE': [4880, 6689, 18646, 22082, 29467, 32735, 33885, 48586, 51332, 53136, 60608, 60681, 88199, 88606, 88787, 94255, 111780, 111827, 114708, 119458, 121389, 129667, 140179, 143371, 147336], 'NEGATIVE->POSITIVE': [116236], 'NEGATIVE->NEUTRAL': [31137, 49142, 99795, 136849]}
  emotion agree 16/150, single 16/59; const anger 4 (single 4); best anticipation 22 (single 22); TIE 67 NONE 24; llm-in-tie 37 const-in-tie 6; llm!=const {'n': 88, 'agree': 12, 'rate': 0.13636363636363635}; anticipation with 'gift' lemma hit 17/22
  LLM emotion by truth: {'POSITIVE': {'joy': 40, 'trust': 10}, 'NEUTRAL': {'anticipation': 5, 'sadness': 4, 'trust': 11, 'anger': 21, 'joy': 6, 'disgust': 3}, 'NEGATIVE': {'anger': 41, 'anticipation': 3, 'trust': 1, 'fear': 1, 'surprise': 2, 'sadness': 2}}
  NEUTRAL->NEGATIVE LLM emotions: {'sadness': 4, 'anger': 20, 'disgust': 1}
== first100_v3
acc 95/100 = 95.0% | baseline 93.0% | bal 65.6% | macroF1 60.4% | truth {'POSITIVE': 93, 'NEUTRAL': 2, 'NEGATIVE': 5} | pred {'POSITIVE': 91, 'NEUTRAL': 2, 'NEGATIVE': 7, 'UNPARSED': 0} | stars {1: 4, 2: 1, 3: 2, 4: 2, 5: 91} | cache 7 calls 93
  cells {'POSITIVE->POSITIVE': 90, 'POSITIVE->NEUTRAL': 2, 'POSITIVE->NEGATIVE': 1, 'NEUTRAL->POSITIVE': 1, 'NEUTRAL->NEGATIVE': 1, 'NEGATIVE->NEGATIVE': 5} | misclassified {'POSITIVE->NEUTRAL': [46, 83], 'POSITIVE->NEGATIVE': [17], 'NEUTRAL->POSITIVE': [98], 'NEUTRAL->NEGATIVE': [91]}
  emotion agree 20/100, single 20/38; const joy 22 (single 22); best joy 22 (single 22); TIE 47 NONE 15; llm-in-tie 45 const-in-tie 45; llm!=const {'n': 18, 'agree': 0, 'rate': 0.0}; anticipation with 'gift' lemma hit 10/14
  LLM emotion by truth: {'POSITIVE': {'joy': 81, 'trust': 9, 'anger': 1, 'anticipation': 2}, 'NEUTRAL': {'anger': 1, 'joy': 1}, 'NEGATIVE': {'anger': 5}}
== first100_v2
acc 97/100 = 97.0% | baseline 93.0% | bal 91.8% | macroF1 89.2% | truth {'POSITIVE': 93, 'NEGATIVE': 7} | pred {'POSITIVE': 92, 'NEGATIVE': 8, 'UNPARSED': 0} | stars {1: 4, 2: 1, 3: 2, 4: 2, 5: 91} | cache 10 calls 90
  cells {'POSITIVE->POSITIVE': 91, 'POSITIVE->NEGATIVE': 2, 'NEGATIVE->POSITIVE': 1, 'NEGATIVE->NEGATIVE': 6} | misclassified {'POSITIVE->NEGATIVE': [17, 46], 'NEGATIVE->POSITIVE': [98]}
  emotion agree 20/100, single 20/38; const joy 22 (single 22); best joy 22 (single 22); TIE 47 NONE 15; llm-in-tie 45 const-in-tie 45; llm!=const {'n': 20, 'agree': 1, 'rate': 0.05}; anticipation with 'gift' lemma hit 10/14
  LLM emotion by truth: {'POSITIVE': {'joy': 79, 'trust': 9, 'anger': 1, 'anticipation': 3, 'disgust': 1}, 'NEGATIVE': {'anger': 6, 'joy': 1}}
== first100_v1
acc 97/100 = 97.0% | baseline 93.0% | bal 91.8% | macroF1 89.2% | truth {'POSITIVE': 93, 'NEGATIVE': 7} | pred {'POSITIVE': 92, 'NEGATIVE': 8, 'UNPARSED': 0} | stars {1: 4, 2: 1, 3: 2, 4: 2, 5: 91} | cache 10 calls 90
  cells {'POSITIVE->POSITIVE': 91, 'POSITIVE->NEGATIVE': 2, 'NEGATIVE->POSITIVE': 1, 'NEGATIVE->NEGATIVE': 6} | misclassified {'POSITIVE->NEGATIVE': [17, 46], 'NEGATIVE->POSITIVE': [98]}
== comparisons.json
weights {'NEGATIVE': 0.09305530942957843, 'NEUTRAL': 0.021462185204875264, 'POSITIVE': 0.8854825053655463}; reweighted acc 0.9411; prec {'POSITIVE': 0.9938095461715041, 'NEUTRAL': 0.14547481472176862, 'NEGATIVE': 0.8864204734911636}
Wilson: {'first100_v1_accuracy_wilson95': [91.5, 99.0], 'first100_v3_accuracy_wilson95': [88.8, 97.8], 'balanced150_v3_accuracy_wilson95': [65.7, 79.8], 'balanced150_v3_neutral_recall_wilson95': [22.4, 47.8], 'balanced150_v3_neutral_to_negative_share_wilson95': [36.6, 63.4], 'balanced150_v3_neutral_to_positive_share_wilson95': [8.3, 28.5]}
== verify_leak.py
PASS runs/balanced150_v3/predictions.jsonl: 150 rows, prompt prompts/sentiment_v3.txt; 26 rows had a star-phrase title/text blanked; 3 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v1/predictions.jsonl: 100 rows, prompt prompts/sentiment_v1.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v2/predictions.jsonl: 100 rows, prompt prompts/sentiment_v2.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v3/predictions.jsonl: 100 rows, prompt prompts/sentiment_v3.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)  exit=0
balanced rows whose sent title/text contain forbidden words: [(121389, ['stars']), (138151, ['Helpful']), (140676, ['stars'])]
  balanced150_v3 star-phrase title-or-text rows: 26, title-only: 26
  first100_v3 star-phrase title-or-text rows: 4, title-only: 4
  first100_v2 star-phrase title-or-text rows: 4, title-only: 4
  first100_v1 star-phrase title-or-text rows: 4, title-only: 4
== dashboard (Playwright headless Chromium)
balanced150_v3: 226 data-metric numbers, 131 chart marks, 150 table rows; numeric fields shown as text: ['seed', 'temperature']
  visible digit text outside data-metric (table body excluded): ['"MBAX 6418 · Assignment 1 · Amazon Reviews \'23, Gift Cards"', '"Balanced 150 · three classes"', '"First 100 · three classes"', '"First 100 · two classes + emotion"', '"First 100 · two classes"', '#run-blurb "three classes; answer key from the stars: 4–5★ positive, 3★ neutral, 1–2★ negative"', '"1★"', '"2★"', '"3★"', '"4★"', '"5★"', '"Macro F1"', '#shown-count "150"', '"Prompt sha256"', '"runs/balanced150_v3/metrics.json"', '"runs/balanced150_v3/predictions.jsonl"']
first100_v3: 215 data-metric numbers, 122 chart marks, 100 table rows; numeric fields shown as text: ['seed', 'temperature']
  visible digit text outside data-metric (table body excluded): ['"MBAX 6418 · Assignment 1 · Amazon Reviews \'23, Gift Cards"', '"Balanced 150 · three classes"', '"First 100 · three classes"', '"First 100 · two classes + emotion"', '"First 100 · two classes"', '#run-blurb "three classes; answer key from the stars: 4–5★ positive, 3★ neutral, 1–2★ negative"', '"1★"', '"2★"', '"3★"', '"4★"', '"5★"', '"Macro F1"', '#shown-count "100"', '"Prompt sha256"', '"runs/first100_v3/metrics.json"', '"runs/first100_v3/predictions.jsonl"']
first100_v2: 194 data-metric numbers, 115 chart marks, 100 table rows; numeric fields shown as text: ['seed', 'temperature']
  visible digit text outside data-metric (table body excluded): ['"MBAX 6418 · Assignment 1 · Amazon Reviews \'23, Gift Cards"', '"Balanced 150 · three classes"', '"First 100 · three classes"', '"First 100 · two classes + emotion"', '"First 100 · two classes"', '#run-blurb "two classes; answer key from the stars: 4–5★ positive, 1–3★ negative"', '"1★"', '"2★"', '"3★"', '"4★"', '"5★"', '"Macro F1"', '#shown-count "100"', '"Prompt sha256"', '"runs/first100_v2/metrics.json"', '"runs/first100_v2/predictions.jsonl"']
first100_v1: 65 data-metric numbers, 14 chart marks, 100 table rows; numeric fields shown as text: ['seed', 'temperature']
  visible digit text outside data-metric (table body excluded): ['"MBAX 6418 · Assignment 1 · Amazon Reviews \'23, Gift Cards"', '"Balanced 150 · three classes"', '"First 100 · three classes"', '"First 100 · two classes + emotion"', '"First 100 · two classes"', '#run-blurb "two classes; answer key from the stars: 4–5★ positive, 1–3★ negative"', '"1★"', '"2★"', '"3★"', '"4★"', '"5★"', '"Macro F1"', '#shown-count "100"', '"Prompt sha256"', '"runs/first100_v1/metrics.json"', '"runs/first100_v1/predictions.jsonl"']
== written claims
v1 -> v3 moved on batch_100: [(46, 'NEGATIVE', 'NEUTRAL'), (83, 'POSITIVE', 'NEUTRAL')]
retry rows: [('balanced150_v3', 4880, ['LABEL=NEGATIVE;EMOTION=disappointment', 'LABEL=NEGATIVE;EMOTION=sadness'])] | dup groups: [('Five Stars', 'Great gift')] | gift anticipation: 17
Wilson half-widths (pts): {'first100_v1_accuracy_wilson95': 3.75, 'first100_v3_accuracy_wilson95': 4.5, 'balanced150_v3_accuracy_wilson95': 7.049999999999997, 'balanced150_v3_neutral_recall_wilson95': 12.7, 'balanced150_v3_neutral_to_negative_share_wilson95': 13.399999999999999, 'balanced150_v3_neutral_to_positive_share_wilson95': 10.1}
  FAIL: [PROGRESS] 'Wilson 95% (comparisons.json): balanced accuracy 65.7–79.8%' does not hold (label: comparisons.json balanced150_v3_accuracy_wilson95 = Wilson(110,150), the interval for plain accuracy, not balanced accuracy)
written claims checked: 110
TOTAL checks: 15151; FAILURES: 1
  - [PROGRESS] 'Wilson 95% (comparisons.json): balanced accuracy 65.7–79.8%' does not hold (label: comparisons.json balanced150_v3_accuracy_wilson95 = Wilson(110,150), the interval for plain accuracy, not balanced accuracy)
exit=1
```

## Findings

No value mismatches in metrics.json, emotion_metrics.json, comparisons.json, the dashboard DOM or any of the 110 written claims. No BLOCKERs.

1. MINOR — `PROGRESS.md` line 10 — **the round-1 mislabel is still here: a Wilson interval for plain accuracy is called "balanced accuracy".** The round-1 log in ISSUES.md says it was relabelled, but only the analysis was fixed.
   - Evidence: PROGRESS.md l.10 reads "Wilson 95% (comparisons.json): balanced accuracy 65.7–79.8%".
   - `balanced150_v3_accuracy_wilson95` = Wilson(110, 150), which my script recomputes as [65.7, 79.8]. That is the interval for plain accuracy.
   - `reviews/step6_analysis.md` l.135 already says "plain accuracy of the run 65.7%–79.8%".
   - Script output: `[PROGRESS] 'Wilson 95% (comparisons.json): balanced accuracy 65.7–79.8%' does not hold`.
   - Same line: "review 121389 text says "5 stars"" names only one of the two star mentions; l.20 of the same file names both.
   - Suggested fix: change it to "accuracy 65.7–79.8%" and list 140676 next to 121389.

2. MINOR — `reviews/step6_analysis.md` line 132 (with l.135) — **"±13 points" does not fit every interval listed under it.** The lead-in says "With 50 reviews per class, each share could move by roughly ±13 points:", but one bullet is plain accuracy over 150 rows, whose half-width is about 7.0 points.
   - Script output: `Wilson half-widths (pts): {... 'balanced150_v3_accuracy_wilson95': 7.05, 'balanced150_v3_neutral_recall_wilson95': 12.7, 'balanced150_v3_neutral_to_negative_share_wilson95': 13.4, 'balanced150_v3_neutral_to_positive_share_wilson95': 10.1}` (65.7%–79.8% for accuracy).
   - The next bullet's NEUTRAL→POSITIVE interval (8.3%–28.5%) is also asymmetric, about −7.7 / +12.5.
   - Suggested fix: say "each per-class share (n = 50) could move by roughly ±13 points", and give plain accuracy (n = 150) as about ±7 points. Or just give the intervals without a single ± figure.
