# Step 2 — what the model gets right and wrong on batch_100 (binary, prompt v1)

Source files: `runs/first100_v1/metrics.json`, `runs/first100_v1/predictions.jsonl`, `runs/first100_v1/run_meta.json`, `runs/rating_distribution.json`.
Truth: rating ≥ 4 → POSITIVE, else NEGATIVE. Confusion matrix rows = truth, columns = predicted.
Revised after reviewer round 1 (`reviews/step2_grader.md`, `reviews/step2_numbers_auditor.md`).

## Class skew first
- Truth distribution: POSITIVE 93, NEGATIVE 7 (`truth_distribution.counts`).
- Majority-class baseline (always answer POSITIVE): 93.0% (`majority_baseline_accuracy` = 0.93).
- batch_100 is even more lopsided than the whole file. It is the first 100 rows in file order, not a random sample (the inclusion rule excluded 0 of them: `run_meta.selection_info.rows_skipped_by_inclusion_rule` = 0, so batch_100 = review_ids 0–99). Its NEGATIVE share is 7%, against 11.5% of the full file (1★ 8.0874% + 2★ 1.2289% + 3★ 2.1462% in `rating_distribution.json`). File-wide, "always POSITIVE" would score about 88.5%; on this batch it scores 93.0%.

## Headline
- Accuracy 97.0% = 97/100 (`accuracy`, `correct`), parse failures 0, API errors 0 (`parse_fail_count`, `api_error_count`).
- Over the baseline: +4.0 percentage points (`accuracy_minus_majority_baseline` = 0.04), i.e. 4 more reviews right out of 100 than a model that never reads anything.
- Balanced accuracy (mean of per-class recall) 91.8% (`balanced_accuracy` = 0.9178) vs 50.0% for the majority baseline (`majority_baseline_balanced_accuracy`).

## Confusion matrix (rows = truth, columns = predicted)

| truth \ predicted | POSITIVE | NEGATIVE | UNPARSED |
|---|---|---|---|
| POSITIVE (93) | 91 | 2 | 0 |
| NEGATIVE (7)  | 1  | 6 | 0 |

## Per class
- POSITIVE: recall 91/93 = 97.8%, precision 91/92 = 98.9% (`per_class.POSITIVE`).
- NEGATIVE: recall 6/7 = 85.7%, precision 6/8 = 75.0%, F1 0.800 (`per_class.NEGATIVE`).
- The NEGATIVE numbers rest on 7 reviews: one review moves NEGATIVE recall by 14.3 points. They are indicative, not stable.

## The three errors (`misclassified_review_ids`)
1. **review_id 17 — truth POSITIVE (5★), predicted NEGATIVE.** Title "No note attached to sent gift card". Text opens "the recipient loved it !" and then describes "one complaint": the note wasn't attached. The v1 prompt's mixed-review rule points to POSITIVE here. It reserves NEGATIVE for reviewers who "could not use the card, lost money, or say they would not buy again", and none of those apply. The model let one non-blocking complaint outweigh an explicit "recipient loved it". **The model did not follow its instructions; the rule itself is not the gap.**
2. **review_id 46 — truth POSITIVE (5★), predicted NEGATIVE.** Title "Love it!!", text "This is an online gift card nothing to show sorry🤪". The v1 prompt says to use the title when the text is "too short or vague to decide on its own" and to "classify from the title" when the text is filler. This text is short, joking filler (an apology for having no photo), so the prompt's rules give POSITIVE. The model reacted to "sorry" in the text instead. **The model did not follow its instructions; the rule itself is not the gap.**
3. **review_id 98 — truth NEGATIVE (3★), predicted POSITIVE.** Title "Easy to use", text "Very easy to use. I wish I knew about it earlier". The words are positive; the binary truth maps 3★ to NEGATIVE. This error is created by the truth definition rather than by the model misreading the text. It previews the Step 6 question about where 3★ reviews belong.

## What the model is good and bad at (with evidence)
- Good: clear complaints. All five 1–2★ reviews in the batch (review_ids 4, 15, 32, 51, 63) were predicted NEGATIVE. Of the two 3★ reviews, 91 was predicted NEGATIVE and 98 POSITIVE.
- Bad: following the prompt's own tie-break rules when a review is mostly positive but contains a negative-sounding word. In both POSITIVE→NEGATIVE errors the prompt's rules pointed to POSITIVE, and the model answered NEGATIVE:
  - (a) a positive title paired with apologetic filler text (46);
  - (b) a happy review with one minor complaint (17).
- Also scored as wrong: lukewarm-positive wording from a 3★ reviewer, which the binary truth rule calls NEGATIVE (98).
- Does the skew change the picture? Yes. 97.0% sounds excellent, but 93.0% comes free from the skew, and this batch is more skewed than the file. The informative numbers are the NEGATIVE row (6 of 7) and NEGATIVE precision (6 of 8), and 7 negatives are too few to trust. Step 6's balanced sample is the real test.
- Batch composition caveat: 9 rows fall into two identical groups ("Good Product" ×7: review_ids 20–24, 27, 28; "Good product" ×2: review_ids 25–26). That is 7 rows repeating an earlier row, all easy POSITIVE cases (ISSUES.md, Step 2).
