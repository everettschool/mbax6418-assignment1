# PROGRESS.md — source of truth for where this job stands

After any context compaction: read this file, ISSUES.md, docs/assignment.md, and reviews/ in full, then continue from "Next action". Never redo a step whose gate is recorded as passed.

## Current step
Step 4 — Interactive filtering (starting)

## Gates passed
- Step 0 — evidence: `runs/rating_distribution.json`, `reviews/step0/hello_browser.png`, Step 0 entries in ISSUES.md. `gh auth` OK (account essboomer); `gh repo view mbax6418-assignment1` → not found. Commit 8a8f484.
- Step 1 (self-check) — spot check 10/10 (`reviews/step1_spotcheck.txt`, `.json`); parser/FAIL/API_ERROR self-test passes (`reviews/step1_selftest.txt`); `verify_leak.py` PASS (`reviews/step1_verify_leak.txt`). `prompts/sentiment_v1.txt` is now IMMUTABLE. Commit 8176267.
- Step 2 (Grader + Numbers Auditor, round 1) — `runs/first100_v1/` (accuracy 97.0% vs majority baseline 93.0%; NEGATIVE recall 6/7); `reviews/step2_analysis.md`; `reviews/step2_grader.md` (1 MAJOR, 4 MINOR — all fixed); `reviews/step2_numbers_auditor.md` (0 mismatches, 1 MINOR — fixed); `reviews/step2_verify_leak.txt` PASS. Commit c0b780c.
- Step 3 (Numbers Auditor, round 1) — `dashboard/template.html`, `dashboard/manifest.json`, `src/build_dashboard.py`, built `dashboard/index.html` (62,287 bytes, 0 console errors, 0 network requests); `reviews/step3_numbers_auditor.md` (0 mismatches over 62 fields / 56 numbers / 14 marks; 2 MINOR — both fixed); gate screenshot `reviews/step3_dashboard_1440x900.png` (viewed).

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
- Dashboard: HTML/CSS marks (not SVG); all colors in one `:root` block. Classes: POSITIVE `#2f5aa8`, NEUTRAL `#8f8a7e`, NEGATIVE `#c8502e`, UNPARSED `#6e56b8`. Right `#3e4a57` (slate), wrong `#d9822b` (amber) — validator evidence in ISSUES.md.
- Dashboard display rules (verify_dashboard.py must mirror): `pct` = (v×100).toFixed(1)+"%"; `count` = integer with en-US thousands commas; `pp` = sign ("+" or U+2212 "−") + |v×100|.toFixed(1) + " pts"; `text` = String(v). Metric spans: `data-metric`, `data-raw` (JSON), `data-source` (`file#field`), `data-format`, `data-run`. Marks: `data-run`, `data-metric`, `data-value`, `data-label`. Live row count: `#shown-count[data-live-count]`; table rows carry `data-review-id`, `data-correct`, `data-truth`, `data-prediction`.
- Run blurb is built from `run_meta.json`; `manifest.json` holds only title + tab labels, and the build checks label digits vs `n_rows` and class wording vs `label_scheme`.
- Review text display decodes `<br />` and HTML entities for reading only; stored data unchanged.
- `dashboard/screenshots/drafts/` is scratch from Step 3 iterations — do not commit; delete before the Step 7 screenshot capture.

## API calls used
106 after Step 3 (3 Step 0 probes + 10 spot check + 3 preview + 90 first100_v1); live total in `cache/api_calls_total.json`. Cap 1500.

## Open reviewer findings
(none — Step 3 round-1 findings both fixed)

## Next action
Commit Step 3. Then Step 4: add filters (correct/mismatched, truth class, predicted class, free-text search; combinable; live count) to `dashboard/template.html`; write `src/verify_dashboard.py` (browser asserts: each filter + combinations vs counts computed from predictions.jsonl; every data-raw equals its data-source file value and displayed text matches display rule); save output to `reviews/step4_verify_dashboard.txt`.
