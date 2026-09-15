# Step 6 Grader review — Three-class scoring with balanced sampling

What I checked and found correct (no finding):
- Truth labels (4–5 POSITIVE, 3 NEUTRAL, 1–2 NEGATIVE) match the data file for all 150 rows.
- A fresh draw with seed 42 gives exactly the saved ids, 50 per class.
- `score.py`, rerun on scratch copies, rebuilds both `metrics.json` files byte for byte.
- `nrc_emotion.py`, rerun on copies, rebuilds both `emotion_metrics.json` files and both `predictions.jsonl` files byte for byte.
- The Wilson intervals and the named fields in `comparisons.json` recompute correctly.
- `verify_leak.py` passes and matches its saved log.
- The built `index.html` equals template plus run files.
- `verify_dashboard.py` passes: 3676 checks, 0 failures.
- The balanced tab shows the three-class answer key, a 3×3 matrix plus an UNPARSED column, and the seed and sampling rule.
- The prompt v3 hash matches both v3 runs.
- Both "Ask yourself" questions are answered with counts from saved files.
- ISSUES.md has 16 Step 6 entries.
Scratch output is in `reviews/step6_grader_scratch/`.

MAJOR — reviews/step6_analysis.md, "Seven of the 25 also contain explicit praise…" and "Does the hunch hold?" ("At least 7 of the 25 are mixed reviews the model tipped to NEGATIVE against its instructions") — At least 2 of the 7 were labelled NEGATIVE as prompt v3's own rules require, so "against its instructions" is wrong for them. The "still a real weakness" conclusion rests on this count. — Evidence (`.venv/bin/python` dump of `runs/balanced150_v3/predictions.jsonl`):
- **60608:** the text says "It's a brilliant idea but I probably won't be using it again". v3 line 13 says: "if they … say they would not buy again, pick NEGATIVE".
- **88787:** the praise is only in the title ("Still a happy recipient of this gift."), and the text is "took almost five days … Very disappointed." v3 line 11 says: "Title and text disagree: the TEXT decides".
- **121389:** ends "Bad bad bad", so the complaint plausibly outweighs the praise.

Suggested fix: re-read each of the 7 against every v3 rule, not just the equal-weight rule. Restate the count (at most 5, possibly fewer) and soften "against its instructions" to "arguably". Update the "Does the hunch hold?" bullet to match.

MAJOR — ISSUES.md line 92 ("…disclosed wherever balanced POSITIVE numbers are quoted") vs dashboard/index.html, balanced150_v3 tab — The balanced POSITIVE sample has no 4★ reviews. ISSUES.md says this is disclosed wherever balanced POSITIVE numbers appear, but the dashboard never says it. The page shows POSITIVE recall "48 of 50 · 96.0%" and precision 84.2% for this sample. — Evidence:
- The rendered text of the balanced tab (Playwright `inner_text('body')`, saved to `reviews/step6_grader_scratch/balanced_text.txt`) has no match for `4★`, `no 4` or "star mix".
- `grep -n "4★" dashboard/template.html` finds only the answer-key definition strings (lines 345–346).

A reader of the product would assume 4★ reviews were tested. Suggested fix: add a run-bound note to the balanced tab, e.g. a star mix of the sample from `sample_ids.json`/predictions (1★ 43 · 2★ 7 · 3★ 50 · 4★ 0 · 5★ 50). Otherwise, correct the ISSUES.md wording to say it is disclosed in the analysis only.

MINOR — reviews/step6_analysis.md Caveats ("One review's own text mentions stars (121389)"), ISSUES.md line 97, PROGRESS.md — The review text of 2 balanced reviews mentioned stars when it reached the model, not 1. A third review uses a flagged word ("Helpful"). The saved leak log reports 3, which contradicts "one". — Evidence:
- `verify_leak.py` → `PASS runs/balanced150_v3/predictions.jsonl: … 3 reviews use a forbidden word in their own sent title/text`.
- Listing those rows gives:
  - `121389 3.0 NEUTRAL→NEGATIVE ['stars'] "Cannot give 5 stars…"`
  - `140676 1.0 NEGATIVE→NEGATIVE ['stars'] "I would give this 'zero stars'"`
  - `138151 3.0 NEUTRAL→NEUTRAL ['Helpful'] "Helpful Review"`

Suggested fix: name 140676 as well (a correct prediction, so the conclusions are unaffected), and say that the 3 flagged rows match the leak log.

MINOR — ISSUES.md line 93 ("Sample quirks … 147 API calls with 4 cache hits") — The call count is not fully explained, and a model output failure goes unlogged. On review 4880 the model first answered with an emotion outside the allowed eight. That reply failed to parse and needed a retry, which accounts for the 147th call (146 uncached rows + 1 retry). ISSUES.md does not record this, although the prompt says "never invent another word". — Evidence:
- `runs/balanced150_v3/run_meta.json` → `rows_needing_retry: 1`.
- The predictions row for 4880 → `raw_responses: ['LABEL=NEGATIVE;EMOTION=disappointment', 'LABEL=NEGATIVE;EMOTION=sadness']`.
- `grep -n "4880\|disappointment\|retry" ISSUES.md` → no Step 6 hit.

Suggested fix: add an ISSUES entry for the out-of-vocabulary emotion and its retry, and note it in the call-count arithmetic.

MINOR — PROGRESS.md, Step 6 status ("`verify_dashboard.py` PASS 3,661 checks") — The number is stale. The saved log and a fresh run both report 3676. — Evidence: `tail reviews/step6_verify_dashboard.txt` → `3676 checks, 0 failures`, and a rerun to `reviews/step6_grader_scratch/verify_dashboard_now.txt` → `3676 checks, 0 failures`. Suggested fix: update to 3,676. Per the project's own rule, cite the log rather than retyping the number.
