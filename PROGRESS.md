# PROGRESS.md — source of truth for where this job stands

After any context compaction: read this file, ISSUES.md, docs/assignment.md, and reviews/ in full, then continue from "Next action". Never redo a step whose gate is recorded as passed.

## Current step
Step 3 — Dashboard (starting)

## Gates passed
- Step 0 — evidence: `runs/rating_distribution.json`, `reviews/step0/hello_browser.png`, Step 0 entries in ISSUES.md. `gh auth` OK (account essboomer); `gh repo view mbax6418-assignment1` → not found. Commit 8a8f484.
- Step 1 (self-check) — spot check 10/10 (`reviews/step1_spotcheck.txt`, `.json`); parser/FAIL/API_ERROR self-test passes (`reviews/step1_selftest.txt`); `verify_leak.py` PASS (`reviews/step1_verify_leak.txt`). `prompts/sentiment_v1.txt` is now IMMUTABLE. Commit 8176267.
- Step 2 (Grader + Numbers Auditor, round 1) — `runs/first100_v1/` (accuracy 97.0% vs majority baseline 93.0%; NEGATIVE recall 6/7); `reviews/step2_analysis.md`; `reviews/step2_grader.md` (1 MAJOR, 4 MINOR — all fixed); `reviews/step2_numbers_auditor.md` (0 mismatches, 1 MINOR — fixed); `reviews/step2_verify_leak.txt` PASS.

## Fixed facts (never re-decide)
- Dataset: `data/Gift_Cards.jsonl.gz`, sha256 `e03a258ebd7b1e2591b09862aab65d3dcde9c300744d800aa1fbaf374b7c2340`, 152,410 rows, 49 rows fail inclusion rule.
- Rating distribution saved: `runs/rating_distribution.json`.
- Model: `cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit` (only model offered by `/v1/models`). Endpoint label in metadata: `course-endpoint`.
- `temperature=0` accepted by the endpoint.
- Thinking disabled on every call: `extra_body={"chat_template_kwargs": {"enable_thinking": false}}` (otherwise content is null).
- API_ERROR rows also get `prediction: UNPARSED`; `parse_status` distinguishes FAIL from API_ERROR.
- Prompt files contain no digits, so verify_leak can check row field values against the template literally.
- Session API call counter: `cache/api_calls_total.json` (starts at 3 for the Step 0 probes).
- `build_messages` blanks any title or text that is only "<One–Five> Star(s)" (Amazon auto-fill = the rating). Stored title/text stay original.
- Metrics store rates as fractions in [0,1]; display = ×100, one decimal. Confusion matrix rows = truth, columns = predicted, UNPARSED is its own column.
- RANDOM_SEED = 42. Repo name `mbax6418-assignment1`, public.
- Python: `.venv/` (Homebrew Python 3.14.2). Browser: Playwright Chromium headless shell 153.0.8010.12.
- Kept metadata fields in predictions: `verified_purchase`, `helpful_vote`, `timestamp`, `asin`, `parent_asin`, `images_count` (see ISSUES.md). None reach the model.
- batch_100 = review_ids 0–99 (0 rows excluded). Contains 7 duplicate "Good Product"/"Good product" repeats.
- Step 2 interpretation: errors 17 and 46 are instruction-following failures (prompt rules point POSITIVE), not rule gaps; 98 is a 3★ truth-definition artifact.

## API calls used
106 after Step 2 (3 Step 0 probes + 10 spot check + 3 preview + 90 first100_v1); live total in `cache/api_calls_total.json`. Cap 1500.

## Open reviewer findings
(none — Step 2 round-1 findings all fixed)

## Next action
Commit Step 2. Then Step 3: write `dashboard/template.html` + `src/build_dashboard.py` (manifest of runs, inline SVG, data-metric/data-raw/data-source attrs), build `dashboard/index.html`, screenshot at 1440×900, Numbers Auditor.
