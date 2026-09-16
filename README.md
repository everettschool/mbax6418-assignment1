# Sentiment & emotion classification of Amazon gift-card reviews

MBAX 6418, Assignment 1. An LLM classifies Amazon "Gift Cards" reviews from their title and text alone, the star rating is used only as the answer key, and everything is presented in one self-contained dashboard.

Every number below is cited as **value** (run: field) and read from a committed file. `src/check_readme_numbers.py` re-checks each citation against those files.

## What was built and how to run it

| Piece | File |
|---|---|
| Prompts (v1 binary, v2 + emotion, v3 three-class) | `prompts/sentiment_v1.txt`, `v2`, `v3` |
| Classifier: prompt building, cache, retries, parser | `src/classify.py` |
| Scoring | `src/score.py`, cross-run numbers `src/compare_runs.py` |
| Word-list emotions | `src/get_nrc.py`, `src/nrc_emotion.py` |
| Dashboard generator and page | `src/build_dashboard.py`, `dashboard/template.html` → `dashboard/index.html` |
| Checks | `src/verify_leak.py` (rating never sent), `src/verify_dashboard.py` (browser), `src/test_classify.py`, `src/check_readme_numbers.py` |
| Raw output | `runs/<run>/predictions.jsonl`, `metrics.json`, `emotion_metrics.json`, `run_meta.json` |

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/playwright install chromium
cp .env.example .env            # fill in OPENAI_BASE_URL, OPENAI_API_KEY, MODEL_NAME
.venv/bin/python src/classify.py --prompt prompts/sentiment_v3.txt --selection balanced_150 --run balanced150_v3
.venv/bin/python src/score.py runs/balanced150_v3 && .venv/bin/python src/nrc_emotion.py runs/balanced150_v3
.venv/bin/python src/build_dashboard.py && open dashboard/index.html
```

Open `dashboard/index.html` in a browser: no server, no network. The run tabs switch between the four runs; the review table filters by result, class, emotion agreement and free text, with a live count.

## Data source

- **Amazon Reviews '23**, McAuley Lab, UC San Diego — dataset page: https://amazon-reviews-2023.github.io
- File used: `Gift_Cards.jsonl.gz` — https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/Gift_Cards.jsonl.gz (152,410 reviews; sha256 `e03a258e…c2340`, recorded in every `run_meta.json`). Not committed: it is large and re-downloadable.
- **NRC Emotion Lexicon (EmoLex) v0.92** — Saif M. Mohammad and Peter D. Turney, *Crowdsourcing a Word-Emotion Association Lexicon*, Computational Intelligence 29(3), 436–465, 2013. Home page: https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm. Its terms allow free non-commercial research and educational use, require citing the papers, and **forbid redistribution**, so the lexicon is not committed; `src/get_nrc.py` downloads it and records its hashes in `runs/nrc_lexicon_meta.json`.

## Method

- **Model:** `cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit` through the course OpenAI-compatible endpoint, **temperature 0**, thinking disabled, `max_tokens` small, replies parsed from a single `LABEL=…;EMOTION=…` line. 442 API calls in total.
- **Prompts:** v1 decides POSITIVE/NEGATIVE from title and text with written rules for conflicting titles, mixed reviews, sarcasm and non-English text; v2 adds one primary emotion from the eight NRC emotions; v3 moves to POSITIVE/NEUTRAL/NEGATIVE with a NEUTRAL definition that never mentions stars. Each version is a new, immutable file.
- **The model never sees the rating.** `build_messages(title, text)` is the only place messages are built, every sent message is stored, and `src/verify_leak.py` re-derives them and fails on any leak. Amazon's auto-filled titles ("Five Stars") are the rating in disguise, so they are blanked: 26 of the 150 balanced reviews.
- **Samples:** `batch_100` = review_ids 0–99. `balanced150_v3` = 50 reviews per class drawn with **seed 42** from the whole file; the ids are saved in `runs/balanced150_v3/sample_ids.json`, so reproduction reads ids rather than redrawing.
- **Word-list emotions:** lowercase tokens of the same title and text, a documented s/es/ed/ing fallback, counts summed over the eight emotions only (positive/negative columns excluded), argmax, ties → TIE, no hits → NONE.
- **Reproducibility caveat:** temperature 0 on this endpoint is **not** fully deterministic. One review (4880) was re-sent with identical messages and answered differently. The published numbers are reproduced from the committed predictions, not guaranteed by re-querying.

## Results

![Headline, balanced run](dashboard/screenshots/fold_balanced150_v3.png)

| Run | Accuracy | Baseline | Balanced accuracy |
|---|---|---|---|
| `first100_v1` (binary, first 100) | **97.0%** (first100_v1: accuracy) | **93.0%** (first100_v1: majority_baseline_accuracy) | **91.8%** (first100_v1: balanced_accuracy) |
| `first100_v3` (three classes, first 100) | **95.0%** (first100_v3: accuracy) | **93.0%** (first100_v3: majority_baseline_accuracy) | **65.6%** (first100_v3: balanced_accuracy) |
| `balanced150_v3` (three classes, balanced) | **73.3%** (balanced150_v3: accuracy) | **33.3%** (balanced150_v3: majority_baseline_accuracy) | **73.3%** (balanced150_v3: balanced_accuracy) |

![Stars in the file vs the sample, and answers per class](dashboard/screenshots/stars_and_answers_balanced150_v3.png)
![Confusion matrix](dashboard/screenshots/confusion_matrix_balanced150_v3.png)
![Right answers by class](dashboard/screenshots/right_answers_by_class_balanced150_v3.png)
![Emotion, two ways](dashboard/screenshots/emotion_two_ways_balanced150_v3.png)
![Filtered review table](dashboard/screenshots/review_table_filtered_neutral_to_negative.png)

## Q1. Why did the lopsided run look accurate, and what did balanced sampling change?

The first 100 reviews are almost all positive (93 /100). Someone who ignores the text and answers "positive" every single time already scores 93%. My model got 97%, which sounds good until you realize it is only four reviews better than doing nothing at all. The gap is not even big enough to call real: the model wins 6 reviews the shortcut loses, and loses 2 that the shortcut wins, which comes out to p = 0.29.

Sampling 50 reviews from each class dropped accuracy to 73.3%, against a 33.3% baseline because the test got harder. If I take the per-class hit rates from the balanced run and apply them back to the lopsided mix, I get 94.5%, which is basically the 95% I actually measured on that batch. The first batch hid the middle class the most. It contained 2 neutral reviews, so there was nothing there to measure. With 50 of them, the model only gets 34% right.

## Q2. Where do the mistakes go?

Of the 50 three-star reviews, my model called 17 neutral, 25 negative and 8 positive. Going the other direction barely happens: only 4 of the one and two-star reviews were called neutral, and 2 of the four and five-star ones. It almost never flips a review.

Three-star reviews get pulled toward negative a lot more than negative reviews drift toward neutral. That is about half of them, even though with only 50 reviews in the class the true rate has a wide range so I can't claim it is a majority. I read all 25 of those reviews. Seventeen were flat complaints and my prompt tells the model to call exactly those negative. Only about eight are genuinely mixed. So that cell is mostly my own prompt's rules disagreeing with people who complained and still gave three stars, not the model misreading the words. One caveat on precision: neutral precision looks like 73.9% here, but that number only exists because I forced the classes to be equal whereas weighted to the file's real mix, it would be closer to 14.5%.

## Q3. How do the LLM's emotions and the word list's differ, and why?

They barely agree. On the balanced run the two pick the same emotion for 10.7% of reviews. That is worse than it sounds: answering "anticipation" for every review matches the word list 14.7% of the time, so the model is about 4 points behind saying one word over and over.

The reason shows up as soon as I read the rows. The word list only counts words, so it ends up scoring what a review is about rather than how the writer feels. "Gift" is itself tagged anticipation, joy and surprise, and it turns up 104 times in the first batch, which is why the list ties on 67 reviews and finds nothing at all on 24. It has no sense of context either: "hit button by mistake" registers as anger, "a Bronx cheer for you" comes out joy and trust, negation goes straight past it, and it misses "loved" because chopping off the "-ed" leaves "lov". The model reads the whole review, but it has its own habit. It answered joy for 80 of the first 100 reviews, and called a review titled "love it!!" disgust.

### Where these numbers come from

Every figure above is read from a saved file; `python src/check_readme_numbers.py` re-checks each one.

| | |
|---|---|
| First batch, positive reviews | **93** (first100_v1: truth_distribution.counts.POSITIVE) |
| Always-"positive" baseline | **93.0%** (first100_v1: majority_baseline_accuracy) |
| Binary accuracy | **97.0%** (first100_v1: accuracy) |
| Model-only-right / shortcut-only-right | **6** (comparisons: first100_v1_vs_majority_model_only_right) / **2** (comparisons: first100_v1_vs_majority_shortcut_only_right) |
| Balanced accuracy / baseline | **73.3%** (balanced150_v3: accuracy) / **33.3%** (balanced150_v3: majority_baseline_accuracy) |
| Predicted from balanced hit rates | **94.5%** (comparisons: first100_v3_accuracy_expected_from_balanced150_v3_recalls) |
| Three-class accuracy, first batch | **95.0%** (first100_v3: accuracy) |
| First batch, neutral reviews | **2** (first100_v3: per_class.NEUTRAL.support) |
| Neutral recall, balanced | **34.0%** (balanced150_v3: per_class.NEUTRAL.recall) |
| 3★ called neutral / negative / positive | **17** (balanced150_v3: confusion_cells.NEUTRAL->NEUTRAL) / **25** (balanced150_v3: confusion_cells.NEUTRAL->NEGATIVE) / **8** (balanced150_v3: confusion_cells.NEUTRAL->POSITIVE) |
| 1–2★ called neutral | **4** (balanced150_v3: confusion_cells.NEGATIVE->NEUTRAL) |
| 4–5★ called neutral | **2** (balanced150_v3: confusion_cells.POSITIVE->NEUTRAL) |
| 3★ called negative ("about half") | **50.0%** (comparisons: balanced150_v3_neutral_to_negative_share), 95% range **36.6%** (comparisons: balanced150_v3_neutral_to_negative_share_wilson95.0) to **63.4%** (comparisons: balanced150_v3_neutral_to_negative_share_wilson95.1) |
| Neutral precision, balanced / re-weighted | **73.9%** (balanced150_v3: per_class.NEUTRAL.precision) / **14.5%** (comparisons: balanced150_v3_population_weighted_precision.NEUTRAL) |
| Emotion agreement, balanced run | **10.7%** (balanced150_v3 emotions: agreement_rate_all_rows) |
| Best constant emotion / model's gap to it | **14.7%** (comparisons: balanced150_v3_emotion_best_constant_all_rows) / **−4.0 pts** (comparisons: balanced150_v3_emotion_llm_minus_best_constant_all_rows) |
| Word list ties / no hits | **67** (balanced150_v3 emotions: tie_rows) / **24** (balanced150_v3 emotions: none_rows) |

## Q4. What bugs and issues came up?

Full log with evidence in [ISSUES.md](ISSUES.md). The ones that changed results:

- **The rating leaked through the title.** 31,868 titles are Amazon's auto-filled "Five Stars"; `build_messages` now blanks them, and `verify_leak.py` fails if one is ever sent. Two reviews mention stars in their own words, which is disclosed rather than rewritten.
- **The model returned nothing at first.** It is a thinking model and spent the whole token budget on hidden reasoning; disabling thinking fixed it.
- **Silent rendering bugs the number checks missed:** `[object HTMLSpanElement]`, a literal "null", and bars drawn at the wrong length. Each was found by reading the rendered page, and each is now a check in `verify_dashboard.py`, proven by mutation tests.
- **Claims I had to withdraw** after review: that two Step 2 errors were prompt-rule gaps; that ties explained low emotion agreement; that 3★ reviews "mostly collapse"; that "at most 3" of the 25 were instruction failures. Each is corrected in ISSUES.md with the evidence.
- **Not fully reproducible by re-querying:** see the temperature-0 caveat above.
- **Sample quirks:** the balanced positive class drew **0** (balanced150_v3: sample_rating_counts.4) four-star reviews, and the first batch contains 7 duplicate "Good Product" rows.

### From the student: working with the agent

Working with an AI agent on the assignment was a very interesting experience. As much as it helped me do the bulk of the work, it has some limitations. For example, having a strong prompt can be a double-edged sword. I invested ample time into fleshing out an intricate prompt, but it came back to haunt me when the output took over 3 hours. I burnt through a ridiculous number of tokens because I was recruiting sub-agents with specific tasks. What originally was implemented as a safeguard against creating an echo-chamber, and an objective 2nd look at my assignment's progress, became a heavy token-consuming beast that nearly maxed out my usage limits and context window. On the positive end, having these protections in place caught multiple issues with the dashboard's layout and how the agent interpreted unique review situations. When I realized how long the assignment was taking the agent, I injected a few new prompts to speed up the remaining steps without hindering output quality. In the future, I won't overcomplicate my initial project prompt because although rewriting prompts can be annoying, it probably saves me time in the long-run when compared to getting everything perfect on the first prompt. The agent made a few claims that it later withdrew, and these mistakes still occur whether a prompt has been refined or not. For example, it claimed that 3-star reviews mostly collapsed into negative, then withdrew that when the data showed it was exactly half. All-in-all, I found that creating specific folders designed to report progress, issues, and changes enables a level of transparency that would go unseen if not.

## Reproduction

```bash
.venv/bin/python src/rating_distribution.py                 # whole-file star distribution
.venv/bin/python src/get_nrc.py                             # NRC lexicon into data/ (not committed)
.venv/bin/python src/classify.py --prompt prompts/sentiment_v3.txt --selection balanced_150 --run balanced150_v3
.venv/bin/python src/score.py runs/*/ && .venv/bin/python src/compare_runs.py
.venv/bin/python src/verify_leak.py                         # rating never reached the model
.venv/bin/python src/build_dashboard.py && .venv/bin/python src/verify_dashboard.py
.venv/bin/python src/check_readme_numbers.py                # every number in this README
```

Replies are cached in `cache/` by (model, prompt, title, text), so a re-run costs nothing for rows already answered. To check the headline numbers yourself:

```bash
python3 -c "import json;m=json.load(open('runs/balanced150_v3/metrics.json'));print(m['accuracy'],m['majority_baseline_accuracy'],m['per_class']['NEUTRAL']['recall'])"
python3 -c "import json;print(json.load(open('runs/balanced150_v3/metrics.json'))['confusion_cells'])"
python3 -c "import json;print(json.load(open('runs/balanced150_v3/emotion_metrics.json'))['agreement'])"
```
