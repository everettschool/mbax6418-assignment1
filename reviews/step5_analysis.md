# Step 5 — Primary emotion, two ways (batch_100, prompt v2)

Sources: `runs/first100_v2/emotion_metrics.json` (fields cited in backticks), `runs/first100_v2/predictions.jsonl` (per-row `llm_emotion`, `nrc_emotion`, `nrc_tied`, `nrc_scores`, `nrc_hits`, `nrc_emotion_tiebreak`, `nrc_negated_hits`), `runs/nrc_lexicon_meta.json`, exploration output `reviews/step5_emotion_explore.txt`, `reviews/step5_round2_explore.txt`, `reviews/step5_claim_checks.txt`.
Cross-tab orientation: rows = LLM emotion, columns = NRC word-list emotion.
Revised after reviewer round 1 (`reviews/step5_grader.md`, `reviews/step5_numbers_auditor.md`).

## How the two methods work
- **LLM** (`prompts/sentiment_v2.txt`): the model names one of the eight emotions per review, alongside the sentiment label. The prompt glosses each emotion; for example, trust is "relies on it, finds it dependable, safe, or convenient".
- **NRC word list** (`src/nrc_emotion.py`, no model calls): EmoLex v0.92, 14,154 words, of which 4,454 carry at least one of the eight emotions (`runs/nrc_lexicon_meta.json`).
  - Input: lowercase alphabetic tokens from the same title + text the model saw.
  - Stemming fallback: if a token isn't in the lexicon, strip "ing", "ed", "es" or "s" and use the stem when that is in the lexicon.
  - Scoring: sum per emotion over the eight emotions only; the positive and negative columns are excluded, and the code asserts this.
  - Result: argmax. A tie is reported as TIE, no hits as NONE.

## Agreement, three ways, next to a skew baseline
The LLM answered joy for 80 of 100 reviews, so the relevant baseline is a constant answer of "joy" (`constant_baseline_emotion`), scored against the same word list.

| Subset | LLM agrees with word list | Constant "joy" agrees with word list |
|---|---|---|
| All reviews | 20 / 100 = 20.0% (`agreement_rate_all_rows`) | 22 / 100 = 22.0% (`constant_baseline_rate_all_rows`) |
| Excluding NONE | 20 / 85 = 23.5% (`agreement_rate_excluding_none`) | 22 / 85 = 25.9% (`constant_baseline_rate_excluding_none`) |
| Excluding NONE and TIE | 20 / 38 = 52.6% (`agreement_rate_excluding_none_and_tie`) | 22 / 38 = 57.9% (`constant_baseline_rate_excluding_none_and_tie`) |

- The LLM is **below** the constant-joy baseline: −2.0 points on all reviews (`llm_minus_constant_rate_all_rows`) and −5.3 points where the word list has a single winner (`llm_minus_constant_rate_excluding_none_and_tie`). On this batch, agreement between the two methods is no better than always answering joy.
- Where the LLM did **not** say joy, the two methods almost never meet: 1 of 20 reviews agree (5.0%), and 1 of 11 among those with a single word-list winner (9.1%) (`agreement_llm_not_constant`). All other agreement is the two methods both landing on joy (cross-tab joy→joy 19; the one other diagonal cell is anticipation→anticipation 1).
- Ties do not rescue the LLM. The word list tied on 47 reviews (`tie_rows`); the LLM's emotion is among the tied emotions in 45 (`tie_rows_llm_emotion_in_tied_set`), but "joy" alone is also in 45 (`tie_rows_constant_in_tied_set`). Tie containment therefore says nothing about the LLM specifically. *(Round 1 of this analysis claimed it did; the Grader showed the constant-joy answer does as well, and that claim is withdrawn.)*
- Literal "take the highest" reading: break ties by the fixed emotion order anger → trust (`tiebreak_rule`).
  - The LLM then agrees with the word list on 23 / 100 = 23.0%, or 23 / 85 = 27.1% excluding NONE (`agreement_tiebreak`).
  - This alternative is an artifact of the order, not a neutral reading. Anticipation comes before joy, so 43 of the 47 ties become anticipation; 2 become anger, 1 disgust and 1 joy (`tie_rows_broken_to`). The tie-broken word list says anticipation for 57 of 100 reviews (`tiebreak_label_counts`).
  - Under it, a constant "joy" also agrees 23 / 100 = 23.0%, the same as the LLM. A constant "anticipation" agrees 57 / 100 = 57.0% (`tiebreak_constant_baseline`).
  - So the conclusion holds under either reading: the LLM does no better than a constant answer. The tie-break only moves which constant looks best.
- Duplicates: 9 of the 47 TIE rows belong to the duplicate "Good Product" / "Good product" groups (ids 20–28; see Step 2). Removing the 7 repeats (keeping the first copy of each group) leaves 93 unique title+text reviews: agree 20, TIE 40, NONE 15 (`unique_title_text`).

## What each method says (`llm_emotion_counts`, `nrc_emotion_counts`)
- LLM: joy 80, trust 9, anger 7, anticipation 3, disgust 1; fear, sadness and surprise 0.
- NRC: TIE 47, joy 22, NONE 15, anticipation 14, sadness 1, trust 1; anger, fear, disgust and surprise 0.
- The word list never produced anger. The LLM said anger for 7 reviews: 6 are NEGATIVE-truth (4, 15, 32, 51, 63, 91), and one is the 5★ complaint review 17 (`reviews/step5_claim_checks.txt`).

## Cross-tab, non-zero cells (`crosstab_cells`)
- joy row: joy→joy 19, joy→TIE 44, joy→NONE 9, joy→anticipation 8.
- anger row: anger→anticipation 3, anger→joy 1, anger→sadness 1, anger→trust 1, anger→NONE 1.
- trust row: trust→NONE 5, trust→anticipation 2, trust→joy 1, trust→TIE 1.
- anticipation row: anticipation→TIE 2, anticipation→anticipation 1.
- disgust row: disgust→joy 1.

## Divergent reviews, each explained by its own words and lexicon hits
Divergent means the word list had a single winner that differs from the LLM (`divergent_review_ids`, 18 rows). Hits are shown as token → lexicon word (emotions), taken from `nrc_hits`.

1. **review_id 51 — LLM anger, NRC anticipation** (scores: anticipation 3, joy 2, surprise 2, trust 1).
   - Text: "Purchasing an Amazon gift card came with an added monetary value but no more. A Bronx cheer for you!"
   - Hits: gift (anticipation, joy, surprise); monetary (anticipation); cheer (anticipation, joy, surprise, trust).
   - "A Bronx cheer" is a jeer: the reviewer is annoyed that the bonus was withdrawn. The word list reads the idiom literally as cheerful, and "gift" and "monetary" are topic words.
   - **Limitation shown:** sarcasm and idiom read literally; topic nouns scored as emotion.

2. **review_id 32 — LLM anger, NRC sadness** (scores: sadness 2, anger 1, trust 1).
   - Title "Mistake"; text "Hit button by mistake n deduction from credit card on file".
   - Hits: mistake ×2 (sadness), once from the title and once from the text; hit (anger); credit (trust).
   - "Hit" means pressing a button, but the lexicon tags it anger. "Credit" is tagged trust. Sadness wins only because the title word repeats in the text.
   - **Limitation shown:** word sense ignored; repeated title words double-count.

3. **review_id 63 — LLM anger, NRC trust** (scores: trust 6, anticipation 3, fear 2, joy 2, sadness 2, surprise 1).
   - Text includes "It was difficult to use. Must be run as credit, not as gift card. No remaining balance is given… I misplaced or lost this card".
   - Hits include credit ×2 (trust), transaction (trust), provide (trust), problem (fear, sadness), difficult (fear), lost (sadness).
   - Payment vocabulary wins trust. The complaint words are split across fear and sadness, so no single negative emotion outscores trust.
   - **Limitation shown:** transaction words tagged trust; negative feeling spread over several emotions loses.

4. **review_id 17 — LLM anger, NRC anticipation** (scores: anticipation 9, joy 4, surprise 3, trust 2, anger 1).
   - Text: "What a pretty gift card presentation, the recipient loved it! I have one complaint… the note wasn't attached".
   - Complete hit list: gift ×3 (anticipation, joy, surprise); pretty (anticipation, joy, trust); recipient ×2 (anticipation); time and times → time (anticipation); mail (anticipation); showed → show (trust); complaint (anger).
   - The single anger word is outvoted 9 to 1 on anticipation. 8 of those points come from topic words (gift ×3, recipient ×2, time ×2, mail) and 1 from "pretty". Joy 4 = gift ×3 + pretty; trust 2 = pretty + show.
   - "loved" does **not** hit: the fallback strips "ed" to "lov", which is not in the lexicon ("love" is, tagged joy; `reviews/step5_claim_checks.txt`).
   - **Limitation shown:** the simple suffix fallback misses "loved" → "love"; topic words outvote the one complaint word.

5. **review_id 46 — LLM disgust, NRC joy** (scores: joy 2, anticipation 1, surprise 1, trust 1).
   - Title "Love it!!"; text "This is an online gift card nothing to show sorry🤪".
   - Hits: love (joy); gift (anticipation, joy, surprise); show (trust).
   - Here the word list is closer to the reviewer, and the **LLM is the odd one out**: disgust fits neither the title nor the playful apology. The model also mislabeled this review NEGATIVE in Step 2.

6. **review_ids 9, 16, 41, 42, 70, 71, 93, 95 — LLM joy, NRC anticipation** (the largest divergent cell, `crosstab_cells` joy→anticipation = 8).
   - Every one of the 8 is decided by a word the lexicon tags *only* anticipation. Without it, anticipation is no longer the sole winner in any of them (`reviews/step5_round2_explore.txt`).
   - The words: mail in 9, 41, 42 and 70 (from "mail person" / "mailed right out" / "in the mail"); time in 71 and 93 ("just in time", "on time"); recipient in 16; store in 95 (twice).
   - Clean example, review 9: title "Great for saying 'thank you' to the mail person, farrier, yard man, etc", text "So many people / Make your life better so remember them!". The only hit is mail (anticipation), so the word list says anticipation. The LLM reads gratitude and says joy.
   - Review 93 also hits "fits" (anger) from "One size fits all", a word-sense error, though anger does not win there.
   - **Limitation shown:** delivery and logistics words are tagged anticipation, and in short reviews one such word decides the answer.

## Where the word list gives no single answer
- **NONE (15 rows):**
  - 8 are short "easy" reviews: 31, 49, 55, 67, 68, 78, 97, 98 (e.g. 31 "So easy" / "Easy to do"). "easy", "great" and "works" are not emotion words in the lexicon (`reviews/step5_claim_checks.txt`).
  - Others are emoji-only (45 "👍" / "👍") or contain no emotion vocabulary at all (15 "Card did not work!!!!").
  - The LLM still names an emotion for all 15: joy 9, trust 5, anger 1.
  - **Limitation shown:** coverage gaps for everyday evaluative words and emoji.
- **TIE (47 rows):**
  - Multi-tagged topic words cause most ties. "gift" (anticipation, joy, surprise) is hit 104 times across the batch and 40 times inside tie rows; "good" (anticipation, joy, surprise, trust) is hit 29 times inside tie rows.
  - The most common tied sets: {anticipation, joy, surprise} 15; {anticipation, joy} 14; {anticipation, joy, surprise, trust} 13.
  - 8 reviews have "gift" as their only hit word, so they tie by construction.
  - **Limitation shown:** in a gift-card corpus the product name is itself an emotion word.

## Two further causes of divergence
- **Negation is counted, not reversed.**
  - 15 hits in 11 reviews follow a negator within 3 tokens (`negation`). Read in context (`reviews/step5_round2_explore.txt`), they split three ways:
  - **5 rhetorical, where reversing would be wrong:** "who doesn't love" and "doesn't love shopping" (3), "who wouldn't love" and "love this wonderful" (57), "is not to love" (76).
  - **6 real negations that the word list scores as if affirmed:** "wasn't able to cover" (4), "nothing to show" (46), "nothing is good" (64), "no service fee" (76), "without the fees" (91), "don't have to leave" (95).
  - **4 where the negator does not govern the hit word:** "never too late" (1), title "Not $10 Gift Cards" (4), "not as gift card" (63), "not necessary I recommend" (90).
  - A fixed token window cannot separate these cases, which is why negation is reported and not reversed. These rows do not show that the LLM handles negation better; nothing here isolates that.
- **The prompt's own definitions steer the LLM.**
  - 8 of the LLM's 9 trust answers are "easy / convenient / simple / time saver" reviews: 14, 31, 34, 49, 55, 56, 78, 97 (`reviews/step5_round2_explore.txt`). That matches the v2 gloss "trust: … dependable, safe, or convenient".
  - 5 of them are word-list NONE (31, 49, 55, 78, 97), because "easy" has no lexicon emotion. The trust→NONE 5 cell partly reflects how the prompt defines trust, not the LLM reading the review better.

## Why they differ (summary, grounded in the rows above)
- **Agreement is no better than always saying joy:**
  - LLM 20/100 vs constant joy 22/100;
  - 20/38 vs 22/38 where the word list has a single winner;
  - apart from joy, the methods meet on 1 of 20 reviews.
- **The word list counts vocabulary.** It scores what a review is about as heavily as how the reviewer feels:
  - topic words: gift, mail, time, recipient, credit (17, 51, 63, the joy→anticipation eight);
  - word sense ignored: hit (32), fits (93);
  - idiom and sarcasm read literally: Bronx cheer (51);
  - negation not handled: 6 real negations scored as affirmed (e.g. 64, 46);
  - coverage gaps: easy, emoji, and the missed stem "loved" (17).
- **The LLM reads whole reviews but has its own biases:**
  - joy for 80 of 100 reviews;
  - an implausible disgust (46);
  - trust labels that follow the prompt's gloss for "convenient".
- **Caveat:** batch_100 is 93% positive, so these rates mostly describe positive reviews. Step 6 repeats the comparison on the balanced sample.
