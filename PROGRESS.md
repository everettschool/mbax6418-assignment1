# PROGRESS.md — source of truth for where this job stands

After any context compaction: read this file, ISSUES.md, docs/assignment.md, and reviews/ in full, then continue from "Next action". Never redo a step whose gate is recorded as passed.

## Current step
Step 2 — Score batch_100 against the rating, binary (in progress)

## Gates passed
- Step 0 — evidence: `runs/rating_distribution.json`, `reviews/step0/hello_browser.png`, Step 0 entries in ISSUES.md. `gh auth` OK (account essboomer); `gh repo view mbax6418-assignment1` → not found.
- Step 1 (self-check) — spot check 10/10 (`reviews/step1_spotcheck.txt`, `.json`); parser/FAIL/API_ERROR self-test passes (`reviews/step1_selftest.txt`); `verify_leak.py` PASS (`reviews/step1_verify_leak.txt`). `prompts/sentiment_v1.txt` is now IMMUTABLE.

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

## API calls used
13 after Step 1 (3 Step 0 probes + 10 spot check); live total in `cache/api_calls_total.json`

## Open reviewer findings
(none)

## Next action
Commit Step 1. Step 2: preview 3 raw responses, run `classify.py` on batch_100 → `runs/first100_v1/`, `score.py`, `verify_leak.py`, then Grader + Numbers Auditor.
