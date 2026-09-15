# Step 2 — Numbers Auditor

Scope: Step 2 "Score against the rating" (binary truth, rating >= 4 -> POSITIVE, `batch_100`).
No dashboard or README exist at this step, so the written numbers checked are in `reviews/step2_analysis.md` and the Step 2 entries of `ISSUES.md` (plus the Step 0 "~88.5% POSITIVE" figure those entries lean on).

## Method

- Script: `reviews/step2_numbers_auditor/audit_step2.py`. It imports nothing from `src/`.
- Full output: `reviews/step2_numbers_auditor/audit_step2_output.txt`.
- Command: `.venv/bin/python reviews/step2_numbers_auditor/audit_step2.py`
- What the script does:
  - Re-reads `data/Gift_Cards.jsonl.gz` and re-derives the batch selection (first 100 included ids) and the truth label for each row from the source rating.
  - Re-parses each stored `raw_responses` with its own parser.
  - Recomputes every key in `metrics.json` (a guard fails if any key goes unchecked) and the count fields in `run_meta.json` (cache hits, API calls, parse failures, API errors, retries), and all of `rating_distribution.json` from the full file.
  - Checks each number and each quoted title, text, id and rating in `step2_analysis.md` and the `ISSUES.md` Step 2 entries.
- Leak check: `.venv/bin/python src/verify_leak.py`

## Leak check output

```
PASS runs/first100_v1/predictions.jsonl: 100 rows, prompt prompts/sentiment_v1.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
EXIT=0
```

## Audit script output (condensed; every line is in the output file)

```
== selection / source integrity
OK   n rows 100; review_ids unique 100; review_ids == first 100 included ids [0..99]
OK   run_meta dataset_row_count 152410; run_meta n_rows 100
== truth re-derived from source rating (>=4 POSITIVE else NEGATIVE)
OK   stored truth == re-derived truth (mismatch count): 0
== prediction re-parsed from raw_responses (own strict parser)
OK   stored prediction == re-parsed (mismatch count): 0
OK   raw responses exactly 'LABEL=X' (non-exact count): 0
== metrics.json recomputation
OK   correct 97, incorrect 3, accuracy 0.97
OK   truth counts {'POSITIVE': 93, 'NEGATIVE': 7}, shares 0.93 / 0.07
OK   prediction counts {'POSITIVE': 92, 'NEGATIVE': 8, 'UNPARSED': 0}, shares 0.92 / 0.08 / 0.0
OK   majority_class POSITIVE; majority_baseline_accuracy 0.93; accuracy_minus_majority_baseline 0.039999999999999925
OK   balanced_accuracy 0.9178187403993856; majority_baseline_balanced_accuracy 0.5; macro_f1 0.8918918918918919
OK   POSITIVE support 93 predicted 92 correct 91 wrong 2 precision 0.9891304347826086 recall 0.978494623655914 f1 0.9837837837837837
OK   NEGATIVE support 7 predicted 8 correct 6 wrong 1 precision 0.75 recall 0.8571428571428571 f1 0.7999999999999999
OK   confusion counts [[91, 2, 0], [1, 6, 0]]; all 6 confusion_cells and 6 confusion_row_share values
OK   misclassified_review_ids {'POSITIVE->NEGATIVE': [17, 46], 'NEGATIVE->POSITIVE': [98]}
OK   parse_fail_count 0, api_error_count 0, unparsed_count 0, unparsed_share 0.0, rows_needing_retry 0
OK   metrics.json keys not covered by this audit: []
== run_meta.json
OK   parse_fail_count / api_error_count / rows_needing_retry agree with metrics
OK   cache_hits 10 == rows from_cache; api_call_count 90 == rows not from cache
== rating_distribution.json (recomputed from full file)
OK   row_count 152410; rating_counts {1: 12326, 2: 1873, 3: 3271, 4: 6692, 5: 128248}
OK   rating_pct 8.0874 / 1.2289 / 2.1462 / 4.3908 / 84.1467
OK   rows_failing_inclusion 49; by rating {1: 18, 2: 3, 3: 1, 4: 1, 5: 26}
== claims in reviews/step2_analysis.md and ISSUES.md
OK   97.0%, 93.0%, +4.0 pp, balanced 91.8%
OK   POSITIVE recall 91/93=97.8, precision 91/92=98.9; NEGATIVE recall 6/7=85.7, precision 6/8=75.0, F1 0.800; 14.3 pts per negative
OK   id 17 (5, POSITIVE, NEGATIVE) title 'No note attached to sent gift card'; text contains quoted phrases
OK   id 46 (5, POSITIVE, NEGATIVE) 'Love it!!' / 'This is an online gift card nothing to show sorry🤪'
OK   id 98 (3, NEGATIVE, POSITIVE) 'Easy to use' / 'Very easy to use. I wish I knew about it earlier'
OK   1-2 star ids [4, 15, 32, 51, 63], all predicted NEGATIVE; 3 star ids [91, 98] -> NEGATIVE, POSITIVE
     duplicate (title,text) groups: {('Good Product', 'Good Product'): [20, 21, 22, 23, 24, 27, 28], ('Good product', 'Good product'): [25, 26]}
OK   rows in duplicate groups 9; rows that repeat an earlier row 7
OK   cache-hit ids [0, 1, 2, 21, 22, 23, 24, 26, 27, 28] = 3 preview + 7 repeats
OK   ISSUES Step 0: file share POSITIVE 88.5%

TOTAL FAILS: 0 []
```

## Findings

MINOR — `ISSUES.md` line 23 ("[Step 2] Duplicate reviews inside batch_100") and `reviews/step2_analysis.md` last bullet — the count of duplicates can be misread. "9 of the 100 rows are copies" counts every row in the two duplicate groups, including the first row of each group, which is the original. Only 7 rows repeat an earlier row. The analysis then says these rows "pad the easy-POSITIVE share", which suggests 9 extra rows when there are 7. The same ISSUES entry later says "7 repeats", which is correct, so the two numbers in that entry look inconsistent. — Evidence: the audit script prints `rows in duplicate groups (ISSUES: '9 of the 100'): recomputed=9` and `rows that are repeats of an earlier row: recomputed=7`, with groups `'Good Product'` [20, 21, 22, 23, 24, 27, 28] and `'Good product'` [25, 26]. Quoted text: "9 of the 100 rows are copies" and "9 of the 100 rows are duplicate "Good Product" reviews". The second quote also leaves out the lowercase "Good product" pair. — Suggested fix: reword to "9 rows fall in two duplicate groups ('Good Product' ×7, 'Good product' ×2), i.e. 7 rows repeat an earlier row", and use that wording in both files.

No BLOCKER or MAJOR findings. Every metric in `metrics.json` and `run_meta.json`, every value in `rating_distribution.json`, and every Step 2 number and quoted review in `reviews/step2_analysis.md` and `ISSUES.md` matches the independent recomputation, and `verify_leak.py` passes.
