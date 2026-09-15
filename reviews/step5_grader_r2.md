# Step 5 Grader — round 2

Checked and passing:
- **Literal requirements are met.**
  - Prompt v2 asks for both sentiment and one of the eight emotions.
  - The word list sums scores per emotion over the eight emotions only and takes the highest. TIE and NONE are reported, and a tie-break alternative is added.
  - It makes no model calls and runs over the existing predictions.
  - Both emotions are kept per row, and the two are compared three ways, next to a constant baseline.
- **The "Ask yourself" questions can be answered from saved files.**
  - How often they agree: `emotion_metrics.json`.
  - Where they diverge: the cross-tab and 18 divergent ids.
  - Why they diverge: the analysis, with row-grounded hits.
- **ISSUES.md has 10+ Step 5 entries**, including the round-1 fix log.
- **Reproducible.** I re-ran on a copy (`reviews/step5_grader_r2_scratch/first100_v2`), and `cmp` reports both `predictions.jsonl` and `emotion_metrics.json` byte-identical, including the new round-2 fields.
- **Round-2 claims re-derived independently, all matching:**
  - constant joy 22/100 and 22/38;
  - non-joy LLM rows agree on 1 of 20 (id 38);
  - tie-break agreement 23/100;
  - unique rows 93, agree 20, TIE 40;
  - negation: 15 hits in 11 rows;
  - all 8 joy→anticipation rows are decided by one anticipation-only word (9, 41, 42, 70 mail; 71, 93 time; 16 recipient; 95 store ×2);
  - 8 of 9 LLM trust rows are "easy/convenient" reviews;
  - the 8 "easy" NONE rows (67, 68 and 98 contain "easy");
  - the 7 anger rows: 6 NEGATIVE, plus review 17.
- **Build and verification are current.** `dashboard/index.html` (14:57:17) and `reviews/step5_verify_dashboard.txt` (14:57:20, 1342 checks, PASS) are newer than the last `template.html` edit (14:57:06). The built page contains the final context sentence, and the round-1 "anticipati/on" header break is fixed at 1440px.

## Findings

MINOR — reviews/step5_analysis.md, "Literal 'take the highest' reading" bullet (and `emotion_metrics.json#agreement_tiebreak`) — "The picture does not change" is stated with no baseline for the tie-break variant, which is the gap round 1 flagged. The fixed order (anger, anticipation, …, joy, …) also biases the result without saying so. Anticipation comes before joy, so every tie that contains anticipation (45 of 47) is broken to anticipation. — Evidence: my recomputation over `runs/first100_v2/predictions.jsonl` gave `tiebreak label counts Counter({'anticipation': 57, 'joy': 23, 'NONE': 15, 'anger': 2, ...})` and `tie sets with anticipation 45`. Against the tie-broken word list, `tb const anticipation 57` and `tb const joy 23`, while `tiebreak llm 23`. So the LLM only equals constant joy, and a constant "anticipation" matches the tie-broken word list 57/100. The conclusion happens to survive, but the text gives no evidence for it, and the order effect (the word list becomes "anticipation" for 57 reviews) is not disclosed. — Suggested fix: add the constant baselines under the tie-break (joy 23/100; best constant, anticipation, 57/100) to `emotion_metrics.json` and the analysis. State that the alphabetical order sends 45 ties to anticipation, which makes this alternative an artifact of the order rather than a neutral literal reading.

MINOR — reviews/step5_analysis.md "Negation is counted, not reversed" (and ISSUES.md round-1 log, "mostly rhetorical 'who doesn't love'") — "Most are rhetorical, where reversing would be wrong" is false by the saved rows. Only 5 of the 15 negated hits are rhetorical. The follow-up "the LLM reads them in context" has no evidence behind it, and one of the two negation examples cited (46) is the review where the LLM gave an implausible disgust. — Evidence: `reviews/step5_round2_explore.txt` negation block. The rhetorical hits are 3 'who doesn t love', 3 'doesn t love shopping', 57 'who wouldn t love', 57 't love this wonderful', 76 'is not to love' = 5. The other 10 are real or accidental negations: 1 'never too late', 4 'not gift', 4 't able to cover', 46 'nothing to show', 63 'not as gift', 64 'nothing is good', 76 'no service fee', 90 'not necessary i recommend' (a window false positive), 91 'without the fees', 95 't have to leave'. — Suggested fix: say "5 of 15 are rhetorical (3, 57, 76); the rest are real negations or window false positives". Drop or evidence the claim that the LLM handles them, and mirror the correction in ISSUES.md.

MINOR — ISSUES.md, "[Step 5] LLM emotion has its own failures" — The last sentence contradicts the corrected finding. It says the LLM's "agreement advantage partly reflects a skewed batch", but after round 1 the LLM has no agreement advantage: it is below the constant baseline. — Evidence: quoted "The LLM also answered joy for 80 of 100 reviews, so its agreement advantage partly reflects a skewed batch." against `llm_minus_constant_rate_all_rows: -0.0199…` and `llm_minus_constant_rate_excluding_none_and_tie: -0.0526…`, and the ISSUES entry "Emotion agreement is no better than a constant 'joy' answer". — Suggested fix: rewrite it as "…so the batch is dominated by joy, and the LLM's agreement is 2.0 points below simply answering joy".

MINOR — PROGRESS.md — The round-1 Grader finding about the stale PROGRESS.md is logged in ISSUES.md as fixed ("updated PROGRESS.md"), but the file is still out of date. It still lists the round-1 findings as open and the claim checks and screenshot as remaining, although both files exist. — Evidence: quoted "Step 5 — Primary emotion, two ways (reviewer round 1 done; fixing findings)", "Step 5 round 1 (...), all being fixed:", and "Remaining: verify analysis claims (`reviews/step5_claim_checks.txt`), view emotion screenshot, Grader + Numbers Auditor, fix, record gate, commit." `reviews/step5_claim_checks.txt` exists (14:47:40), and the round-1 fixes are recorded in ISSUES.md. — Suggested fix: mark round 1 fixed and list round 2 as the current review. Update "Remaining" to name the screenshot of the final build still to be viewed (see next finding) and the gate.

MINOR — dashboard emotion section (dashboard/template.html renderEmotion layout; built dashboard/index.html) — The section is only checked at desktop width. At a narrow viewport it breaks. No screenshot of the final build was viewed: the provided `step5_emotion_section_r2.png` (14:56:49) predates the last template edit (14:57:06). — Evidence: `reviews/step5_grader_r2_scratch/overflow.py` (Playwright, 400px viewport, emotion tab) printed `scrollWidth: 509` with offenders `{'tag': 'DIV', 'section': 'sec-emotion', 'right': 509}` ×2 (the bar pair and the cross-tab). Screenshot `reviews/step5_grader_r2_scratch/emotion_400.png` shows:
- the NRC word-list bars and counts clipped off the right edge, with the legend cut to "N";
- cross-tab columns after "sadness" cut off;
- the headers "anticip." and "disgust" running together as "anticipdisgust".

At 1440px (`emotion_1440.png`) the layout is fine, and there are no console errors or external requests. — Suggested fix: stack the bar pair and cross-tab to one column below ~700px, and put the cross-tab in its own `overflow-x:auto` wrapper. Capture and view a screenshot of the final build at desktop and narrow widths.

MINOR — reviews/step5_analysis.md "Duplicates" bullet (and ISSUES.md "tied on 47 rows (9 of them duplicate 'Good Product' rows; 40 of 93 unique reviews)") — The two numbers do not add up for a reader: 47 − 9 = 38, yet the unique-row TIE count is 40. The 9 ids (20–28) are the whole duplicate group, including the two first copies that de-duplication keeps. Only 7 are removed repeats, which matches PROGRESS.md's "7 duplicate … repeats". — Evidence: de-duplicating on (title, text), keeping the first occurrence, gave `unique 93 20 40`, and the removed TIE ids were `[21, 22, 23, 24, 26, 27, 28]` (7). — Suggested fix: write "9 of the 47 TIE rows belong to the duplicate 'Good Product' groups (ids 20–28); removing the 7 repeats leaves TIE 40 of 93 unique reviews".
