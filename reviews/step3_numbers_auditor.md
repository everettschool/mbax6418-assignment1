# Step 3 — Numbers Auditor

Step under review: Step 3, "A results dashboard" (one run, `first100_v1`; no README yet).

## What was checked

- **Script:** `reviews/step3_numbers_auditor/audit_step3.py`, run as `.venv/bin/python reviews/step3_numbers_auditor/audit_step3.py`. It imports nothing from `src/`.
  1. It works out truth again from `rating` (4 or more is POSITIVE, anything lower is NEGATIVE). It re-reads each prediction from `raw_responses` with its own strict parser. It recomputes every metric from `predictions.jsonl` and compares all 62 leaf values of `metrics.json`.
  2. It checks that `dashboard/index.html` is a fresh build:
     - the page shell is byte-identical to `template.html`;
     - the embedded JSON equals `metrics.json`, `run_meta.json`, `predictions.jsonl` (all 100 rows), `rating_distribution.json`, and `manifest.json`.
  3. It opens the built page in headless Chromium and reads every value from the DOM:
     - **Metric numbers (all 56 with `data-metric`):**
       - `data-source` resolves to a real file and field;
       - the file value equals `data-raw`, which equals the recomputed value;
       - the visible text follows the display rules (percentages are fraction × 100 to 1 decimal; counts are integers; "pts" for the gap);
       - `data-metric` equals the field named in `data-source`.
     - **Chart marks (all 14):**
       - `data-run`, `data-metric`, `data-value` and `data-label` are all present;
       - each value equals the recomputed value and `metrics.json`;
       - marks with a value above zero render with non-zero width and height;
       - stacked-bar widths are in proportion to the counts.
     - **Confusion matrix:** DOM order and headers show rows = truth and columns = predicted.
     - **Review table:** all 100 rows match on id, stars, answer key, prediction, and Match/Miss. The Miss ids are 17, 46, 98.
     - **Headline sentences:** the weakest class is chosen correctly.
     - **Page health:** 0 console errors and 0 network requests other than the local file.
     - **Stray numbers:** every visible text node with a digit that is outside a tagged metric span and outside the review table is listed.
- **`src/verify_leak.py`:** run as `.venv/bin/python src/verify_leak.py`. It passed.

**Result:** 0 mismatches between `predictions.jsonl`, `metrics.json` and the rendered DOM. No README exists at this step, so none was checked. Two MINOR display-rule and provenance gaps are listed below.

## Findings

MINOR — `dashboard/template.html` line 434–435 (`renderReviews`, the `#row-count` element "Showing 100 of 100 reviews") — this count is shown on the page but has no `data-metric`, `data-raw` or `data-source`. The display rules exempt only per-review table cells, and this line sits above the table. The page also computes the value itself (`rows.length`) instead of reading it from a saved field. The build script's own docstring says the page "never computes a published metric of its own". The value is correct today (100 = `metrics.json#n_rows`), but no DOM check can tie it to a source. — Evidence: the audit script's DOM read returned `row-count element: {'text': 'Showing 100 of 100 reviews', 'live': '100', 'metric': None, 'raw': None, 'source': None}`, and the untagged-digit scan lists `[row-count] '100'` twice. — Suggested fix: render the total as `M(run, "n_rows", "count")`. Give the shown-count number (which becomes live in Step 4) `data-metric`/`data-raw` as well, with `data-source` naming the filter it comes from, e.g. `predictions.jsonl#filter=all`. A Step 4 check can then assert shown count = number of visible rows, and total = `n_rows`.

MINOR — `dashboard/manifest.json` `runs[0].blurb` and `label`, shown in `#run-blurb` and the run tab — facts about the run are typed in by hand rather than read from run files: "The first 100 reviews", "First 100 · two classes", "Answer key: 4–5★ positive, 1–3★ negative". They agree with `run_meta.json` today (`n_rows` 100, `selection_rule` "first 100 review_ids in file order…", `label_scheme` binary, truth rule matches all 100 rows). But the page's Method section says "Everything on this page is read from the run's saved files; nothing is typed in by hand", and these numbers carry no `data-source`. Once Step 6 adds balanced runs, a copied or stale blurb would publish unchecked numbers. — Evidence: the untagged-digit scan printed `[run-tabs] 'First 100 · two classes'` and `[run-blurb] 'The first 100 reviews in the file, scored POSITIVE or NEGATIVE with prompt v1. Answer key: 4–5★ positive, 1–3★ negative.'` — Suggested fix: either build the count and answer-key rule from `run_meta.json` (`n_rows`, `selection_rule`, `label_scheme`) as tagged `META(...)` spans, or add a build-time check in `build_dashboard.py` that the number in the blurb or label equals `run_meta.n_rows` and the stated star rule matches `label_scheme`.

## Script output

`reviews/step3_numbers_auditor/audit_step3_output.txt` (exit 0):

```
== 1. inputs
OK   rows: expected=100 got=100
OK   unique ids: expected=100 got=100
OK   stored truth mismatches vs rating>=4 rule: expected=0 got=0
OK   stored prediction mismatches vs re-parse: expected=0 got=0
== 1b. metrics.json vs recomputation (every leaf)
OK   metrics.json leaf paths == recomputed leaf paths: identical (1951 chars) ['accuracy', 'accuracy_minus_majority_baseline', 'api_error_count', 'balanced_accuracy', 'confusion_...
     62 leaves compared, 0 mismatches
OK   run_meta n_rows: expected=100 got=100
OK   run_meta parse_fail_count: expected=0 got=0
OK   run_meta api_error_count: expected=0 got=0
OK   run_meta labels: expected=['POSITIVE', 'NEGATIVE'] got=['POSITIVE', 'NEGATIVE']
== 2. index.html freshness
OK   page shell == template.html: expected=True got=True
OK   embedded title == manifest: expected='Gift card reviews: does the model agree with the stars?' got='Gift card reviews: does the model agree with the stars?'
OK   embedded rating_distribution == file: identical (394 chars) {'source_file': 'Gift_Cards.jsonl.gz', 'row_count': 152410, 'rating_counts': {'1': 12326, '2': 1873,...
OK   embedded runs == manifest runs: expected=['first100_v1'] got=['first100_v1']
OK   embedded metrics == metrics.json: identical (1915 chars) {'run': 'first100_v1', 'label_scheme': 'binary', 'labels': ['POSITIVE', 'NEGATIVE'], 'confusion_matr...
OK   embedded meta values == run_meta.json: identical (757 chars) {'run': 'first100_v1', 'model': 'cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit', 'endpoint': 'course-endpoint', ...
OK   embedded rows == predictions.jsonl (mismatching ids): expected=[] got=[]
OK   embedded row count: expected=100 got=100
== 3. DOM (headless Chromium)
OK   console/page errors: expected=[] got=[]
OK   non-file requests: expected=[] got=[]
     56 tagged metric numbers
     metric numbers with any failure: 0
     formats: {'pct': 23, 'count': 26, 'pp': 1, 'text': 6} | distinct fields: 49
     metrics.json fields shown on page: ['accuracy', 'accuracy_minus_majority_baseline', 'balanced_accuracy', 'confusion_cells.NEGATIVE->NEGATIVE', 'confusion_cells.NEGATIVE->POSITIVE', 'confusion_cells.NEGATIVE->UNPARSED', 'confusion_cells.POSITIVE->NEGATIVE', 'confusion_cells.POSITIVE->POSITIVE', 'confusion_cells.POSITIVE->UNPARSED', 'confusion_row_share.NEGATIVE->NEGATIVE', 'confusion_row_share.NEGATIVE->POSITIVE', 'confusion_row_share.NEGATIVE->UNPARSED', 'confusion_row_share.POSITIVE->NEGATIVE', 'confusion_row_share.POSITIVE->POSITIVE', 'confusion_row_share.POSITIVE->UNPARSED', 'correct', 'macro_f1', 'majority_baseline_accuracy', 'majority_baseline_balanced_accuracy', 'n_rows', 'per_class.NEGATIVE.correct', 'per_class.NEGATIVE.precision', 'per_class.NEGATIVE.recall', 'per_class.NEGATIVE.support', 'per_class.POSITIVE.correct', 'per_class.POSITIVE.precision', 'per_class.POSITIVE.recall', 'per_class.POSITIVE.support', 'prediction_distribution.counts.NEGATIVE', 'prediction_distribution.counts.POSITIVE', 'prediction_distribution.counts.UNPARSED', 'prediction_distribution.share.NEGATIVE', 'prediction_distribution.share.POSITIVE', 'prediction_distribution.share.UNPARSED', 'truth_distribution.counts.NEGATIVE', 'truth_distribution.counts.POSITIVE', 'truth_distribution.share.NEGATIVE', 'truth_distribution.share.POSITIVE', 'unparsed_count']
OK   [data-metric] numbers missing data-raw/data-source: expected=0 got=0
     14 chart marks
     chart marks with any failure: 0
     marks by metric group: {'truth_distribution': 2, 'prediction_distribution': 2, 'confusion_cells': 6, 'per_class': 4}
     truth_distribution.counts.POSITIVE: width share 0.930 vs count share 0.930
     truth_distribution.counts.NEGATIVE: width share 0.070 vs count share 0.070
     prediction_distribution.counts.POSITIVE: width share 0.920 vs count share 0.920
     prediction_distribution.counts.NEGATIVE: width share 0.080 vs count share 0.080
OK   confusion cells DOM order (row-major, rows=truth, cols=pred): expected=['POSITIVE->POSITIVE', 'POSITIVE->NEGATIVE', 'POSITIVE->UNPARSED', 'NEGATIVE->POSITIVE', 'NEGATIVE->NEGATIVE', 'NEGATIVE->UNPARSED'] got=['POSITIVE->POSITIVE', 'POSITIVE->NEGATIVE', 'POSITIVE->UNPARSED', 'NEGATIVE->POSITIVE', 'NEGATIVE->NEGATIVE', 'NEGATIVE->UNPARSED']
OK   confusion column headers (predicted): expected=['Positive', 'Negative', 'Unparsed'] got=['Positive', 'Negative', 'Unparsed']
OK   confusion row headers (truth): expected=['Positive', 'Negative'] got=['Positive', 'Negative']
OK   confusion grid column count (header + 3): expected=4 got=4
     cell labels: ['Stars: Positive → model: Positive', 'Stars: Positive → model: Negative', 'Stars: Positive → model: Unparsed', 'Stars: Negative → model: Positive', 'Stars: Negative → model: Negative', 'Stars: Negative → model: Unparsed']
OK   table row count: expected=100 got=100
OK   table ids in order: identical (390 chars) [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 2...
OK   table rows disagreeing with recomputation: expected=[] got=[]
OK   table Miss rows == recomputed incorrect: expected=3 got=3
OK   Miss ids: expected=[17, 46, 98] got=[17, 46, 98]
     row-count element: {'text': 'Showing 100 of 100 reviews', 'live': '100', 'metric': None, 'raw': None, 'source': None}
OK   row-count text: expected='Showing 100 of 100 reviews' got='Showing 100 of 100 reviews'
     verdict-line: Reading the reviews is worth +4.0 pts over that shortcut. Weakest class: Negative, 6 of 7 right (85.7%).
OK   weakest class named: expected=True got=True
     verdict-head: The model matches the stars on 97.0% of these reviews. Answering “Positive” every time would score 93.0%.
     hero: Agreement with the star rating |  | 97.0% |  | 97 of 100 reviews match the answer key. |  | Unreadable model replies: 0 (counted as wrong).
     classes: Right answers by class |  | For each answer-key class: how many reviews the model got right (recall). Small classes swing on one or two reviews. |  | Positive | 91 of 93 · 97.8% | Negative | 6 of 7 · 85.7% | Right | Wrong |  | When the model says a class, how often it is right (precision): Positive 98.9% · Negative 75.0%
     blurb: The first 100 reviews in the file, scored POSITIVE or NEGATIVE with prompt v1. Answer key: 4–5★ positive, 1–3★ negative.
     visible text nodes with digits outside tagged metric spans and the review table:
       [P] "MBAX 6418 · Assignment 1 · Amazon Reviews '23, Gift Cards"
       [run-tabs] 'First 100 · two classes'
       [run-blurb] 'The first 100 reviews in the file, scored POSITIVE or NEGATIVE with prompt v1. Answer key: 4–5★ positive, 1–3★ negative.'
       [sec-verdict] 'Macro F1'
       [row-count] '100'
       [row-count] '100'
       [sec-method] 'Prompt sha256'
       [sec-method] 'runs/first100_v1/metrics.json'
       [sec-method] 'runs/first100_v1/predictions.jsonl'

TOTAL FAILS: 0 []
```

The remaining untagged digits are all non-metric text: the course code, "Reviews '23", "F1", "sha256", and file paths.

## verify_leak.py

`reviews/step3_numbers_auditor/verify_leak_output.txt`:

```
PASS runs/first100_v1/predictions.jsonl: 100 rows, prompt prompts/sentiment_v1.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
EXIT=0
```
