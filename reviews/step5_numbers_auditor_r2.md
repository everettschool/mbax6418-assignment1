# Step 5 — Numbers Auditor, round 2

Script: `reviews/step5_numbers_auditor_r2/audit_step5_r2.py`. It imports nothing from `src/`. It has its own NRC implementation of the documented method, its own reply parser and its own metrics, and it reads the dashboard DOM with Playwright headless Chromium. Full output: `reviews/step5_numbers_auditor_r2/audit_output.txt`. verify_leak output: `reviews/step5_numbers_auditor_r2/verify_leak_output.txt`.

Command: `.venv/bin/python reviews/step5_numbers_auditor_r2/audit_step5_r2.py` (exit 1, 3 FAILs). Condensed output:

```
== 1. lexicon       sha256 02c66154…535a OK; zip sha256 4edcbd00…34e6 OK; word_count 14154 OK;
                    words_with_any_of_8_emotions 4454 OK; columns_found OK
== 2. per-row       mismatches in truth, prediction, llm_emotion (v1+v2, re-parsed from raw_responses),
                    nrc_emotion, nrc_tied, nrc_scores, nrc_hits, nrc_token_count, nrc_emotion_tiebreak,
                    nrc_negated_hits, emotion_agree: {}
== 3. metrics       first100_v1/metrics.json: 62 leaves, 0 mismatches
                    first100_v2/metrics.json: 62 leaves, 0 mismatches
                    first100_v2/emotion_metrics.json: 191 leaves, 0 mismatches (4 prose leaves skipped:
                      method, constant_baseline_note, tiebreak_rule, negation.rule); no leaf NOT RECOMPUTED
                    api_call_count + cache_hits = 100, from_cache rows = 10 OK; v1 vs v2 sentiment flips: []
== 4. dashboard     embedded payload == files for metrics, emotion_metrics and row projections (both runs)
  -- tab first100_v1   60 visible data-raw numbers (47 metrics.json, 13 run_meta.json): 0 failures
                       (data-raw == file == recomputation; data-metric == source field; format; text)
                       14 visible marks: 0 failures; emotion section hidden
  -- tab first100_v2   189 visible data-raw numbers (129 emotion_metrics.json, 47 metrics.json, 13 run_meta): 0 failures
                       115 visible marks (llm bars 5, nrc bars 6, cross-tab 90): 0 failures
                         (data-value == file == recomputation; labels; bar width% = 100·v/max; no collapsed mark)
                       cross-tab DOM order rows=LLM, cols=NRC OK; headers all 1 line box, no overflow
                         (anticip. with title "anticipation")
                       tiles: 20.0% 20 of 100 | 23.5% 20 of 85 | 52.6% 20 of 38
                       context: "…“joy” … 22.0% … (22 of 100) and on 57.9% … (22 of 38). … tied on 47 …
                                 among the tied ones in 45, and “joy” alone … in 45 …"
                       review table 100 rows: data-emo and emotion cells == recomputation
                       f-emo agree/differ/tie/none/all: live count == text == visible rows == 20/18/47/15/100
                     untagged visible digit text: labels/paths only ("MBAX 6418", "First 100", "4–5★",
                       "Macro F1", "Prompt sha256", file paths) and the live row count "100"
                     console/page errors: []; non-file requests: []
== 5. written claims (step5_analysis.md, ISSUES.md, PROGRESS.md) all OK:
     agreement 20/100 20.0%, 20/85 23.5%, 20/38 52.6%; constant joy 22/100 22.0%, 22/85 25.9%, 22/38 57.9%;
     −2.0 pts / −5.3 pts; non-joy 1/20 5.0%, 1/11 9.1%; TIE 47 / LLM-in-tie 45 / joy-in-tie 45 / NONE 15;
     tie-break 23/100 23.0%, 23/85 27.1%; duplicates ids 20–28 all TIE; unique 93/20/40/15;
     LLM and NRC counts; anger ids 4,15,32,51,63,91 NEGATIVE + 17 (5★); all 16 non-zero cross-tab cells;
     18 divergent; scores and hit lists for 51, 32, 63 (subset), 17 (complete list now matches), 46;
     joy→anticipation ids 9,16,41,42,70,71,93,95, deciding words mail/recipient/time/store, removal ends sole win
     in all 8; 95 store ×2; 9 only mail; 93 fits→anger; NONE "easy" ids 31,49,55,67,68,78,97,98;
     NONE by LLM joy 9/trust 5/anger 1; gift 104 hits / 40 in ties; good 29 in ties; tied sets 15/14/13;
     8 gift-only; negation 15 hits / 11 rows; trust "easy…" ids 14,31,34,49,55,56,78,97, NONE 31,49,55,78,97;
     errors 17,46,98; lexicon 14,154/4,454; API calls 199 == cache/api_calls_total.json
FAIL PROGRESS 'verify_dashboard.py PASS N checks' == step5_verify_dashboard.txt: expected='1342' got='1309'
FAIL ISSUES.md contains stale 'agreement advantage' wording: expected=False got=True
FAIL PROGRESS 'Current step' still says 'fixing findings': expected=False got=True
TOTAL FAILS: 3
```

Checker fix made during this audit: the first run reported 5 "data-format" failures that came from my own checker, not from the page. `JSON.stringify(0.0)` gives `"0"`, so my checker saw the UNPARSED shares as counts; and `temperature`/`seed` are run settings, which may be shown as text. The expected format is now taken from the file value's type. After that fix, the page has 0 failures.

`.venv/bin/python src/verify_leak.py` (exit 0):
```
PASS runs/first100_v1/predictions.jsonl: 100 rows, prompt prompts/sentiment_v1.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
PASS runs/first100_v2/predictions.jsonl: 100 rows, prompt prompts/sentiment_v2.txt; 4 rows had a star-phrase title/text blanked; 0 reviews use a forbidden word in their own sent title/text (customer's words, allowed)
```

Round-1 BLOCKER (review 17 hit list): fixed. The stored and recomputed hit multiset equals the list in the analysis, and the arithmetic holds: anticipation 9 = gift 3 + pretty 1 + recipient 2 + time 2 + mail 1; joy 4; trust 2.

## Findings

BLOCKER — ISSUES.md line 73, "[Step 5] LLM emotion has its own failures" — The entry says the LLM has an agreement advantage, but the saved numbers show it has none. The LLM agrees with the word list less often than a constant "joy" answer does. This sentence was left over from round 1 and contradicts the corrected finding on line 59 and the analysis. — Evidence: quoted "The LLM also answered joy for 80 of 100 reviews, so its agreement advantage partly reflects a skewed batch." `emotion_metrics.json`: `agreement_rate_all_rows` 0.2 vs `constant_baseline_rate_all_rows` 0.22; `llm_minus_constant_rate_all_rows` −0.02 (−2.0 pts); `llm_minus_constant_rate_excluding_none_and_tie` −0.0526 (−5.3 pts). Script: `FAIL ISSUES.md contains stale 'agreement advantage' wording: expected=False got=True`. — Suggested fix: replace it with, for example, "The LLM also answered joy for 80 of 100 reviews; its agreement with the word list (20/100) is below a constant 'joy' answer (22/100)."

BLOCKER — PROGRESS.md line 51, "Step 5 status" — The check count quoted for verify_dashboard does not match the saved log. — Evidence: quoted "`verify_dashboard.py` PASS 1,309 checks (`reviews/step5_verify_dashboard.txt`)". The file's last lines read "1342 checks, 0 failures / PASS". Script: `FAIL PROGRESS 'verify_dashboard.py PASS N checks' == step5_verify_dashboard.txt: expected='1342' got='1309'`. — Suggested fix: change it to "1,342 checks", or re-run `src/verify_dashboard.py` and quote whatever the saved file then says.

MINOR — PROGRESS.md lines 6, 44–52 ("Current step", "Open reviewer findings", "Step 5 status") — PROGRESS.md still describes round 1 as open, while ISSUES.md line 60 says all round-1 findings are fixed. The file calls itself the source of truth after compaction. — Evidence: quoted "Step 5 — Primary emotion, two ways (reviewer round 1 done; fixing findings)", "Step 5 round 1 (…), all being fixed:", "Remaining: verify analysis claims (…), view emotion screenshot, Grader + Numbers Auditor, fix, record gate, commit." Script: `FAIL PROGRESS 'Current step' still says 'fixing findings'`. — Suggested fix: move the round-1 findings to resolved, set the current step to "reviewer round 2", and update "Remaining".

MINOR — reviews/step5_analysis.md line 97 ("Most are rhetorical, where reversing would be wrong") and ISSUES.md line 65 ("15 hits in 11 reviews, mostly rhetorical 'who doesn't love'") — The count does not support "most". Only 5 of the 15 negated hits come from a rhetorical "who doesn't/wouldn't love" or "what is not to love" phrase, and real negations (6) outnumber them. — Evidence: the script prints each negated hit with its context. Rhetorical (5): 3 "who doesn t love" (love) and "doesn t love shopping" (shopping); 57 "who wouldn t love" (love) and "t love this wonderful" (wonderful); 76 "is not to love" (love). Real negation scored as affirmed (6): 4 "t able to cover" (cover), 46 "nothing to show" (show), 64 "nothing is good enough" (good), 76 "no service fee" (fee), 91 "without the fees" (fees), 95 "t have to leave" (leave). Negator does not apply to the hit word (4): 1 "never too late" (late), 4 "not gift cards" (title "Not $10 Gift Cards"), 63 "not as gift card", 90 "not necessary i recommend" (recommend). — Suggested fix: state the split, for example "5 of the 15 are rhetorical (3, 57, 76), 6 are real negations scored as affirmed (4, 46, 64, 76, 91, 95), and in 4 the negator does not apply to the hit word", and drop "most/mostly".

MINOR — ISSUES.md line 72 item (b) — The emotion tags for "cheer" are incomplete. — Evidence: quoted "'A Bronx cheer for you!' → cheer = joy/trust (review 51)". In the lexicon (and in the analysis, line 47), cheer is tagged anticipation, joy, surprise and trust. Script: `OK 51 cheer tags …: ['anticipation', 'joy', 'surprise', 'trust']`. Anticipation is the emotion that wins review 51 (anticipation 3). — Suggested fix: "cheer = anticipation/joy/surprise/trust".
