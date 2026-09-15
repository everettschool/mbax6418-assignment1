"""Skeptic round 2 checks. Read-only on project files; no model calls."""
import json, re, sys, gzip, random, math
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import classify as cl, load_data as ld

def rows(run): return [json.loads(l) for l in open(ROOT/"runs"/run/"predictions.jsonl")]
B = rows("balanced150_v3"); F3 = rows("first100_v3"); F1 = rows("first100_v1")
def sent(r):
    u = r["messages"][1]["content"]
    m = re.match(r"TITLE:\n<<<(.*)>>>\n\nTEXT:\n<<<(.*)>>>\Z", u, re.S)
    return m.group(1), m.group(2)

print("== A. All 40 wrong rows on balanced150_v3 (sent title | sent text)")
for r in sorted(B, key=lambda r: (r["truth"], r["prediction"], r["review_id"])):
    if r["truth"] != r["prediction"]:
        t, x = sent(r)
        print(f"[{r['review_id']}] {int(r['rating'])}★ {r['truth']}->{r['prediction']} emo={r['llm_emotion']} | T: {t!r} | X: {x[:400]!r}")

print("\n== B. Star/rating words in SENT content (all runs), broader regex")
pat = re.compile(r"\b(zero|one|two|three|four|five|[0-5]|no)\s*-?\s*stars?\b|\bstars?\b|\brat(ed|ing)\b|★", re.I)
for run in ["first100_v1","first100_v2","first100_v3","balanced150_v3"]:
    for r in rows(run):
        t, x = sent(r)
        for f, v in (("title", t), ("text", x)):
            for m in pat.finditer(v):
                print(f"  {run} {r['review_id']} {int(r['rating'])}★ pred={r['prediction']} {f}: ...{v[max(0,m.start()-40):m.end()+40]!r}")

print("\n== B2. Is a blank SENT title informative? original empty titles vs blanked star titles, by class (whole file, included rows)")
empty = Counter(); star = Counter(); tot = Counter(); near = Counter(); near_ex = defaultdict(list)
nearpat = re.compile(r"^\s*(one|two|three|four|five|[1-5])\s*-?\s*stars?\W*$", re.I)
for rid, row in ld.iter_rows():
    if not ld.is_included(row): continue
    c = ld.truth_three(row["rating"]); tot[c] += 1
    ti = row["title"]
    if not ti.strip(): empty[c] += 1
    elif cl.STAR_TITLE.match(ti): star[c] += 1
    elif nearpat.match(ti):
        near[(c, int(row["rating"]))] += 1
        if len(near_ex[c]) < 3: near_ex[c].append(ti)
for c in tot:
    print(f"  {c}: pool {tot[c]}; originally empty title {empty[c]} ({empty[c]/tot[c]:.1%}); blanked star title {star[c]} ({star[c]/tot[c]:.1%})")
    print(f"     among rows whose SENT title is empty, share that are blanked star titles: {star[c]/(star[c]+empty[c]):.1%}")
print("  near-variant star titles NOT blanked (e.g. 'Five stars!', '5 stars'), by (class, rating):", dict(near), dict(near_ex))

print("\n== C. first100 v1 vs v3 predictions")
for a, b in zip(F1, F3):
    assert a["review_id"] == b["review_id"]
    if a["prediction"] != b["prediction"] or b["prediction"] != b["truth"]:
        print(f"  {a['review_id']} {int(a['rating'])}★ v1={a['prediction']} v3={b['prediction']} v3truth={b['truth']}")

print("\n== D. Emotions, balanced150_v3")
print("  NRC answer counts:", Counter(r["nrc_emotion"] for r in B))
print("  NRC answer by truth:", {c: dict(Counter(r["nrc_emotion"] for r in B if r["truth"]==c)) for c in ("POSITIVE","NEUTRAL","NEGATIVE")})
print("  LLM answer counts:", Counter(r["llm_emotion"] for r in B))
ant = [r for r in B if r["nrc_emotion"] == "anticipation"]
def without_gift(r):
    s = Counter()
    for tok, lem, emos in r["nrc_hits"]:
        if lem.startswith("gift"): continue
        for e in emos: s[e] += 1
    if not s: return "NONE"
    top = max(s.values()); w = [e for e in s if s[e]==top]
    return w[0] if len(w)==1 else "TIE"
g = [r for r in ant if any(l.startswith("gift") for _, l, _ in r["nrc_hits"])]
print(f"  anticipation answers {len(ant)}; with gift {len(g)}; answer if gift hits removed: {Counter(without_gift(r) for r in g)}")
print("  gift-hit rows overall:", sum(any(l.startswith('gift') for _,l,_ in r['nrc_hits']) for r in B), "of 150")
print("  NRC answer when gift removed, ALL rows:", Counter(without_gift(r) for r in B))
agree = [r for r in B if r["llm_emotion"] == r["nrc_emotion"]]
print("  the 16 agreements:", [(r["review_id"], r["llm_emotion"], r["truth"]) for r in agree])
print("  nrc_hits keys sample:", B[0]["nrc_hits"][:2])
print("  first100_v3: non-joy LLM rows", sum(r["llm_emotion"]!="joy" for r in F3), "agree among them", sum(r["llm_emotion"]!="joy" and r["llm_emotion"]==r["nrc_emotion"] for r in F3))
print("  balanced ties/none:", Counter(r["nrc_emotion"] for r in B if r["nrc_emotion"] in ("TIE","NONE")))
# emotion agreement by truth class
for c in ("POSITIVE","NEUTRAL","NEGATIVE"):
    sub=[r for r in B if r["truth"]==c]
    print(f"  {c}: LLM=NRC {sum(r['llm_emotion']==r['nrc_emotion'] for r in sub)}/50; NRC single winner {sum(r['nrc_emotion'] not in ('TIE','NONE') for r in sub)}")
# NRC anger/negative words in the 25 N->NEG rows
nn = [r for r in B if r["truth"]=="NEUTRAL" and r["prediction"]=="NEGATIVE"]
print("  N->NEG rows NRC answers:", Counter(r["nrc_emotion"] for r in nn))

print("\n== E. Blanked-title effect on 3★->POSITIVE")
neu = [r for r in B if r["truth"]=="NEUTRAL"]
bl = [r for r in neu if cl.STAR_TITLE.match(r["title"])]
nb = [r for r in neu if not cl.STAR_TITLE.match(r["title"])]
a = sum(r["prediction"]=="POSITIVE" for r in bl); b = sum(r["prediction"]=="POSITIVE" for r in nb)
print(f"  blanked {a}/{len(bl)} POSITIVE; not blanked {b}/{len(nb)}")
# Fisher exact one-sided
def comb(n,k): return math.comb(n,k)
N=len(neu); K=a+b; n=len(bl)
p = sum(comb(K,i)*comb(N-K,n-i) for i in range(a, min(K,n)+1))/comb(N,n)
print(f"  Fisher one-sided p (>= {a} of {n}) = {p:.3f}")
print(f"  expected 3★->POSITIVE at mean 6.61 blanked titles: {6.61*a/len(bl) + (50-6.61)*b/len(nb):.2f} vs observed {a+b}")

print("\n== F. Blanked titles in NEUTRAL->NEGATIVE / by prediction (NEUTRAL row)")
print("  ", {k: Counter(r["prediction"] for r in grp) for k, grp in (("blanked", bl), ("not", nb))})

print("\n== G. Balanced sample NEGATIVE row: 2★ rows and predictions")
print("  ", Counter((int(r["rating"]), r["prediction"]) for r in B if r["truth"]=="NEGATIVE"))
print("  POSITIVE row:", Counter((int(r["rating"]), r["prediction"]) for r in B if r["truth"]=="POSITIVE"))
