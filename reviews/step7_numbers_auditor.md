# Step 7 — Numbers Auditor

Scope: Step 7 "Descriptive and prediction visualizations", on the complete dashboard with four runs (balanced150_v3, first100_v3, first100_v2, first100_v1). There is no README yet. Written numbers checked are in the Step 7 entries of ISSUES.md and PROGRESS.md.

## Result

No findings.

## What was checked

My script is `reviews/step7_numbers_auditor/audit.py`. It imports no project module and re-implements every rule from the docstrings. Its output is saved in `reviews/step7_numbers_auditor/audit_output.txt` and copied in full below.

1. **Whole file** (all 152,410 lines of `data/Gift_Cards.jsonl.gz`). Recomputed `rating_counts`, `rating_pct` (rounded to 4 places), `rating_share`, `rows_failing_inclusion` and the per-rating failing counts. All match `runs/rating_distribution.json`, and every rating is an integer value.
2. **Samples.**
   - first100 runs: ids equal the first 100 included rows.
   - balanced150_v3: redrew `random.Random(42).sample(sorted pool, 50)` for each class. The result equals `sample_ids.json` (`by_class` and `review_ids`) and the ids in predictions. Pool sizes 14,178 / 3,270 / 134,913 match `sample_ids.json` and `run_meta.json`.
   - Every prediction row's title, text and rating equals its line in the data file (review_id = 0-based line index).
3. **Per-run metrics.**
   - Truth labels recomputed from the rating: three classes for v3, binary for v1/v2.
   - Each prediction and LLM emotion re-parsed from `raw_responses` with my own strict parser.
   - Every leaf of every `metrics.json` recomputed, with nothing missing or extra: accuracy, confusion matrix, cells, row shares, per-class precision/recall/F1/support/correct/wrong, majority baseline, balanced accuracy, macro F1, sample star counts and shares, misclassified ids, parse and retry counts. `run_meta` counts also cross-checked.
4. **Emotions.**
   - Lexicon sha256, word count (14,154) and 8-emotion word count (4,454) verified against `runs/nrc_lexicon_meta.json`.
   - Per row, every NRC field in predictions recomputed: emotion, tied set, scores, hits, token count, tie-break label, negated hits, `emotion_agree`.
   - Every numeric or label field of the 3 `emotion_metrics.json` files recomputed. Prose fields (`method`, notes, rules) are excluded.
   - first100_v1 has no emotions and no `emotion_metrics.json`, which is consistent.
5. **`runs/comparisons.json`.** Every field recomputed, excluding the note, sources and weighting note. This includes the Wilson 95% intervals, the population pools and weights (derived again from the data file), the re-weighted accuracy, precision and shares, the expected-from-recalls accuracy, the one-more-NEUTRAL counterfactual, and all emotion comparison fields.
6. **Dashboard** (`dashboard/index.html`, Playwright headless Chromium, each run selected by clicking `[data-run-tab]`, at 1440px and at 400px wide).
   - The data embedded in the page equals the files on disk (the build is not stale).
   - Every `[data-metric]` number (250 / 239 / 217 / 88 per run) matches my recomputed value, not just the file. Its `data-source` resolves to that run's file, `data-metric` equals the source field, `data-raw` equals the value, and the visible text equals the display rule (exact-binary `toFixed(1)` rounding, en-US commas, "+/− N.N pts").
   - Every chart mark (140 / 132 / 125 / 24 per run) has all 4 attributes. `data-value` matches my value under the mark conventions (`__file__`, `emotion.`, `metrics.json`).
   - Every mark with value > 0 is visible and at least 2×2 px at both widths.
   - Bar length matches its value within 1 px: share of the track for the star bars, value/max for the paired-class and emotion bars, flex share with gaps for the per-class segments. This rules out collapsed or overflowing bars.
   - Every mark with value > 0 has a visible tagged label in its own row or cell showing its true count.
   - No console or page errors.
7. **Written Step 7 numbers.** All are present verbatim and correct: 152,410 rows; 5★ 84.1%; 2★ 1.2% (the smallest file class); batch_100 91% 5★; the balanced sample has no 4★; NEUTRAL 50 vs 23; NEGATIVE 50 vs 70; the "· 2 wrong" example; and "4,404 checks, 0 failures", which matches the last line of `reviews/step7_verify_dashboard.txt`.

Untagged digit text on the page, outside the review table, is limited to:
- the eyebrow ("MBAX 6418", "'23")
- the scheme sentence ("4–5★", "1–2★")
- the star axis labels "1★"–"5★"
- "Macro F1" and "Prompt sha256"
- source file paths
- the live filter count in `#shown-count` ("150" / "100"), which carries `data-live-count` and is checked by the filter tests

None of these is a metric value.

## Project checks re-run

```
$ .venv/bin/python src/verify_leak.py
PASS runs/balanced150_v3/predictions.jsonl: 150 rows, prompt prompts/sentiment_v3.txt; 26 rows had a star-phrase title/text blanked; 3 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v1/predictions.jsonl: 100 rows, prompt prompts/sentiment_v1.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v2/predictions.jsonl: 100 rows, prompt prompts/sentiment_v2.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v3/predictions.jsonl: 100 rows, prompt prompts/sentiment_v3.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
EXIT=0

$ .venv/bin/python src/verify_dashboard.py | tail -3     (read-only; confirms the written check count is current)
4404 checks, 0 failures
PASS
```

## Script output

```
$ .venv/bin/python reviews/step7_numbers_auditor/audit.py
[file] rows 152410; counts {1: 12326, 2: 1873, 3: 3271, 4: 6692, 5: 128248}; failing inclusion 49
[balanced150_v3] accuracy 110/150; truth {'POSITIVE': 50, 'NEUTRAL': 50, 'NEGATIVE': 50}; predicted {'POSITIVE': 57, 'NEUTRAL': 23, 'NEGATIVE': 70, 'UNPARSED': 0}
[balanced150_v3] emotions: agree 16/150; TIE 67; NONE 24; constant anger; best anticipation
[first100_v3] accuracy 95/100; truth {'POSITIVE': 93, 'NEUTRAL': 2, 'NEGATIVE': 5}; predicted {'POSITIVE': 91, 'NEUTRAL': 2, 'NEGATIVE': 7, 'UNPARSED': 0}
[first100_v3] emotions: agree 20/100; TIE 47; NONE 15; constant joy; best joy
[first100_v2] accuracy 97/100; truth {'POSITIVE': 93, 'NEGATIVE': 7}; predicted {'POSITIVE': 92, 'NEGATIVE': 8, 'UNPARSED': 0}
[first100_v2] emotions: agree 20/100; TIE 47; NONE 15; constant joy; best joy
[first100_v1] accuracy 97/100; truth {'POSITIVE': 93, 'NEGATIVE': 7}; predicted {'POSITIVE': 92, 'NEGATIVE': 8, 'UNPARSED': 0}
[balanced150_v3 @1440px] dashboard: 250 tagged numbers (227 distinct fields), 140 marks; untagged digit text: ["MBAX 6418 · Assignment 1 · Amazon Reviews '23, Gift Cards", 'three classes; answer key from the stars: 4–5★ positive, 3★ neutral, 1–2★ negative', '1★', '2★', '3★', '4★', '5★', 'Macro F1', '150', 'Prompt sha256', 'runs/balanced150_v3/metrics.json', 'runs/balanced150_v3/predictions.jsonl']
[first100_v3 @1440px] dashboard: 239 tagged numbers (217 distinct fields), 132 marks; untagged digit text: ["MBAX 6418 · Assignment 1 · Amazon Reviews '23, Gift Cards", 'three classes; answer key from the stars: 4–5★ positive, 3★ neutral, 1–2★ negative', '1★', '2★', '3★', '4★', '5★', 'Macro F1', '100', 'Prompt sha256', 'runs/first100_v3/metrics.json', 'runs/first100_v3/predictions.jsonl']
[first100_v2 @1440px] dashboard: 217 tagged numbers (197 distinct fields), 125 marks; untagged digit text: ["MBAX 6418 · Assignment 1 · Amazon Reviews '23, Gift Cards", 'two classes; answer key from the stars: 4–5★ positive, 1–3★ negative', '1★', '2★', '3★', '4★', '5★', 'Macro F1', '100', 'Prompt sha256', 'runs/first100_v2/metrics.json', 'runs/first100_v2/predictions.jsonl']
[first100_v1 @1440px] dashboard: 88 tagged numbers (69 distinct fields), 24 marks; untagged digit text: ["MBAX 6418 · Assignment 1 · Amazon Reviews '23, Gift Cards", 'two classes; answer key from the stars: 4–5★ positive, 1–3★ negative', '1★', '2★', '3★', '4★', '5★', 'Macro F1', '100', 'Prompt sha256', 'runs/first100_v1/metrics.json', 'runs/first100_v1/predictions.jsonl']
[balanced150_v3 @400px] dashboard: 250 tagged numbers (227 distinct fields), 140 marks; untagged digit text: ["MBAX 6418 · Assignment 1 · Amazon Reviews '23, Gift Cards", 'three classes; answer key from the stars: 4–5★ positive, 3★ neutral, 1–2★ negative', '1★', '2★', '3★', '4★', '5★', 'Macro F1', '150', 'Prompt sha256', 'runs/balanced150_v3/metrics.json', 'runs/balanced150_v3/predictions.jsonl']
[first100_v3 @400px] dashboard: 239 tagged numbers (217 distinct fields), 132 marks; untagged digit text: ["MBAX 6418 · Assignment 1 · Amazon Reviews '23, Gift Cards", 'three classes; answer key from the stars: 4–5★ positive, 3★ neutral, 1–2★ negative', '1★', '2★', '3★', '4★', '5★', 'Macro F1', '100', 'Prompt sha256', 'runs/first100_v3/metrics.json', 'runs/first100_v3/predictions.jsonl']
[first100_v2 @400px] dashboard: 217 tagged numbers (197 distinct fields), 125 marks; untagged digit text: ["MBAX 6418 · Assignment 1 · Amazon Reviews '23, Gift Cards", 'two classes; answer key from the stars: 4–5★ positive, 1–3★ negative', '1★', '2★', '3★', '4★', '5★', 'Macro F1', '100', 'Prompt sha256', 'runs/first100_v2/metrics.json', 'runs/first100_v2/predictions.jsonl']
[first100_v1 @400px] dashboard: 88 tagged numbers (69 distinct fields), 24 marks; untagged digit text: ["MBAX 6418 · Assignment 1 · Amazon Reviews '23, Gift Cards", 'two classes; answer key from the stars: 4–5★ positive, 1–3★ negative', '1★', '2★', '3★', '4★', '5★', 'Macro F1', '100', 'Prompt sha256', 'runs/first100_v1/metrics.json', 'runs/first100_v1/predictions.jsonl']
[written] ISSUES: whole file 152,410 rows: present=True correct=True
[written] ISSUES: 5★ 84.1%: present=True correct=True
[written] ISSUES: 2★ 1.2%: present=True correct=True
[written] ISSUES: 2★ smallest whole-file class ("small value such as 2★ at 1.2%"): present=True correct=True
[written] ISSUES: batch_100 91% 5★: present=True correct=True
[written] ISSUES: balanced sample drops 4★ entirely: present=True correct=True
[written] ISSUES: NEUTRAL 50 stars vs 23 model: present=True correct=True
[written] ISSUES: NEGATIVE 50 vs 70: present=True correct=True
[written] ISSUES: "· 2 wrong" example exists (balanced POSITIVE wrong 2): present=True correct=True
[written] ISSUES/PROGRESS: 4,404 checks, 0 failures (matches reviews/step7_verify_dashboard.txt): present=True correct=True

18529 checks, 0 mismatches
```
