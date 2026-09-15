"""Skeptic checks for Step 6 (read-only; no model calls)."""
import json, re, sys, random, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import load_data as ld
import classify as cl

def rows(run):
    return [json.loads(l) for l in open(ROOT / "runs" / run / "predictions.jsonl", encoding="utf-8")]

B = rows("balanced150_v3"); F3 = rows("first100_v3")
byid = {r["review_id"]: r for r in B}

print("== 1. rating-like content in what the model saw (balanced150_v3)")
pat = re.compile(r"(\b[1-5]\s*(/\s*5|out of (5|five))\b|\bstars?\b|\brating\b|\brated\b|\b(one|two|three|four|five|[1-5])[- ]?stars?\b|\bhelpful\b|\bverified\b)", re.I)
for r in B:
    user = r["messages"][1]["content"]
    m = pat.findall(user)
    if m:
        print(" ", r["review_id"], r["rating"], r["prediction"], [x[0] for x in m], "|", user[:160].replace("\n", " "))
print("  near-miss star titles not blanked:",
      [(r["review_id"], r["title"]) for r in B if re.search(r"stars?", r["title"], re.I) and not cl.STAR_TITLE.match(r["title"])])

print("\n== 2. retry row / raw responses with >1 attempt")
for r in B:
    if len(r["raw_responses"]) > 1 or r["from_cache"]:
        print(" ", r["review_id"], "from_cache", r["from_cache"], r["raw_responses"])

print("\n== 3. blanked star titles by truth and correctness")
c = collections.Counter()
for r in B:
    bl = bool(cl.STAR_TITLE.match(r["title"]) or cl.STAR_TITLE.match(r["text"]))
    c[(bl, r["truth"], r["prediction"] == r["truth"])] += 1
for k in sorted(c): print(" ", k, c[k])

print("\n== 4. full sent text for rows cited in the analysis")
cite = [4880, 6689, 33885, 114708, 51332, 48586, 32735, 60681, 147336, 53136, 60608, 88787, 121389, 129667,
        31137, 49142, 99795, 136849, 116236, 12158, 43820, 20086, 23773, 144273, 111780, 88199, 18646, 94255, 22082]
for i in cite:
    r = byid[i]
    print(f"  [{i}] {r['rating']}★ pred={r['prediction']} emo={r['llm_emotion']}\n    SENT: {r['messages'][1]['content']!r}")

print("\n== 5. population-reweighted numbers (per-class rates from balanced run, class priors from file)")
dist = json.loads((ROOT / "runs/rating_distribution.json").read_text())
print("  rating_distribution.json:", dist)
m = json.loads((ROOT / "runs/balanced150_v3/metrics.json").read_text())
share = m["confusion_row_share"]
meta = json.loads((ROOT / "runs/balanced150_v3/run_meta.json").read_text())
pool = meta["selection_info"]["pool_size_by_class"]
N = sum(pool.values())
prior = {k: v / N for k, v in pool.items()}
print("  class priors from pools:", {k: round(v, 4) for k, v in prior.items()})
L = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
acc = sum(prior[t] * share[f"{t}->{t}"] for t in L)
print(f"  population-weighted accuracy: {acc:.4f}")
for p in L:
    num = prior[p] * share[f"{p}->{p}"]
    den = sum(prior[t] * share[f"{t}->{p}"] for t in L)
    print(f"  population-weighted precision {p}: {num/den:.4f}  (balanced-sample precision {m['per_class'][p]['precision']:.4f})")
den = sum(prior[t] * share[f"{t}->NEGATIVE"] for t in L)
print(f"  share of NEGATIVE predictions that are 3★ (population-weighted): {prior['NEUTRAL']*share['NEUTRAL->NEGATIVE']/den:.4f}  (balanced: 25/70 = {25/70:.4f})")
den = sum(prior[t] * share[f"{t}->NEUTRAL"] for t in L)
print(f"  share of NEUTRAL predictions from 4-5★ (population-weighted): {prior['POSITIVE']*share['POSITIVE->NEUTRAL']/den:.4f}")

print("\n== 6. other seeds: star mix of the balanced draw (no model calls)")
by_class = {"NEGATIVE": [], "NEUTRAL": [], "POSITIVE": []}
rating_of, title_of = {}, {}
for rid, row in ld.iter_rows():
    if ld.is_included(row):
        by_class[ld.truth_three(row["rating"])].append(rid)
        rating_of[rid] = int(row["rating"]); title_of[rid] = row["title"]
srt = {c: sorted(v) for c, v in by_class.items()}
four0 = twos = 0
four_counts, three_titles, blanked_total = [], [], []
for seed in range(1000):
    s = {c: random.Random(seed).sample(srt[c], 50) for c in srt}
    f = sum(rating_of[i] == 4 for i in s["POSITIVE"]); four_counts.append(f)
    three_titles.append(sum(bool(cl.STAR_TITLE.match(title_of[i])) for i in s["NEUTRAL"]))
    blanked_total.append(sum(bool(cl.STAR_TITLE.match(title_of[i])) for c in s for i in s[c]))
cc = collections.Counter(four_counts)
print("  4★ count in POSITIVE draw over seeds 0-999:", dict(sorted(cc.items())), "| share with 0:", cc[0] / 1000)
s42 = {c: random.Random(42).sample(srt[c], 50) for c in srt}
print("  seed 42: 4★", sum(rating_of[i] == 4 for i in s42["POSITIVE"]),
      "| 'Three Stars' titles in NEUTRAL", sum(bool(cl.STAR_TITLE.match(title_of[i])) for i in s42["NEUTRAL"]),
      "| blanked total", sum(bool(cl.STAR_TITLE.match(title_of[i])) for c in s42 for i in s42[c]))
tt = sorted(three_titles); bt = sorted(blanked_total)
print("  'Three Stars' titles in NEUTRAL draw: median", tt[500], "5-95%", tt[50], tt[950])
print("  blanked titles in whole draw: median", bt[500], "5-95%", bt[50], bt[950])
print("  pool share of star-phrase titles by class:",
      {c: round(sum(bool(cl.STAR_TITLE.match(title_of[i])) for i in srt[c]) / len(srt[c]), 4) for c in srt})

print("\n== 7. emotion claims")
for run, R in (("balanced150_v3", B), ("first100_v3", F3)):
    tr = collections.Counter((r["truth"], r["llm_emotion"]) for r in R)
    print(f"  {run} LLM emotion by truth:", dict(sorted(tr.items())))
    nonjoy = [r for r in R if r["llm_emotion"] != "joy"]
    print(f"  {run}: non-joy LLM rows {len(nonjoy)}, agree {sum(r['emotion_agree'] for r in nonjoy)}")
    for e in cl.EMOTIONS:
        print(f"    constant {e}: {sum(r['nrc_emotion'] == e for r in R)}", end="")
    print()
win = collections.Counter()
for r in B:
    if r["nrc_emotion"] == "anticipation":
        for h in r["nrc_hits"]:
            if "anticipation" in (h.get("emotions") or []):
                win[h.get("lexicon_word") or h.get("word")] += 1
print("  balanced150_v3: words contributing anticipation in rows where NRC answer is anticipation:", win.most_common(15))
print("  sample nrc_hits entry:", B[0]["nrc_hits"][:2])
