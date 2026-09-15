# PROGRESS.md — source of truth for where this job stands

After any context compaction: read this file, ISSUES.md, docs/assignment.md, and reviews/ in full, then continue from "Next action". Never redo a step whose gate is recorded as passed.

## Current step
Step 6 — Three-class balanced run (starting)

## Gates passed
- Step 0 — evidence: `runs/rating_distribution.json`, `reviews/step0/hello_browser.png`, Step 0 entries in ISSUES.md. `gh auth` OK (account essboomer); `gh repo view mbax6418-assignment1` → not found. Commit 8a8f484.
- Step 1 (self-check) — spot check 10/10 (`reviews/step1_spotcheck.txt`, `.json`); parser/FAIL/API_ERROR self-test passes (`reviews/step1_selftest.txt`); `verify_leak.py` PASS (`reviews/step1_verify_leak.txt`). `prompts/sentiment_v1.txt` is IMMUTABLE. Commit 8176267.
- Step 2 (Grader + Numbers Auditor, round 1) — `runs/first100_v1/` (accuracy 97.0% vs majority baseline 93.0%; NEGATIVE recall 6/7); `reviews/step2_analysis.md`; `reviews/step2_grader.md` (1 MAJOR, 4 MINOR — all fixed); `reviews/step2_numbers_auditor.md` (0 mismatches, 1 MINOR — fixed); `reviews/step2_verify_leak.txt` PASS. Commit c0b780c.
- Step 3 (Numbers Auditor, round 1) — `dashboard/template.html`, `dashboard/manifest.json`, `src/build_dashboard.py`, built `dashboard/index.html`; `reviews/step3_numbers_auditor.md` (0 mismatches; 2 MINOR — both fixed); gate screenshot `reviews/step3_dashboard_1440x900.png` (viewed). Commit b1b1229.
- Step 4 (self-check) — filters in `dashboard/template.html`; `src/verify_dashboard.py` PASS 294 checks (`reviews/step4_verify_dashboard.txt`); mutation test 3/3 caught (`reviews/step4_verify_mutation.txt`). Commit 1e29dea.
- Step 5 (Grader + Numbers Auditor, 2 rounds) — `prompts/sentiment_v2.txt` (IMMUTABLE), `runs/first100_v2/` (predictions with both emotions, metrics.json, emotion_metrics.json), `runs/nrc_lexicon_meta.json`, `src/get_nrc.py`, `src/nrc_emotion.py`, dashboard emotion section + emotion columns/filter; `reviews/step5_analysis.md` (revised twice); round 1 `reviews/step5_grader.md` (1 MAJOR, 8 MINOR) + `reviews/step5_numbers_auditor.md` (1 BLOCKER); round 2 `reviews/step5_grader_r2.md` (6 MINOR) + `reviews/step5_numbers_auditor_r2.md` (2 BLOCKER, 3 MINOR) — ALL fixed, none rejected (ISSUES.md Step 5 round logs). Final `verify_dashboard.py` PASS 1,344 checks incl. 400px no-sideways-scroll (`reviews/step5_verify_dashboard.txt`); `verify_leak.py` PASS (`reviews/step5_verify_leak.txt`); screenshots viewed `reviews/step5_emotion_1440.png`, `reviews/step5_emotion_400.png`.

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
- Kept metadata fields in predictions: `verified_purchase`, `helpful_vote`, `timestamp`, `asin`, `parent_asin`, `images_count`. None reach the model.
- batch_100 = review_ids 0–99 (0 rows excluded). Contains duplicate groups "Good Product" ×7 (20–24, 27, 28) and "Good product" ×2 (25–26) = 7 repeats.
- Step 2 interpretation: errors 17 and 46 are instruction-following failures (prompt rules point POSITIVE), not rule gaps; 98 is a 3★ truth-definition artifact.
- Dashboard: HTML/CSS marks (not SVG); all colors in one `:root` block. Classes: POSITIVE `#2f5aa8`, NEUTRAL `#8f8a7e`, NEGATIVE `#c8502e`, UNPARSED `#6e56b8`. Right `#3e4a57`, wrong `#d9822b`. Emotion series `--llm #7a5195`, `--lex #b08a3e`. Validator evidence in ISSUES.md.
- Dashboard display rules (verify_dashboard.py mirrors): `pct` = (v×100).toFixed(1)+"%"; `count` = integer with en-US commas; `pp` = "+"/"−" + |v×100|.toFixed(1) + " pts"; `text` = String(v). Metric spans: `data-metric`, `data-raw`, `data-source` (`file#field`), `data-format`, `data-run`. Marks: `data-run`, `data-metric`, `data-value`, `data-label`; emotion marks use `data-metric="emotion.<field>"` (→ run's emotion_metrics.json). Live count `#shown-count[data-live-count]`; rows carry `data-review-id`, `data-correct`, `data-truth`, `data-prediction`, `data-emo`. Filters: `#f-result`, `#f-truth`, `#f-pred`, `#f-emo` (if emotions), `#f-search`, `#f-reset`.
- Run blurb built from `run_meta.json`; `manifest.json` holds title + tab labels (build checks label digits vs `n_rows`, class wording vs `label_scheme`).
- Review text display decodes `<br />` and HTML entities for reading only; stored data unchanged.
- `dashboard/screenshots/drafts/` is scratch — do not commit; delete before Step 7 capture.
- Step 5: NRC = official EmoLex v0.92 (lexicon sha256 02c66154…535a, 14,154 words, 4,454 with ≥1 of 8 emotions), never committed (license: non-commercial research/education, no redistribution). `nrc_emotion.py` uses the model's star-phrase blanking, decodes HTML, keeps `nrc_hits`, `nrc_emotion_tiebreak`, `nrc_negated_hits`; `emotion_agree` = exact match (TIE/NONE never agree). `emotion_metrics.json` carries a constant-answer baseline (LLM's most common emotion), tie-break baselines, unique-row and negation stats. `classify.py` deletes a stale `emotion_metrics.json`; `build_dashboard.py` refuses emotion metrics that don't match rows.
- Step 5 numbers (first100_v2): sentiment identical to v1 (0 flips; errors 17, 46, 98). Emotion agreement 20/100, 20/85 excl NONE, 20/38 excl NONE+TIE; constant "joy" 22/100, 22/85, 22/38 (LLM −2.0 / −5.3 pts); LLM non-joy rows agree 1/20; TIE 47 (LLM emotion in 45, "joy" in 45; 43 → anticipation under tie-break), NONE 15; tie-break agreement 23/100 (constant joy 23/100, constant anticipation 57/100); unique rows 93 (agree 20, TIE 40, NONE 15); negation 15 hits in 11 rows (5 rhetorical, 6 real, 4 not governing).
- Step 5 interpretation: emotion agreement is no better than always answering joy; "ties explain the low agreement" is WITHDRAWN. Every later emotion comparison (Step 6, README) must sit beside the constant baseline.
- `verify_dashboard.py` also asserts no sideways page scroll at a 400px viewport for every run.

## API calls used
199 after Step 5 (3 Step 0 probes + 10 spot check + 3 v1 preview + 90 first100_v1 + 3 v2 preview + 90 first100_v2); live total in `cache/api_calls_total.json`. Cap 1500.

## Open reviewer findings
(none)

## Next action
Commit Step 5. Then Step 6:
1. `prompts/sentiment_v3.txt` = v2 with three classes (POSITIVE / NEUTRAL / NEGATIVE) and an explicit NEUTRAL definition that does not reference stars; no digits, no forbidden words. Truth: 4–5 POSITIVE, 3 NEUTRAL, 1–2 NEGATIVE (`truth_three` in load_data.py; spec already in classify.PROMPT_SPECS).
2. `runs/balanced150_v3/`: `classify.py --prompt prompts/sentiment_v3.txt --selection balanced_150 --run balanced150_v3` (writes `sample_ids.json` first; preview 3 before full run). Then `runs/first100_v3/` on batch_100 (addition: isolates sampling change). ~250 new API calls.
3. `score.py` both; `nrc_emotion.py` both; `verify_leak.py`; add both runs to `dashboard/manifest.json` ("Balanced 150 · three classes", "First 100 · three classes"); build; `verify_dashboard.py`.
4. Comparison fields for README quoting (e.g. `runs/comparisons.json` or named fields): accuracy/baseline deltas first100_v3 vs balanced150_v3; NEUTRAL row cells both directions (NEUTRAL→NEGATIVE, NEUTRAL→POSITIVE, NEGATIVE→NEUTRAL).
5. `reviews/step6_analysis.md` with exact cell counts; then Grader + Numbers Auditor + Skeptic in parallel.
