"""Word-list primary emotion from the NRC Emotion Lexicon (EmoLex). No model calls.

Method (documented so the result can be reproduced by hand):
  1. Text = title + " " + text, using the same blanking the model got (a title or text
     that is only "<One–Five> Star(s)" is blanked), so both methods read the same words.
     HTML line breaks and entities are decoded first ("<br />" -> space, "&#34;" -> '"').
  2. Tokens = lowercase alphabetic runs: re.findall(r"[a-z]+", text.lower()).
     "don't" -> "don", "t".
  3. Lemmatization fallback: use the token if it is a lexicon word with at least one of the
     8 emotions; otherwise strip the first of the suffixes "ing", "ed", "es", "s" (tried in
     that order) whose remaining stem is such a word; otherwise the token has no hits.
     (Lexicon words tagged only positive/negative, or with no tags, do not count.)
  4. Every token occurrence adds 1 to each of its word's emotions. Only the 8 emotions
     count; the lexicon's "positive" and "negative" sentiment columns are excluded.
  5. Primary emotion = the emotion with the highest total. Several share the highest
     total -> "TIE" (tied emotions listed). All totals zero -> "NONE".

Adds to every row of predictions.jsonl: nrc_emotion, nrc_tied, nrc_scores, nrc_hits,
nrc_token_count, emotion_agree (llm_emotion == nrc_emotion; TIE/NONE never agree),
nrc_emotion_tiebreak (ties broken by the fixed EMOTIONS order, a literal "take the highest"
alternative, reported separately), nrc_negated_hits (hits right after a negator; counted only).
Writes runs/<run>/emotion_metrics.json, including a constant-answer skew baseline (always the
LLM's most common emotion), agreement on unique title+text rows, and tie-break agreement.

Usage: python src/nrc_emotion.py runs/first100_v2 [runs/... ...]
"""
import hashlib
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classify as cl  # noqa: E402

ROOT = cl.ROOT
LEXICON = ROOT / "data" / "nrc" / "NRC-Emotion-Lexicon-Wordlevel.txt"
LEXICON_META = ROOT / "runs" / "nrc_lexicon_meta.json"
EMOTIONS = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]
EXCLUDED_COLUMNS = {"positive", "negative"}
SUFFIXES = ["ing", "ed", "es", "s"]
TOKEN = re.compile(r"[a-z]+")
# Reported only (the method does not reverse them): a hit within 3 tokens after one of these.
NEGATORS = {"not", "no", "never", "nothing", "none", "nor", "without", "t"}  # "t" = don't/isn't/wasn't

assert EMOTIONS == cl.EMOTIONS, "word-list and LLM emotion sets must be identical"
assert not EXCLUDED_COLUMNS & set(EMOTIONS), "sentiment columns must not be counted as emotions"


def load_lexicon():
    raw = LEXICON.read_bytes()
    meta = json.loads(LEXICON_META.read_text())
    if hashlib.sha256(raw).hexdigest() != meta["lexicon_sha256"]:
        raise SystemExit("lexicon file does not match runs/nrc_lexicon_meta.json; re-run src/get_nrc.py")
    lexicon = {}
    for line in raw.decode("utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) != 3 or parts[2] not in ("0", "1"):
            continue
        word, column, flag = parts
        lexicon.setdefault(word, set())
        if flag == "1" and column in EMOTIONS:
            lexicon[word].add(column)
    lexicon = {w: e for w, e in lexicon.items() if e}
    assert all(e <= set(EMOTIONS) for e in lexicon.values()), "only the 8 emotions may be counted"
    return lexicon, meta


def lookup(token, lexicon):
    if token in lexicon:
        return token
    for suffix in SUFFIXES:
        if token.endswith(suffix) and token[: -len(suffix)] in lexicon:
            return token[: -len(suffix)]
    return None


def clean(s):
    return html.unescape(re.sub(r"<br\s*/?>", " ", s, flags=re.IGNORECASE))


def score_text(title, text, lexicon):
    words = clean(cl.model_title(title) + " " + cl.model_text(text)).lower()
    tokens = TOKEN.findall(words)
    scores = {e: 0 for e in EMOTIONS}
    hits, negated = [], []
    for i, tok in enumerate(tokens):
        entry = lookup(tok, lexicon)
        if entry is None:
            continue
        emotions = sorted(lexicon[entry])
        for e in emotions:
            scores[e] += 1
        hits.append([tok, entry, emotions])
        before = [t for t in tokens[max(0, i - 3):i] if t in NEGATORS]
        if before:
            negated.append([before[-1], tok])
    top = max(scores.values())
    tied = [e for e in EMOTIONS if scores[e] == top] if top else []
    if top == 0:
        label = "NONE"
    elif len(tied) > 1:
        label = "TIE"
    else:
        label = tied[0]
    return {"nrc_emotion": label, "nrc_tied": tied if label == "TIE" else [], "nrc_scores": scores,
            "nrc_hits": hits, "nrc_token_count": len(tokens),
            # Literal "take the highest" alternative: ties broken by the fixed emotion order above.
            "nrc_emotion_tiebreak": tied[0] if label == "TIE" else label,
            "nrc_negated_hits": negated}


def rate(agree, n):
    return agree / n if n else None


def emotion_metrics(run, rows, lex_meta):
    llm_cols = EMOTIONS + ["UNPARSED"]
    nrc_cols = EMOTIONS + ["TIE", "NONE"]
    crosstab = {a: {b: 0 for b in nrc_cols} for a in llm_cols}
    for r in rows:
        crosstab[r["llm_emotion"] or "UNPARSED"][r["nrc_emotion"]] += 1

    def subset(keep):
        sub = [r for r in rows if keep(r)]
        agree = sum(r["emotion_agree"] for r in sub)
        return {"n": len(sub), "agree": agree, "rate": rate(agree, len(sub))}

    all_rows = subset(lambda r: True)
    excl_none = subset(lambda r: r["nrc_emotion"] != "NONE")
    excl_none_tie = subset(lambda r: r["nrc_emotion"] not in ("NONE", "TIE"))
    ties = [r for r in rows if r["nrc_emotion"] == "TIE"]
    llm_in_tie = sum(r["llm_emotion"] in r["nrc_tied"] for r in ties)
    llm_counts = Counter(r["llm_emotion"] or "UNPARSED" for r in rows)
    nrc_counts = Counter(r["nrc_emotion"] for r in rows)
    n = len(rows)

    # Skew baseline: a constant answer equal to the LLM's most common emotion.
    constant = max(EMOTIONS, key=lambda e: (llm_counts.get(e, 0), -EMOTIONS.index(e)))

    def const_subset(keep):
        sub = [r for r in rows if keep(r)]
        agree = sum(r["nrc_emotion"] == constant for r in sub)
        return {"n": len(sub), "agree": agree, "rate": rate(agree, len(sub))}

    const_all = const_subset(lambda r: True)
    const_excl_none = const_subset(lambda r: r["nrc_emotion"] != "NONE")
    const_excl_none_tie = const_subset(lambda r: r["nrc_emotion"] not in ("NONE", "TIE"))
    non_majority = subset(lambda r: r["llm_emotion"] != constant)
    non_majority_single = subset(lambda r: r["llm_emotion"] != constant and r["nrc_emotion"] not in ("NONE", "TIE"))
    tb_agree = sum(r["llm_emotion"] is not None and r["llm_emotion"] == r["nrc_emotion_tiebreak"] for r in rows)
    tb_rows = [r for r in rows if r["nrc_emotion"] != "NONE"]
    tb_agree_excl_none = sum(r["llm_emotion"] == r["nrc_emotion_tiebreak"] for r in tb_rows)
    seen, unique = set(), []
    for r in rows:
        key = (r["title"], r["text"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    negated_rows = [r for r in rows if r["nrc_negated_hits"]]
    # Baselines under the tie-break variant: the fixed order decides where ties go.
    tb_counts = Counter(r["nrc_emotion_tiebreak"] for r in rows)

    def tb_const(emotion):
        agree = sum(r["nrc_emotion_tiebreak"] == emotion for r in rows)
        return {"emotion": emotion, "agree": agree, "rate": rate(agree, n)}

    best_tb = max(EMOTIONS, key=lambda e: (tb_counts.get(e, 0), -EMOTIONS.index(e)))
    # Strongest constant: the single emotion that agrees most with the word list (its most
    # common single answer). A constant equal to the LLM's favourite can be a weak bar.
    best = max(EMOTIONS, key=lambda e: (nrc_counts.get(e, 0), -EMOTIONS.index(e)))
    best_hits = nrc_counts.get(best, 0)

    def best_subset(sub_n):
        return {"n": sub_n, "agree": best_hits, "rate": rate(best_hits, sub_n)}

    best_all, best_excl_none, best_excl_none_tie = (best_subset(n), best_subset(excl_none["n"]),
                                                    best_subset(excl_none_tie["n"]))
    return {
        "run": run,
        "lexicon": {k: lex_meta.get(k) for k in ("source", "download_url", "lexicon_sha256", "word_count",
                                                  "words_with_any_of_8_emotions", "citation")},
        "method": ("NRC: lowercase alphabetic tokens of title + text (same star-phrase blanking as the model); "
                   "fallback strips ing/ed/es/s if the stem is a lexicon word with >=1 of the 8 emotions; sum per emotion over the 8 "
                   "emotions only; argmax; ties -> TIE, no hits -> NONE. emotion_agree = exact match."),
        "n_rows": n,
        "crosstab_orientation": "rows = LLM emotion, columns = NRC word-list emotion",
        "llm_emotion_counts": {c: llm_counts.get(c, 0) for c in llm_cols},
        "llm_emotion_share": {c: llm_counts.get(c, 0) / n for c in llm_cols},
        "nrc_emotion_counts": {c: nrc_counts.get(c, 0) for c in nrc_cols},
        "nrc_emotion_share": {c: nrc_counts.get(c, 0) / n for c in nrc_cols},
        "agreement": {"all_rows": all_rows, "excluding_none": excl_none, "excluding_none_and_tie": excl_none_tie},
        "agreement_rate_all_rows": all_rows["rate"],
        "agreement_rate_excluding_none": excl_none["rate"],
        "agreement_rate_excluding_none_and_tie": excl_none_tie["rate"],
        "tie_rows": len(ties),
        "tie_rows_llm_emotion_in_tied_set": llm_in_tie,
        "tie_rows_llm_emotion_in_tied_set_rate": rate(llm_in_tie, len(ties)),
        "none_rows": nrc_counts.get("NONE", 0),
        "constant_baseline_note": "agreement of the word list with a constant answer equal to the LLM's most common emotion",
        "constant_baseline_emotion": constant,
        "constant_baseline": {"all_rows": const_all, "excluding_none": const_excl_none,
                              "excluding_none_and_tie": const_excl_none_tie},
        "constant_baseline_rate_all_rows": const_all["rate"],
        "constant_baseline_rate_excluding_none": const_excl_none["rate"],
        "constant_baseline_rate_excluding_none_and_tie": const_excl_none_tie["rate"],
        "llm_minus_constant_rate_all_rows": all_rows["rate"] - const_all["rate"],
        "llm_minus_constant_rate_excluding_none_and_tie": (excl_none_tie["rate"] or 0) - (const_excl_none_tie["rate"] or 0),
        "tie_rows_constant_in_tied_set": sum(constant in r["nrc_tied"] for r in ties),
        "best_constant_baseline_note": "agreement of the word list with the single constant emotion that matches it most often",
        "best_constant_baseline_emotion": best,
        "best_constant_baseline": {"all_rows": best_all, "excluding_none": best_excl_none,
                                   "excluding_none_and_tie": best_excl_none_tie},
        "best_constant_baseline_rate_all_rows": best_all["rate"],
        "best_constant_baseline_rate_excluding_none_and_tie": best_excl_none_tie["rate"],
        "llm_minus_best_constant_rate_all_rows": all_rows["rate"] - best_all["rate"],
        "llm_minus_best_constant_rate_excluding_none_and_tie": (excl_none_tie["rate"] or 0) - (best_excl_none_tie["rate"] or 0),
        "agreement_llm_not_constant": {"all_rows": non_majority, "excluding_none_and_tie": non_majority_single},
        "tiebreak_rule": "ties broken by fixed order anger, anticipation, disgust, fear, joy, sadness, surprise, trust (first tied wins)",
        "agreement_tiebreak": {"all_rows": {"n": n, "agree": tb_agree, "rate": rate(tb_agree, n)},
                               "excluding_none": {"n": len(tb_rows), "agree": tb_agree_excl_none,
                                                  "rate": rate(tb_agree_excl_none, len(tb_rows))}},
        "tiebreak_label_counts": {c: tb_counts.get(c, 0) for c in EMOTIONS + ["NONE"]},
        "tie_rows_broken_to": {e: sum(r["nrc_emotion_tiebreak"] == e for r in ties) for e in EMOTIONS},
        "tiebreak_constant_baseline": {"llm_most_common": tb_const(constant), "best_constant": tb_const(best_tb)},
        "unique_title_text": {"n": len(unique), "agree": sum(r["emotion_agree"] for r in unique),
                              "tie": sum(r["nrc_emotion"] == "TIE" for r in unique),
                              "none": sum(r["nrc_emotion"] == "NONE" for r in unique)},
        "negation": {"rows_with_negated_hits": len(negated_rows),
                     "negated_hits_total": sum(len(r["nrc_negated_hits"]) for r in rows),
                     "rule": "hit token within 3 tokens after not/no/never/nothing/none/nor/without/t; counted, not reversed"},
        "crosstab": {"rows": llm_cols, "columns": nrc_cols, "counts": [[crosstab[a][b] for b in nrc_cols] for a in llm_cols]},
        "crosstab_cells": {f"{a}->{b}": crosstab[a][b] for a in llm_cols for b in nrc_cols},
        "divergent_review_ids": [r["review_id"] for r in rows
                                 if r["nrc_emotion"] not in ("NONE", "TIE") and not r["emotion_agree"]],
    }


def process(run_dir, lexicon, lex_meta):
    run_dir = Path(run_dir)
    path = run_dir / "predictions.jsonl"
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    if not rows or "llm_emotion" not in rows[0]:
        raise SystemExit(f"{run_dir}: predictions have no llm_emotion (prompt without emotion)")
    for r in rows:
        r.update(score_text(r["title"], r["text"], lexicon))
        r["emotion_agree"] = r["llm_emotion"] is not None and r["llm_emotion"] == r["nrc_emotion"]
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    m = emotion_metrics(run_dir.name, rows, lex_meta)
    (run_dir / "emotion_metrics.json").write_text(json.dumps(m, indent=2))
    return m


if __name__ == "__main__":
    lexicon, lex_meta = load_lexicon()
    print(f"lexicon: {len(lexicon)} words with >=1 of the 8 emotions (source: {lex_meta['source']})")
    for d in sys.argv[1:]:
        m = process(d, lexicon, lex_meta)
        a = m["agreement"]
        print(f"{m['run']}: agreement all {a['all_rows']['agree']}/{a['all_rows']['n']} "
              f"({100 * a['all_rows']['rate']:.1f}%), excl NONE {a['excluding_none']['agree']}/{a['excluding_none']['n']}, "
              f"excl NONE+TIE {a['excluding_none_and_tie']['agree']}/{a['excluding_none_and_tie']['n']}; "
              f"TIE {m['tie_rows']}, NONE {m['none_rows']}")
        print("  LLM:", m["llm_emotion_counts"])
        print("  NRC:", m["nrc_emotion_counts"])
