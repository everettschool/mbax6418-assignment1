"""Offline self-test of the parser, cache, FAIL retry, and API_ERROR path (no real API calls)."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import httpx2 as httpx  # openai 3.x depends on httpx2, not httpx
import openai

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classify as cl  # noqa: E402

cl.count_call = lambda: None          # fake calls must not touch the session counter
cl.time.sleep = lambda s: None
cl.CACHE_DIR = Path(tempfile.mkdtemp())

V1 = cl.PROMPT_SPECS["sentiment_v1.txt"]
V2 = cl.PROMPT_SPECS["sentiment_v2.txt"]
cases = [
    ("LABEL=POSITIVE", V1, ("POSITIVE", None)),
    ("  LABEL=NEGATIVE  \n", V1, ("NEGATIVE", None)),
    ("```\nLABEL=NEGATIVE\n```", V1, ("NEGATIVE", None)),
    ("`LABEL=POSITIVE`", V1, ("POSITIVE", None)),
    ("The card works.\nLABEL=POSITIVE", V1, ("POSITIVE", None)),
    ("LABEL=POSITIVE\nLABEL=NEGATIVE", V1, ("NEGATIVE", None)),
    ("label=positive", V1, None),
    ("LABEL=NEUTRAL", V1, None),
    ("LABEL = POSITIVE", V1, None),
    ("Positive", V1, None),
    ("", V1, None),
    (None, V1, None),
    ("LABEL=POSITIVE;EMOTION=joy", V2, ("POSITIVE", "joy")),
    ("LABEL=POSITIVE;EMOTION=Joy", V2, None),
    ("LABEL=POSITIVE;EMOTION=love", V2, None),
    ("LABEL=POSITIVE", V2, None),
]
for raw, spec, expected in cases:
    got = cl.parse_response(raw, spec)
    assert got == expected, (raw, got, expected)
print(f"parser: {len(cases)} cases pass (incl. malformed, None, wrong case, wrong label)")


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(model="fake", choices=[SimpleNamespace(
            message=SimpleNamespace(content=reply), finish_reason="stop")])


prompt = cl.PromptFile(cl.ROOT / "prompts" / "sentiment_v1.txt")
bm = cl.make_build_messages(prompt)
stats = {"api_calls": 0, "cache_hits": 0}

r = cl.classify_one(FakeClient(["sure!", "I think positive"]), "m", prompt, bm, "t1", "x1", stats)
assert r["parse_status"] == "FAIL" and r["prediction"] == "UNPARSED"
assert r["raw_responses"] == ["sure!", "I think positive"]
assert not (cl.CACHE_DIR / f"{r['cache_key']}.json").exists()
print("malformed twice -> FAIL, UNPARSED, both raw responses kept, nothing cached")

r = cl.classify_one(FakeClient(["???", "LABEL=NEGATIVE"]), "m", prompt, bm, "t2", "x2", stats)
assert r["parse_status"] == "OK" and r["prediction"] == "NEGATIVE" and len(r["raw_responses"]) == 2
assert (cl.CACHE_DIR / f"{r['cache_key']}.json").exists()
r = cl.classify_one(FakeClient([]), "m", prompt, bm, "t2", "x2", stats)
assert r["from_cache"] and r["prediction"] == "NEGATIVE"
print("malformed then valid -> OK with both raws, cached; second call served from cache")

req = httpx.Request("POST", "http://example.invalid/v1/chat/completions")
errs = [openai.APIConnectionError(request=req) for _ in range(cl.MAX_RETRIES + 1)]
before = stats["api_calls"]
r = cl.classify_one(FakeClient(errs), "m", prompt, bm, "t3", "x3", stats)
assert r["parse_status"] == "API_ERROR" and stats["api_calls"] - before == cl.MAX_RETRIES + 1
print(f"connection errors -> API_ERROR after {cl.MAX_RETRIES + 1} attempts, no crash")

try:
    bm("title", 5)
    raise AssertionError("non-string accepted")
except TypeError:
    print("build_messages rejects non-string input")
print("ALL SELF-TESTS PASS")
