# Step 5 — Numbers Auditor

Script: `reviews/step5_numbers_auditor/audit_step5.py` (imports nothing from `src/`; own NRC implementation of the documented method, own sentiment/emotion parser, own metrics, Playwright headless Chromium for the DOM).
Full output: `reviews/step5_numbers_auditor/audit_step5_output.txt`. verify_leak output: `reviews/step5_numbers_auditor/verify_leak_output.txt`.

Command: `.venv/bin/python reviews/step5_numbers_auditor/audit_step5.py` (exit 0). Condensed output below; the file above has every OK line.

```
== 1. lexicon                      sha256, word_count 14154, words_with_any_of_8_emotions 4454: all OK
== 2. per-row NRC + LLM emotion    per-row field mismatches (stored vs independent): {} (nrc_emotion, nrc_tied,
                                   nrc_scores, nrc_hits, nrc_token_count, emotion_agree, llm_emotion, prediction)
== 3. metrics recomputation
     v1 metrics.json: 62 leaves compared, 0 mismatches
     v2 metrics.json: 62 leaves compared, 0 mismatches
     v2 emotion_metrics.json: 158 leaves compared, 0 mismatches
== 4. v1 vs v2                     0 sentiment predictions differ; misclassified {'POSITIVE->NEGATIVE': [17, 46],
                                   'NEGATIVE->POSITIVE': [98]} in both; cache hits 10, api calls 90; 4 star-phrase rows blanked: OK
== 5. dashboard DOM (headless Chromium)  page shell == template.html; embedded data == files: OK
  -- tab first100_v1
     60 visible tagged numbers, 0 with a failure
     14 visible chart marks, 0 with a failure; emotion section hidden: OK
  -- tab first100_v2
     178 visible tagged numbers, 0 with a failure (118 from runs/first100_v2/emotion_metrics.json)
     115 visible chart marks, 0 with a failure (llm bars 5, nrc bars 6, crosstab cells 90)
     emotion bar width error max 0.0042; min bar width px 2.0
     cross-tab DOM order / row+column headers / cell labels: OK (rows = LLM, columns = NRC)
     emotion tiles: 20.0% | 20 of 100 · 23.5% | 20 of 85 · 52.6% | 20 of 38
     review table emotion cells vs recomputation: (100, []) OK
     f-emo agree/differ/tie/none/all live counts == visible rows == recomputed (20/18/47/15/100): OK
     untagged visible digit text: only labels/paths ("MBAX 6418", "First 100", "4–5★", "Macro F1",
       "Prompt sha256", file paths) and the live row count "100"; no untagged metric numbers
     console/page errors: [] · non-file requests: []
== 6. written claims (step5_analysis.md, ISSUES.md)
     all agreement rates, TIE 47 / NONE 15 / 62, 45 of 47 (95.7%), LLM and NRC counts, all 16 non-zero
     cross-tab cells, 18 divergent, scores for reviews 51/32/63/17/46/93, 8 "easy" NONE rows, NONE column
     joy 9/trust 5/anger 1, gift 104 hits / 40 in ties, good 29 in ties, tied sets 15/14/13, 8 gift-only
     reviews, lexicon tags for hit/fits/credit/cheer, great/easy/works absent: OK
     17 hits: {gift x3 (ant,joy,sur), pretty x1 (ant,joy,trust), recipient x2 (ant), complaint (anger),
               time, times->time (ant), showed->show (trust), mail (ant)}
FAIL claim: 17 hits exactly = claimed list 'gift x3, recipient x2, time, times->time, mail; complaint':
     expected=['complaint','gift','gift','gift','mail','recipient','recipient','time','time']
     got=['complaint','gift','gift','gift','mail','pretty','recipient','recipient','show','time','time']
FAIL claim: 17 anticipation from claimed topic words only (gift3+recipient2+time2+mail1): expected=9 got=8

TOTAL FAILS: 2
```

`.venv/bin/python src/verify_leak.py` (exit 0):
```
PASS runs/first100_v1/predictions.jsonl: 100 rows, prompt prompts/sentiment_v1.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v2/predictions.jsonl: 100 rows, prompt prompts/sentiment_v2.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
```

## Findings

BLOCKER — `reviews/step5_analysis.md`, divergent review 4 (review_id 17) — The hit list and the "outvoted 9 to 1 by topic words" arithmetic do not match the saved row. The list leaves out two hits: `pretty` (anticipation, joy, trust) and `showed → show` (trust). The topic words it names give only 8 of the 9 anticipation points; the ninth comes from "pretty", which is an evaluative word, not a topic word. The omission also leaves joy 4 (gift ×3 + pretty) and trust 2 (pretty + show) unexplained by the listed hits. — Evidence: quoted text "Hits: gift ×3, recipient ×2, time, times → time, mail (all anticipation); complaint (anger)." and "The one anger word, "complaint", is outvoted 9 to 1 by topic words." Stored and recomputed `nrc_hits` for review 17: `gift, pretty, gift, recipient, complaint, time, recipient, gift, times→time, showed→show, mail`, scores `anticipation 9, joy 4, surprise 3, trust 2, anger 1`. Script output: `FAIL claim: 17 anticipation from claimed topic words only (gift3+recipient2+time2+mail1): expected=9 got=8`. — Suggested fix: list every hit, "gift ×3 (anticipation, joy, surprise); pretty (anticipation, joy, trust); recipient ×2, time, times → time, mail (anticipation); showed → show (trust); complaint (anger)". Rephrase the conclusion as "outvoted 9 to 1 on anticipation, 8 of those points from topic words (gift, recipient, time, mail) and 1 from 'pretty'".
