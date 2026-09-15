# Step 6 Grader review, round 2 — Three-class scoring with balanced sampling

What I checked and found correct (no finding). Scratch output is in `reviews/step6_grader_r2_scratch/`.
- **Requirements met as written.**
  - Truth is 4–5★ POSITIVE, 3★ NEUTRAL, 1–2★ NEGATIVE (`truth_three`).
  - `metrics.json` holds a 3×3 matrix plus an UNPARSED column, with per-class P/R/F1.
  - Prompt v3 asks for three classes and defines NEUTRAL without mentioning stars. It has 0 digits and no word from the forbidden list, and its sha256 (`eee1dc0e…`) equals `run_meta.prompt_sha256`.
  - The dashboard shows the three-class answer key on both v3 tabs.
  - The balanced draw is 50 per class, seed 42, with ids saved in `sample_ids.json`.
- **Rebuild from copies in `root/`.** `score.py` (4 runs), `nrc_emotion.py` (3 runs) and `compare_runs.py` all ran. Every file under `runs/` is byte-identical to the rebuild (`rebuild_diff.txt`: 19 SAME, 0 DIFF). `build_dashboard.py` run on a copy of `dashboard/` gives an `index.html` identical to the committed one (`INDEX_SAME`).
- **Checks re-run.**
  - `verify_leak.py` passes, and its output is identical to `reviews/step6_verify_leak.txt`.
  - The last lines of `reviews/step6_verify_dashboard.txt` read `3766 checks, 0 failures`; that log is newer than `index.html` and `template.html`.
- **Rendered page (Playwright, runs chosen by clicking tabs; `text_<run>.txt`).**
  - The balanced tab shows "Stars in this sample: 1★ 43 · 2★ 7 · 3★ 50 · 4★ 0 · 5★ 50."
  - It also shows the re-weighted precision note "Positive 99.4% · Neutral 14.5% · Negative 88.6%", which matches `comparisons.json`.
- **Round-1 fixes confirmed.**
  - The "at least 7" claim is withdrawn.
  - Two star mentions (121389, 140676) and the "Helpful" hit are disclosed.
  - The 4880 retry and non-determinism are logged in ISSUES.md and in the analysis.
  - The Wilson interval is relabelled "plain accuracy".
  - The "older reviews" explanation is replaced by pool shares.
  - Trust is split by class.
  - The population re-weighting recomputes by hand: NEUTRAL precision 0.0073/0.0501 = 14.5%; share from POSITIVE 70.6%.
- **Other checks.**
  - The 147-call arithmetic holds: 150 − 4 cache hits + 1 retry.
  - "18 non-joy rows agree 0 times" (first100_v3) recomputes to 18 / 0.
- **Both "Ask yourself" questions** are answered with counts from saved files:
  - 3★ → NEGATIVE 25, NEUTRAL 17, POSITIVE 8.
  - What the lopsided run hid: 2 NEUTRAL rows versus 50.
- **ISSUES.md** has Step 6 entries, including a round-1 log whose counts match the three round-1 files (Grader 2 MAJOR + 3 MINOR; Auditor 3 MINOR; Skeptic 2 MAJOR + 5 MINOR).

MINOR — PROGRESS.md line 10 ("Numbers:" bullet of the Step 6 status) — Two round-1 errors that were fixed in the analysis and ISSUES.md are still in PROGRESS.md. By its own header, this file is the source of truth after context compaction and feeds the README. — Evidence: `grep -n "balanced accuracy 65.7\|121389 text" PROGRESS.md` → line 10 contains:
- "Wilson 95% (comparisons.json): balanced accuracy 65.7–79.8%". The analysis now labels `balanced150_v3_accuracy_wilson95` as "plain accuracy of the run", and the auditor's round-1 finding 3 says the interval is for plain accuracy.
- "review 121389 text says "5 stars"". This is the single-row version. ISSUES.md line 97 and PROGRESS.md line 20 both say two rows (121389 text, 140676 title).

Suggested fix: change the line to "plain accuracy 65.7–79.8%" and "star mentions reached the model in 121389 (text) and 140676 (title)".

MINOR — PROGRESS.md lines 64–70 ("## Next action") — The Next action section is stale. It still says "Commit Step 5. Then Step 6: 1. `prompts/sentiment_v3.txt` = …". The status bullet says Step 6 is at "Remaining: Grader + Numbers Auditor + Skeptic round 2". An agent resuming from "Next action", as line 3 instructs, would be sent back to redo Step 6, against line 3's own rule never to redo a step whose gate has passed. — Evidence: `grep -n "Next action\|Commit Step 5" PROGRESS.md` → `64:## Next action`, `65:Commit Step 5. Then Step 6:`. `git log --oneline` → `f842eaa Step 5: gate passed`, so Step 5 is already committed. — Suggested fix: replace the section with the current next action: round 2 fixes, Step 6 gate, commit.

MINOR — reviews/step6_analysis.md, "Which of these are model failures by the prompt's own rules?" ("4 follow the prompt's NEGATIVE rules: … 53136 … close to 'lost money → NEGATIVE'") and "So **at most 3 of the 25**"; the same count appears in ISSUES.md (round-1 log) and PROGRESS.md ("at most 3 are candidate instruction-following failures") — 53136 does not clearly meet any v3 NEGATIVE rule. The analysis itself only says "close to". The reviewer did not lose money or fail to use the card; a promotional bonus did not arrive. The text also ends with explicit praise, so the v3 mixed-review rule ("If the good and the bad carry about equal weight … pick NEUTRAL") fits it at least as well as 32735 or 147336. — Evidence (`reviews/step6_grader_r2_scratch/row_texts.txt`): `[53136] 3.0 NEUTRAL->NEGATIVE anger | TITLE: 'No credit this time' | TEXT: "I didnt get my 10$ for reloding 100$. 😣 other than that, I've used it before and get credit for 10$ ,its awesome."` The v3 rule text is: "if they could not use the card, lost money, or say they would not buy again, pick NEGATIVE". — Suggested fix: move 53136 to the judgment-call group and say "3 follow the prompt's NEGATIVE rules; up to 4 are candidate failures". Alternatively, keep it with the others and justify it with a quoted rule instead of "close to". Update ISSUES.md and PROGRESS.md so all three say the same.

MINOR — reviews/step6_analysis.md, "1–2★ → NEUTRAL (4)" ("99795 … (sarcasm read as neutral)") and "Does the hunch hold?" ("The model-side weakness is narrower…") — Review 99795 is described but not counted as a failure to follow instructions. Prompt v3 has an explicit rule for sarcasm, and the text the model saw contains a complaint word ("stolen"). The analysis examines instruction-following only for the NEUTRAL→NEGATIVE cell. A reader could conclude the other off-diagonal cells are all disagreement between the stars and the words, and this row is not. — Evidence: v3 line "Sarcasm: classify the intended meaning, not the literal words." `row_texts.txt`: `[99795] 1.0 NEGATIVE->NEUTRAL anticipation | TITLE: 'One Star' | TEXT: 'There is a very small chance that any Gift Card will not be stolen in the mail.'` — Suggested fix: label 99795 as a probable breach of the v3 sarcasm rule, since the words point to NEGATIVE. Then add one sentence to the model-side weakness bullet saying the instruction-following misses are not limited to the 3★ row.

MINOR — dashboard/template.html lines 381–382 (verdict line), shown on the balanced150_v3 and first100_v3 tabs — The page still leads with the cross-baseline margin framing that round 1 withdrew from the analysis, and the re-weighting note covers precision only, not the plain-accuracy headline. The balanced tab reads "Reading the reviews is worth +40.0 pts over that shortcut"; the first100_v3 tab reads "+2.0 pts". Switching tabs invites exactly the "+2.0 → +40.0 pts" comparison that ISSUES.md says "is replaced by balanced accuracy". The balanced tab's hero figure is plain accuracy (73.3%). The analysis says that figure depends on the forced 1:1:1 mix, but the page's re-weighting footnote gives only precision; the saved `balanced150_v3_population_weighted_accuracy` (94.1%) never appears. — Evidence (`reviews/step6_grader_r2_scratch/text_balanced150_v3.txt`, `text_first100_v3.txt`):
- `Reading the reviews is worth +40.0 pts over that shortcut. Weakest class: Neutral, 17 of 50 right (34.0%).`
- `Reading the reviews is worth +2.0 pts over that shortcut. Weakest class: Neutral, 0 of 2 right (0.0%).`
- `grep -c population_weighted_accuracy dashboard/template.html` → 0.
- ISSUES.md round-1 log: "The margin comparison is replaced by balanced accuracy (65.6% → 73.3%)."

Suggested fix: on balanced runs, add the re-weighted accuracy to the existing footnote (`C("balanced150_v3_population_weighted_accuracy","pct")`, a bound field). Alternatively, rename the verdict line's margin as "over this sample's own shortcut". Otherwise, record in ISSUES.md that the round-1 fix was limited to the analysis.
