# PROGRESS.md — source of truth for where this job stands

After any context compaction: read this file, ISSUES.md, docs/assignment.md, and reviews/ in full, then continue from "Next action". Never redo a step whose gate is recorded as passed.

## Current step
Step 7 — Descriptive and prediction visualizations (starting; commit Step 6 first)

## Step 6 status (gate passed; kept for reference)
- Done: `prompts/sentiment_v3.txt` (IMMUTABLE, used by both v3 runs); `runs/balanced150_v3/` (sample_ids.json, predictions with emotions, metrics.json, emotion_metrics.json); `runs/first100_v3/` (same); `src/compare_runs.py` → `runs/comparisons.json` (named cross-run fields + Wilson 95% intervals, an addition); manifest has all 4 runs; `verify_leak.py` PASS all 4 (`reviews/step6_verify_leak.txt`); `verify_dashboard.py` PASS (count: see last line of `reviews/step6_verify_dashboard.txt`; 3,766 at the round-1 fix build); sample check (`reviews/step6_sample_check.txt`: redraw == saved ids); explorations `reviews/step6_explore_balanced.txt`, `reviews/step6_explore_first100.txt`; ISSUES Step 6 entries.
- Numbers: balanced150_v3 73.3% (110/150), baseline 33.3%, NEUTRAL row 17 NEUTRAL / 25 NEGATIVE / 8 POSITIVE, NEGATIVE→NEUTRAL 4, POSITIVE→NEUTRAL 2, NEGATIVE→POSITIVE 1, predicted NEGATIVE 70; recall POS 48/50, NEU 17/50, NEG 45/50. first100_v3 95.0% (95/100), baseline 93.0%, balanced acc 65.6%, truth 93/2/5, errors 46, 83 (POS→NEU), 17 (POS→NEG), 98 (NEU→POS), 91 (NEU→NEG). Balanced sample star mix 1★43 2★7 3★50 4★0 5★50; 26 star titles blanked; 1 duplicate pair; customers' own star mentions reached the model in 121389 (text, "5 stars") and 140676 (title, "zero stars"). Emotions balanced: agreement 16/150; LLM top emotion anger (62) → constant anger 4/150; BEST constant (new field `best_constant_baseline*`) anticipation 22/150 (14.7%), 22/59 (37.3%) → LLM −4.0 / −10.2 pts. first100_v3 emotions: 20/100 vs constant joy 22/100 (best constant also joy). Wilson 95% (comparisons.json): plain accuracy 65.7–79.8%, NEUTRAL→NEGATIVE share 36.6–63.4%, NEUTRAL recall 22.4–47.8%, NEUTRAL→POSITIVE 8.3–28.5%.
- Dashboard: headline/tile say "any one class" when truth classes tie (balanced run); emotion context adds the best constant when it differs.
- Logs `reviews/step6_nrc_balanced.txt` / `step6_nrc_first100.txt` were replaced by `reviews/step6_nrc_<run>.txt` after the best-constant re-run.
- `reviews/step6_analysis.md` written, then revised after round 1.
- Round 1 done: `reviews/step6_grader.md` (2 MAJOR, 3 MINOR), `reviews/step6_numbers_auditor.md` (0 mismatches / 11,865 checks, 3 MINOR), `reviews/step6_skeptic.md` (2 MAJOR, 5 MINOR) — all fixed, none rejected (ISSUES.md Step 6 round-1 log). Evidence: `reviews/step6_round1_checks.txt`, `reviews/step6_round1_claim_checks.txt`.
- Step 6 decisions made in round 1 (never re-decide):
  - Balanced-sample precision/accuracy are mix-dependent; `comparisons.json` carries a population re-weighting (weights 88.5/2.1/9.3%; re-weighted accuracy ~94.1%, NEUTRAL precision ~14.5%). Quote recall and balanced accuracy as what the balanced run measures well.
  - (Round 2) Q1 sampling comparison uses PER-CLASS RECALLS: balanced recalls applied to batch_100's 93/2/5 counts predict 94.5% vs observed 95.0% (`comparisons.json: first100_v3_accuracy_expected_from_balanced150_v3_recalls`). Do NOT quote the balanced-accuracy change (65.6% → 73.3%): it rests on 2 NEUTRAL reviews (82.3% with one more right). Do NOT compare margins over different baselines.
  - (Round 2) 3★ verdict wording: "half (25 of 50) go to NEGATIVE, the largest destination; 95% interval 36.6–63.4%, so not shown to be a majority". Never "mostly collapse into NEGATIVE".
  - (Round 2) All 25 3★→NEGATIVE re-graded against v3 rules: 17 follow the prompt's NEGATIVE rules; up to 8 are judgment-call candidates (4880, 22082, 32735, 51332, 53136, 60681, 111780, 147336). Plus 99795 (NEG→NEU) probable sarcasm-rule breach → ~9 of 40 balanced errors are candidate prompt-following misses. "At most 3" and "at least 7" are both WITHDRAWN.
  - (Round 2) Framing: the 17 show the model obeyed the prompt's inherited policy (card problem / lost money / won't buy again → NEGATIVE) while reviewers rated 3★. It is policy vs answer key, not "the key is wrong"; prompt variant untested.
  - (Round 2) Empty sent title = always a blanked star phrase (no originally empty titles in file) → weak rating-derived signal (Fisher p 0.041 on NEUTRAL row); disclosed. 103 star-count title variants in file escape exact blanking; none in the saved runs; verify_leak.py now fails on them.
  - Temperature 0 is not deterministic on this endpoint (review 4880 retry gave a different reply); reproducibility rests on committed predictions + cache.
  - Two star mentions reached the model in customers' own words (121389 text, 140676 title).
  - Each run's metrics.json has `sample_rating_counts`; dashboard shows the star mix and, for balanced runs, re-weighted precision from `runs/comparisons.json` (embedded as DATA.comparisons).
- Round 2 done and fixed (see Gates passed). Gate passed; commit pending at the time of writing.

## Gates passed
- Step 0 — evidence: `runs/rating_distribution.json`, `reviews/step0/hello_browser.png`, Step 0 entries in ISSUES.md. `gh auth` OK (account essboomer); `gh repo view mbax6418-assignment1` → not found. Commit 8a8f484.
- Step 1 (self-check) — spot check 10/10 (`reviews/step1_spotcheck.txt`, `.json`); parser/FAIL/API_ERROR self-test passes (`reviews/step1_selftest.txt`); `verify_leak.py` PASS (`reviews/step1_verify_leak.txt`). `prompts/sentiment_v1.txt` is IMMUTABLE. Commit 8176267.
- Step 2 (Grader + Numbers Auditor, round 1) — `runs/first100_v1/` (accuracy 97.0% vs majority baseline 93.0%; NEGATIVE recall 6/7); `reviews/step2_analysis.md`; `reviews/step2_grader.md` (1 MAJOR, 4 MINOR — all fixed); `reviews/step2_numbers_auditor.md` (0 mismatches, 1 MINOR — fixed); `reviews/step2_verify_leak.txt` PASS. Commit c0b780c.
- Step 3 (Numbers Auditor, round 1) — `dashboard/template.html`, `dashboard/manifest.json`, `src/build_dashboard.py`, built `dashboard/index.html`; `reviews/step3_numbers_auditor.md` (0 mismatches; 2 MINOR — both fixed); gate screenshot `reviews/step3_dashboard_1440x900.png` (viewed). Commit b1b1229.
- Step 4 (self-check) — filters in `dashboard/template.html`; `src/verify_dashboard.py` PASS 294 checks (`reviews/step4_verify_dashboard.txt`); mutation test 3/3 caught (`reviews/step4_verify_mutation.txt`). Commit 1e29dea.
- Step 5 (Grader + Numbers Auditor, 2 rounds) — `prompts/sentiment_v2.txt` (IMMUTABLE), `runs/first100_v2/` (predictions with both emotions, metrics.json, emotion_metrics.json), `runs/nrc_lexicon_meta.json`, `src/get_nrc.py`, `src/nrc_emotion.py`, dashboard emotion section + emotion columns/filter; `reviews/step5_analysis.md` (revised twice); round 1 `reviews/step5_grader.md` (1 MAJOR, 8 MINOR) + `reviews/step5_numbers_auditor.md` (1 BLOCKER); round 2 `reviews/step5_grader_r2.md` (6 MINOR) + `reviews/step5_numbers_auditor_r2.md` (2 BLOCKER, 3 MINOR) — ALL fixed, none rejected (ISSUES.md Step 5 round logs). Final `verify_dashboard.py` PASS 1,344 checks incl. 400px no-sideways-scroll (`reviews/step5_verify_dashboard.txt`); `verify_leak.py` PASS (`reviews/step5_verify_leak.txt`); screenshots viewed `reviews/step5_emotion_1440.png`, `reviews/step5_emotion_400.png`. Commit f842eaa.
- Step 6 (Grader + Numbers Auditor + Skeptic, 2 rounds) — `prompts/sentiment_v3.txt` (IMMUTABLE), `runs/balanced150_v3/` (sample_ids.json, predictions, metrics, emotion_metrics), `runs/first100_v3/`, `runs/comparisons.json` (`src/compare_runs.py`), `sample_rating_counts` in every metrics.json; `reviews/step6_analysis.md` (revised twice). Round 1: `reviews/step6_grader.md` (2 MAJOR, 3 MINOR), `reviews/step6_numbers_auditor.md` (0 mismatches, 3 MINOR), `reviews/step6_skeptic.md` (2 MAJOR, 5 MINOR). Round 2: `reviews/step6_grader_r2.md` (5 MINOR), `reviews/step6_numbers_auditor_r2.md` (0 value mismatches / 15,151 checks, 2 MINOR), `reviews/step6_skeptic_r2.md` (4 MAJOR, 7 MINOR). ALL fixed, none rejected (ISSUES.md Step 6 round logs). Final: `verify_dashboard.py` PASS 3,770 checks (`reviews/step6_verify_dashboard.txt`), `verify_leak.py` PASS all 4 runs incl. star-variant check (`reviews/step6_verify_leak.txt`), read-back `reviews/step6_final_readback.txt`.

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
442 after Step 6 runs (199 + 3 balanced preview + 147 balanced150_v3 + 93 first100_v3); live total in `cache/api_calls_total.json`. Cap 1500.

## Open reviewer findings
(none)

## Next action
Commit Step 6 (explicit paths; scan staged files for data/cache/.env/lexicon). Then Step 7:
1. Reproducibility gap: `runs/rating_distribution.json` was produced by an inline Step 0 script; add `src/rating_distribution.py` that regenerates it (adding fraction `rating_share` fields, keeping existing fields identical) so the full-file chart is reproducible from committed code.
2. Dashboard descriptive layer (template + build): star-rating distribution of the full file (marks `data-run="__file__"`, source `runs/rating_distribution.json`) beside each run's sample (`sample_rating_counts`); answer-key vs predicted counts per class as grouped bars; per-class accuracy (exists); confusion heatmap with counts (exists); emotion cross-tab (exists). Failures visible without drilling in.
3. Layout-bug guard: every mark with data-value > 0 renders ≥ 2px in both dimensions (already checked) AND shows its true value as a visible label next to it — extend `verify_dashboard.py` to assert the label.
4. Build; `verify_dashboard.py`; view screenshots; then all four reviewers (Grader, Numbers Auditor, Skeptic, Product Critic) in parallel, ≤ 2 rounds.
5. After the gate: delete `dashboard/screenshots/drafts/`, capture 1440×900 screenshots of every section + one filtered-table state with live count, lowercase names, into `dashboard/screenshots/`; recapture if the dashboard changes.

Previous (done) — Step 6 round-2 fixes (final allowed round): evidence `reviews/step6_round2_checks.txt`; template fixes (literal "null" on non-balanced tabs, equal-mix verdict line, re-weighted accuracy note); `verify_dashboard.py` null check; `verify_leak.py` star-variant check; rebuild + verify + leak audit; rewrite `reviews/step6_analysis.md` (re-grade all 25 3★→NEGATIVE against v3 rules; "half" not "mostly"; prompt policy vs answer key, not "the key is wrong"; Q1 via per-class recalls, not the fragile +7.7 balanced-accuracy change); ISSUES round-2 log + new entries; PROGRESS decisions; then record Step 6 gate and commit.

Old Step 6 plan (completed; kept for reference):
1. `prompts/sentiment_v3.txt` = v2 with three classes (POSITIVE / NEUTRAL / NEGATIVE) and an explicit NEUTRAL definition that does not reference stars; no digits, no forbidden words. Truth: 4–5 POSITIVE, 3 NEUTRAL, 1–2 NEGATIVE (`truth_three` in load_data.py; spec already in classify.PROMPT_SPECS).
2. `runs/balanced150_v3/`: `classify.py --prompt prompts/sentiment_v3.txt --selection balanced_150 --run balanced150_v3` (writes `sample_ids.json` first; preview 3 before full run). Then `runs/first100_v3/` on batch_100 (addition: isolates sampling change). ~250 new API calls.
3. `score.py` both; `nrc_emotion.py` both; `verify_leak.py`; add both runs to `dashboard/manifest.json` ("Balanced 150 · three classes", "First 100 · three classes"); build; `verify_dashboard.py`.
4. Comparison fields for README quoting (e.g. `runs/comparisons.json` or named fields): accuracy/baseline deltas first100_v3 vs balanced150_v3; NEUTRAL row cells both directions (NEUTRAL→NEGATIVE, NEUTRAL→POSITIVE, NEGATIVE→NEUTRAL).
5. `reviews/step6_analysis.md` with exact cell counts; then Grader + Numbers Auditor + Skeptic in parallel.
