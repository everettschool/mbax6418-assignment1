# Step 6 — Three classes, balanced sampling (prompt v3)

Sources:
- **Metrics:** `runs/balanced150_v3/metrics.json`, `runs/first100_v3/metrics.json`, `runs/first100_v1/metrics.json`, `runs/*/emotion_metrics.json`.
- **Comparisons:** `runs/comparisons.json` holds the named cross-run fields, Wilson intervals and population re-weighting; these are cited as `field`.
- **Sample:** `runs/balanced150_v3/sample_ids.json`, plus the sample check `reviews/step6_sample_check.txt`.
- **Row dumps:** `reviews/step6_explore_balanced.txt`, `reviews/step6_explore_first100.txt`.
- **Evidence behind this revision:** `reviews/step6_round1_checks.txt`, `reviews/step6_round1_claim_checks.txt`, `reviews/step6_round2_checks.txt`.

Truth comes from the stars: 4–5★ POSITIVE, 3★ NEUTRAL, 1–2★ NEGATIVE. Confusion matrices put **truth (from the stars) in rows and the model's prediction in columns**.

Revised after two reviewer rounds (`reviews/step6_{grader,numbers_auditor,skeptic}.md` and `…_r2.md`).

## The 3★ verdict in one sentence
On the balanced sample, 3★ reviews mostly do **not** get their own class: 17 of 50 are predicted NEUTRAL and 33 land elsewhere. **Half (25 of 50) go to NEGATIVE**, the largest destination, and 8 go to POSITIVE. The reverse is small: 4 of 50 1–2★ reviews are predicted NEUTRAL.

## Balanced run: `balanced150_v3`
- **Sample:** 50 reviews per class, drawn with seed 42 from the whole file; ids saved in `sample_ids.json`, and an independent re-draw reproduces them.
  - Class pools (included reviews): NEGATIVE 14,178, NEUTRAL 3,270, POSITIVE 134,913.
  - Star mix: 1★ 43, 2★ 7, 3★ 50, **4★ 0**, 5★ 50 (`sample_rating_counts`).
- **Class distribution:**
  - Truth: POSITIVE 50 / NEUTRAL 50 / NEGATIVE 50.
  - Predicted: POSITIVE 57 / NEUTRAL 23 / NEGATIVE 70 / UNPARSED 0.
- **Accuracy 73.3%** (110/150) (`accuracy`). Every class is the same size, so any single constant answer scores 33.3% (`majority_baseline_accuracy`). Balanced accuracy is 73.3% and macro F1 70.4%.
- **Parse failures 0, API errors 0.** One row needed a retry; see "Repeatability".

| truth \ predicted | POSITIVE | NEUTRAL | NEGATIVE | UNPARSED |
|---|---|---|---|---|
| POSITIVE (50) | **48** | 2 | 0 | 0 |
| NEUTRAL (50)  | 8 | **17** | 25 | 0 |
| NEGATIVE (50) | 1 | 4 | **45** | 0 |

| class | recall (right / truth) | precision on this sample (right / predicted) |
|---|---|---|
| POSITIVE | 48/50 = 96.0% | 48/57 = 84.2% |
| NEUTRAL | 17/50 = 34.0% | 17/23 = 73.9% |
| NEGATIVE | 45/50 = 90.0% | 45/70 = 64.3% |

### What the balanced sample measures well, and what it doesn't
- **Measured well: per-class recall and balanced accuracy.** Each class has 50 reviews. The model is strong at the poles (POSITIVE 96.0%, NEGATIVE 90.0%) and weak in the middle (NEUTRAL 34.0%).
- **Tied to the sample's forced 1:1:1 mix: precision and plain accuracy.** The whole file is 88.5% POSITIVE, 2.1% NEUTRAL, 9.3% NEGATIVE (`population_weights`). Re-weighting each truth row's prediction shares by that mix (an addition; rough, see below):
  - **Accuracy would be about 94.1%** (`balanced150_v3_population_weighted_accuracy`).
  - **NEUTRAL precision would be about 14.5%, not 73.9%** (`balanced150_v3_population_weighted_precision.NEUTRAL`).
  - About 70.6% of NEUTRAL answers would land on 4–5★ reviews (`…_population_weighted_share_of_neutral_predictions_from_positive`).
  - The 3★ share of NEGATIVE predictions is 25 of 70 = 35.7% on the sample (`balanced150_v3_share_of_negative_predictions_from_neutral`) but about 11.4% re-weighted (`…_population_weighted_share_of_negative_predictions_from_neutral`).
- **Why the re-weighting is rough:** it rests on small off-diagonal counts (e.g. 2 POSITIVE→NEUTRAL), the POSITIVE draw has no 4★ reviews, and it assumes sampled reviews behave like their pools.

## Where the mistakes go, both directions (`comparisons.json`)
| from (stars) → to (model) | reviews | share of 50 | Wilson 95% interval | field |
|---|---|---|---|---|
| 3★ → NEGATIVE | 25 | 50.0% | 36.6%–63.4% | `balanced150_v3_neutral_to_negative`, `…_share`, `…_share_wilson95` |
| 3★ → POSITIVE | 8 | 16.0% | 8.3%–28.5% | `balanced150_v3_neutral_to_positive_share_wilson95` |
| 3★ → NEUTRAL (correct) | 17 | 34.0% | 22.4%–47.8% | `balanced150_v3_neutral_recall_wilson95` |
| 1–2★ → NEUTRAL | 4 | | | `balanced150_v3_negative_to_neutral` |
| 4–5★ → NEUTRAL | 2 | | | |
| 1–2★ → POSITIVE | 1 | | | |
| 4–5★ → NEGATIVE | 0 | | | |

- **The movement runs one way.** NEUTRAL→NEGATIVE exceeds NEGATIVE→NEUTRAL by 21 reviews (`balanced150_v3_neutral_errors_to_negative_minus_negative_errors_to_neutral`). Middling reviews are read as negative; negative ones are seldom softened to neutral.
- **The assignment's example question:** 3★ reviews labelled negative (25) is the larger effect, and negative reviews called neutral (4) the smaller.

## The 25 3★ reviews predicted NEGATIVE, re-graded against the prompt
Each of the 25 was read exactly as the model saw it (`reviews/step6_round2_checks.txt` §A) and checked against every rule in `prompts/sentiment_v3.txt`. These gradings are my judgment; the ids are listed so they can be checked.

- **17 are NEGATIVE under the prompt's own rules:**
  - **Card did not work, money lost, or payment declined** ("could not use the card, lost money → NEGATIVE"): 6689 "Beware of dud cards… rejected as used", 33885 "It did not work. I lost the money.", 114708 "It kept saying my funds were declined".
  - **Says they would not buy again:** 60608 "I probably won't be using it again".
  - **The text decides against a positive title:** 88787, title "Still a happy recipient of this gift." but text "…Very disappointed."
  - **Problem or complaint with no praise at all:** 18646 "did not receive the ornament", 29467 cannot tell $25 from $50 cards, 48586 "encountered an error when trying to reload… took longer", 88199 "Did not receive mini envelope", 88606 cannot tell card values apart, 94255 "much more difficult… 'fixed' something… that was NOT broken", 111827 "look so cheap… embarrassed", 119458 "I dislike the fact that…", 129667 promo "I can't seem to use… Disappointed".
  - **Complaint clearly outweighs praise:** 121389, "a breeze" then a long complaint ending "Bad bad bad".
  - **Not about gift cards** (dataset noise, but negative in words): 140179 (a device "not responding"), 143371 (a shaver).
- **8 are judgment calls where v3's NEUTRAL wording plausibly applies:**
  - 4880: title "It's a gift card", text "I was hoping I could recharge this card." That is a wish more than "a real problem", and "it's a gift card" is the prompt's own lukewarm example.
  - 22082: a wish plus self-blame, "I knew better, just wasn't thinking".
  - 32735: "There is nothing wrong about this giftcard… But… it was not sent along".
  - 51332: title "It's okay." ("sums it up as merely okay → NEUTRAL") against a complaining text ("the TEXT decides"). Two rules pull opposite ways.
  - 53136: "I didnt get my 10$…", then "its awesome". A bonus not received is not clearly "lost money".
  - 60681: "delivered the next day, as promised. But… the message… was missing".
  - 111780: title blanked, text "Not as fast as the egift card", a mild comparison.
  - 147336: "The gift is fine, but… they are not marked."
- **So up to 8 of the 25 are candidate failures to follow the prompt, and 17 follow it.** *Round 1 said "at most 7" and then "at most 3"; both counts came from re-grading only some of the rows and are withdrawn.*

### What this does and does not show
- The 17 do **not** show that the stars are wrong. They show that the model obeyed the prompt's policy, and that policy is a design choice made in Step 1 for two classes and carried into v3 unchanged: card problem, lost money or won't buy again → NEGATIVE. The reviewers of those 17 still rated their experience 3★, i.e. middling by their own account.
- So the NEUTRAL→NEGATIVE cell mostly measures disagreement between this prompt's policy and the reviewers' ratings, plus up to 8 plausible model misses.
- Which side is "right" is not settled by this run. A prompt variant that treats a single, resolved-or-minor card problem as NEUTRAL was not tested (future work).

## The other off-diagonal cells
- **3★ → POSITIVE (8).** All 8 are POSITIVE under the prompt's rules, so these are the stars and the words disagreeing.
  - Five have short, plainly positive text. Four of them had their auto-filled "Three Stars" title blanked: 43478 "Children loved them", 73030 "I like very good products.", 144067 "Good because I spent my gift card.", 146724 "good". The fifth is 134401 "Yas"/"Yas".
  - The other three are mixed-to-positive: 20086 "Very fast, accurate and available… after I figured it out, it was very easy"; 23773, bought as party prizes; 144273 "I appreciate having the ability…".
- **1–2★ → NEUTRAL (4).**
  - 31137 (title blanked) "bought it for my dad…", 49142 in Spanish "Nada de especial / Es como cualquier otra forma de pagar" ("nothing special; like any other way to pay"), and 136849 "Just found it." contain no complaint words and fit v3's lukewarm rule.
  - **99795** (title blanked), "There is a very small chance that any Gift Card will not be stolen in the mail.", contains "stolen" and is sarcastic. v3 says "Sarcasm: classify the intended meaning", which points to NEGATIVE, so this is **a probable instruction-following miss outside the 3★ row**.
- **4–5★ → NEUTRAL (2).** 12158 "You can't really go wrong with a gift card", 43820 "It's a gift card, just like the description." This is v3's lukewarm rule applied as written.
- **1–2★ → POSITIVE (1).** 116236 "The recipient… was surprised to find that Amazon gift cards came with a tin as the 'wrapping'." The words read mildly positive.
- **Across all 40 balanced errors,** about 9 are candidate prompt-following misses (up to 8 in 3★→NEGATIVE, plus 99795). The rest follow the prompt's rules and disagree with the stars.

## Same prompt, lopsided sample: `first100_v3` vs `balanced150_v3`
Only the sampling changes; prompt v3, model and settings are identical.

| | first100_v3 | balanced150_v3 |
|---|---|---|
| truth counts (POS/NEU/NEG) | 93 / 2 / 5 | 50 / 50 / 50 |
| star mix (1★/2★/3★/4★/5★) | 4 / 1 / 2 / 2 / 91 | 43 / 7 / 50 / 0 / 50 |
| accuracy | 95.0% (95/100) | 73.3% (110/150) |
| majority baseline | 93.0% | 33.3% |
| POSITIVE recall | 90 of 93 | 48 of 50 |
| NEUTRAL recall | 0 of 2 | 17 of 50 |
| NEGATIVE recall | 5 of 5 | 45 of 50 |

Fields: `comparisons.json` `first100_v3_*` / `balanced150_v3_*`; per-class values from each run's `metrics.json`.

- **Accuracy falls by 21.7 points** (`accuracy_balanced150_v3_minus_first100_v3`), and the class mix explains it.
  - The balanced run's per-class recalls, applied to batch_100's counts (93/2/5), predict **94.5%** accuracy for batch_100 (`first100_v3_accuracy_expected_from_balanced150_v3_recalls`); the observed value is 95.0%.
  - The model performs about the same per class on both samples. batch_100 simply contains almost nothing but the easy class.
- **The lopsided run cannot measure the hard classes.** It has 2 NEUTRAL and 5 NEGATIVE reviews.
  - Its balanced accuracy of 65.6% would become 82.3% if one of its 2 NEUTRAL reviews had been right (`first100_v3_balanced_accuracy_if_one_more_neutral_right`). A change in balanced accuracy between the two runs is therefore not a finding.
  - What the balanced run adds is the per-class picture with 50 reviews each: NEUTRAL recall 34.0%, and half of 3★ reviews going to NEGATIVE.
- **What changed on batch_100 from binary v1 to v3** (`reviews/step6_explore_first100.txt`):
  - Only two predictions moved: 46 (NEGATIVE → NEUTRAL) and 83, "This was for a gift" (POSITIVE → NEUTRAL, via the lukewarm rule). Both are 5★, so both count as errors.
  - The two 3★ reviews (91 → NEGATIVE, 98 → POSITIVE) are still wrong under three-class truth.

## Q1 context: the binary run as originally scored
`first100_v1` scored 97.0% (97/100) against a 93.0% majority baseline, with 7 NEGATIVE reviews in the batch (`comparisons.json: first100_v1_*`). The high accuracy is mostly the skew. The balanced three-class run shows what it hides: the middle class is found 34.0% of the time.

## Does the hunch hold?
- **Partly.** 3★ reviews mostly do not get their own class (33 of 50 land elsewhere).
- **The largest destination is NEGATIVE, with half (25 of 50).** The 95% interval of 36.6%–63.4% means this sample cannot say whether that is a majority. 8 go to POSITIVE.
- **Most of the NEGATIVE destination is the prompt's inherited policy meeting reviewers who still gave 3★** (17 rows). Up to 8 rows are plausible model misses.
- **The clearest model-side weakness is that it rarely answers NEUTRAL:** 23 NEUTRAL predictions for 50 NEUTRAL reviews.

## Would another sample change the story?
- **Sampling variation** (Wilson 95%, `comparisons.json`). The intervals treat the stratified draw as simple random sampling, so they are approximate.
  - A per-class share measured on 50 reviews moves by about ±10 to ±13 points: NEUTRAL→NEGATIVE 36.6%–63.4%, NEUTRAL recall 22.4%–47.8%, NEUTRAL→POSITIVE 8.3%–28.5%.
  - Plain accuracy over all 150 reviews moves by about ±7 points: 65.7%–79.8% (`balanced150_v3_accuracy_wilson95`).
- **Direction.** The NEUTRAL→NEGATIVE interval does not overlap the NEUTRAL→POSITIVE interval. Both come from the same 50 reviews, so this is descriptive, not a formal test.
- **Sample composition across 1,000 other seeds** (composition only; not classified, so model results under other seeds are untested; `reviews/step6_round1_checks.txt` §2):
  - 63 of 1,000 seeds also draw no 4★ reviews.
  - Blanked star-phrase titles in the whole draw have median 21 and 5th–95th percentile 14–28; seed 42 has 26.
  - Seed 42 put 10 blanked titles into the NEUTRAL draw (mean 6.6).
- **Effect on the 3★ → POSITIVE cell: about one review.** Blanked NEUTRAL rows were predicted POSITIVE 4 of 10 times, the others 4 of 40. At the seed mean, the cell would hold about 7.0 reviews instead of 8 (`reviews/step6_round2_checks.txt` §D).
- **For contrast:** `first100_v3` accuracy 95.0% has interval 88.8%–97.8%, and `first100_v1` 97.0% has 91.5%–99.0%. Both sit on top of their 93.0% baselines.

## Repeatability
- Review 4880 was the only row in any run that needed a retry. Its first reply, `LABEL=NEGATIVE;EMOTION=disappointment`, used an emotion outside the allowed eight. The retry, with identical messages at temperature 0, replied `LABEL=NEGATIVE;EMOTION=sadness`.
- **The endpoint is therefore not fully deterministic at temperature 0.** The published numbers are reproduced from the committed predictions and the cache. A fresh uncached run may change individual labels, and the Wilson intervals do not cover that.

## Emotions on the three-class runs (beside both baselines)
- **`balanced150_v3`:**
  - The LLM agrees with the NRC word list on 16/150 = 10.7%, and 16/59 = 27.1% where the word list has a single winner (`agreement_rate_*`).
  - The LLM's most common emotion here is anger (62 of 150). A constant "anger" agrees only 4/150 (2.7%), because the word list rarely says anger.
  - The strongest single constant is anticipation: 22/150 = 14.7%, and 22/59 = 37.3% (`best_constant_baseline_*`). **The LLM is 4.0 points below it on all rows and 10.2 points below where the word list has one winner** (`llm_minus_best_constant_*`).
  - The word list tied on 67 reviews and found no emotion words in 24.
- **`first100_v3`:** agreement 20/100 against a constant "joy" at 22/100 (−2.0 points). In the 18 reviews where the LLM did not say joy, the two agree 0 times.
- **Across all three emotion runs, the LLM never agrees with the word list more often than the best constant answer.** The Step 5 conclusion carries over: the two readings largely measure different things.
- **Where the LLM's emotions come from on the balanced sample** (`reviews/step6_round1_checks.txt` §5): anger comes from the non-positive classes (NEGATIVE 41, NEUTRAL 21). Trust is spread across classes: POSITIVE 10, NEUTRAL 11, NEGATIVE 1.
- **Why the word list rarely follows the LLM** (`reviews/step6_round2_checks.txt` §C): its "anticipation" answers are carried by topic and logistics words, not by the reviewer's feeling.
  - Across its 22 anticipation answers, the anticipation-tagged hits are gift 31, time 13, delivery 7, money 7, store 4.
  - "gift" is among the hits in 17 of the 22, but removing "gift" leaves 18 of the 22 still anticipation. It co-occurs with the pattern; it does not cause it alone.
  - Example: 11674, a complaint about a missed UPS delivery ("delivery" ×4, "attempt", "store"), where the LLM says anger.
  - Example: 119173, "Stole my money! …" ("money" ×4), where the LLM also says anger.
  - On the 25 3★→NEGATIVE rows, the word list answers anticipation 7, TIE 6, NONE 4, trust 4, fear 2, sadness 1, anger 1, while the LLM says anger for 20.

## Caveats
- **No 4★ reviews in the balanced POSITIVE class.** The run says nothing about 4★ reviews, the likeliest to sit near NEUTRAL. The dashboard shows each run's star mix.
- **26 of 150 titles were auto-filled star phrases and were blanked for the model** (4 of 100 in batch_100). This is expected from the pools: star-phrase titles are 22.7% of POSITIVE, 13.1% of NEUTRAL and 5.8% of NEGATIVE.
- **An empty title is not neutral information.** No included review in the file has an originally empty title, so an empty title in the prompt always means a blanked star phrase, and blanking rates differ by class. Blanked NEUTRAL rows were predicted POSITIVE 4 of 10 times against 4 of 40 for the rest (Fisher exact one-sided p = 0.041, `reviews/step6_round2_checks.txt` §D). Their short positive texts may explain this fully, but the blank may carry a weak signal derived from the rating.
- **Two reviews' own words mention stars and reached the model:** 121389 in its text ("Cannot give 5 stars…") and 140676 in its title ("I would give this 'zero stars'"; predicted NEGATIVE correctly). A third word hit, 138151's title "Helpful Review", is not rating-related.
  - The exact blanking rule would miss 103 other star-count titles in the file, such as "5 stars", "Three stars." and "0 stars". None of them are in the four saved runs. `verify_leak.py` now fails if one is ever sent (§E).
- **Prompt v3 sends lukewarm reviews to NEUTRAL by rule.** Some NEUTRAL successes, and the two POSITIVE→NEUTRAL errors, are that rule at work.
