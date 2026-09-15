"""LLM sentiment (and emotion) classifier for Gift Cards reviews.

The model sees only a review's title and text. build_messages(title, text) is the
single place messages are built, and every message actually sent is stored in
predictions.jsonl so src/verify_leak.py can audit it.

Usage:
  python src/classify.py --prompt prompts/sentiment_v1.txt --selection batch_100 --run first100_v1
  python src/classify.py ... --preview 3     # print 3 raw responses, write nothing
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load_data as ld  # noqa: E402

ROOT = ld.ROOT
CACHE_DIR = ROOT / "cache"
CALL_COUNTER = CACHE_DIR / "api_calls_total.json"
API_CALL_CAP = 1500
STEP0_PROBE_CALLS = 3  # endpoint probes made in Step 0, before this counter existed
ENDPOINT_LABEL = "course-endpoint"
TEMPERATURE = 0
# The served model is a thinking model; with thinking on, a small max_tokens yields
# content=None. This vLLM chat-template switch turns it off (see ISSUES.md, Step 0).
EXTRA_BODY = {"chat_template_kwargs": {"enable_thinking": False}}
MAX_RETRIES = 5
EMOTIONS = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]

PROMPT_SPECS = {
    "sentiment_v1.txt": {"labels": ["POSITIVE", "NEGATIVE"], "emotion": False, "scheme": "binary", "max_tokens": 16},
    "sentiment_v2.txt": {"labels": ["POSITIVE", "NEGATIVE"], "emotion": True, "scheme": "binary", "max_tokens": 24},
    "sentiment_v3.txt": {"labels": ["POSITIVE", "NEUTRAL", "NEGATIVE"], "emotion": True, "scheme": "three", "max_tokens": 24},
}
USER_SPLIT = "=== USER ==="
PLACEHOLDER = re.compile(r"\{\{(TITLE|TEXT)\}\}")
FENCE_LINE = re.compile(r"^`{3,}[a-zA-Z]*$")  # a code-fence opener/closer on its own line
# Amazon auto-fills some titles from the star count ("Five Stars", "One Star"); a few
# texts are that phrase alone. Such a field is the rating itself rather than customer
# words, so it is blanked before sending. Longer text that merely mentions stars is kept.
STAR_TITLE = re.compile(r"^\s*(one|two|three|four|five)\s+stars?\s*$", re.IGNORECASE)


def model_title(title):
    return "" if STAR_TITLE.match(title) else title


def model_text(text):
    return "" if STAR_TITLE.match(text) else text


class PromptFile:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.name = self.path.name
        self.rel = str(self.path.relative_to(ROOT))
        self.text = self.path.read_text(encoding="utf-8")
        self.sha256 = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        self.spec = PROMPT_SPECS[self.name]
        system, user = self.text.split(USER_SPLIT)
        self.system = system.strip()
        self.user_template = user.strip()


def make_build_messages(prompt):
    def build_messages(title: str, text: str) -> list:
        if not isinstance(title, str) or not isinstance(text, str):
            raise TypeError("build_messages takes exactly two strings: title and text")
        values = {"TITLE": model_title(title), "TEXT": model_text(text)}
        user = PLACEHOLDER.sub(lambda m: values[m.group(1)], prompt.user_template)
        return [{"role": "system", "content": prompt.system},
                {"role": "user", "content": user}]
    return build_messages


def parse_response(raw, spec):
    """(label, emotion) from the last line matching the required format, else None.

    Only normalization: strip whitespace and code fences.
    """
    if not isinstance(raw, str):
        return None
    labels = "|".join(spec["labels"])
    if spec["emotion"]:
        pattern = re.compile(rf"^LABEL=({labels});EMOTION=({'|'.join(EMOTIONS)})$")
    else:
        pattern = re.compile(rf"^LABEL=({labels})$")
    for line in reversed(raw.strip().splitlines()):
        line = line.strip()
        if FENCE_LINE.match(line):
            continue
        line = line.strip("`").strip()
        m = pattern.match(line)
        if m:
            return m.group(1), (m.group(2) if spec["emotion"] else None)
    return None


def cache_key(model, prompt_text, title, text):
    return hashlib.sha256(json.dumps([model, prompt_text, title, text]).encode("utf-8")).hexdigest()


def count_call():
    """Increment the session-wide API call counter; refuse to pass the cap."""
    CACHE_DIR.mkdir(exist_ok=True)
    total = json.loads(CALL_COUNTER.read_text())["total"] if CALL_COUNTER.exists() else STEP0_PROBE_CALLS
    if total >= API_CALL_CAP:
        raise RuntimeError(f"API_CALL_CAP of {API_CALL_CAP} reached; stop and ask the user")
    CALL_COUNTER.write_text(json.dumps({"total": total + 1}))


def get_client():
    from dotenv import load_dotenv
    from openai import OpenAI
    load_dotenv(ROOT / ".env")
    return OpenAI(base_url=os.environ["OPENAI_BASE_URL"], api_key=os.environ["OPENAI_API_KEY"],
                  timeout=60, max_retries=0)


def _scrub(message):
    base = os.environ.get("OPENAI_BASE_URL", "")
    host = re.sub(r"^https?://", "", base).split("/")[0]
    for s in filter(None, [base, host]):
        message = message.replace(s, ENDPOINT_LABEL)
    return message


def call_model(client, model, messages, max_tokens, stats):
    """One completion with up to MAX_RETRIES retries on 429/5xx/timeouts/connection errors."""
    import openai
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        count_call()
        stats["api_calls"] += 1
        try:
            r = client.chat.completions.create(model=model, messages=messages, temperature=TEMPERATURE,
                                               max_tokens=max_tokens, extra_body=EXTRA_BODY)
            return {"ok": True, "content": r.choices[0].message.content,
                    "finish_reason": r.choices[0].finish_reason, "served_model": r.model}
        except (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError,
                openai.InternalServerError) as e:
            last_error = _scrub(f"{type(e).__name__}: {e}")
        except openai.APIStatusError as e:
            return {"ok": False, "error": _scrub(f"{type(e).__name__} {e.status_code}: {e}")}
        if attempt < MAX_RETRIES:
            time.sleep(2 ** attempt)
    return {"ok": False, "error": last_error}


def classify_one(client, model, prompt, build_messages, title, text, stats):
    messages = build_messages(title, text)
    key = cache_key(model, prompt.text, title, text)
    cache_path = CACHE_DIR / f"{key}.json"
    result = {"messages": messages, "cache_key": key, "raw_responses": [], "from_cache": False}

    if cache_path.exists():
        raw = json.loads(cache_path.read_text())["raw_response"]
        parsed = parse_response(raw, prompt.spec)
        if parsed:
            stats["cache_hits"] += 1
            return {**result, "raw_responses": [raw], "from_cache": True, "parse_status": "OK",
                    "prediction": parsed[0], "llm_emotion": parsed[1]}

    # First attempt, then exactly one retry (bypassing the cache) if the reply does not parse.
    for _ in range(2):
        res = call_model(client, model, messages, prompt.spec["max_tokens"], stats)
        if not res["ok"]:
            return {**result, "parse_status": "API_ERROR", "prediction": "UNPARSED",
                    "llm_emotion": None, "api_error": res["error"]}
        result["raw_responses"].append(res["content"])
        result["served_model"] = res["served_model"]
        parsed = parse_response(res["content"], prompt.spec)
        if parsed:
            CACHE_DIR.mkdir(exist_ok=True)
            cache_path.write_text(json.dumps({"model": model, "prompt_sha256": prompt.sha256,
                                              "raw_response": res["content"]}))
            return {**result, "parse_status": "OK", "prediction": parsed[0], "llm_emotion": parsed[1]}
    return {**result, "parse_status": "FAIL", "prediction": "UNPARSED", "llm_emotion": None}


def resolve_selection(selection, run_dir):
    if selection == "batch_100":
        ids, info = ld.select_batch_100()
        return ids, ld.BATCH_100_RULE, info
    if selection == "balanced_150":
        sample_path = run_dir / "sample_ids.json"
        if sample_path.exists():  # reproduction reads ids, never re-draws
            saved = json.loads(sample_path.read_text())
            return saved["review_ids"], ld.BALANCED_RULE, saved["selection_info"]
        by_class, info = ld.select_balanced()
        ids = sorted(i for v in by_class.values() for i in v)
        run_dir.mkdir(parents=True, exist_ok=True)
        sample_path.write_text(json.dumps({"seed": ld.RANDOM_SEED, "per_class": ld.PER_CLASS,
                                           "rule": ld.BALANCED_RULE, "by_class": by_class,
                                           "review_ids": ids, "selection_info": info}, indent=2))
        return ids, ld.BALANCED_RULE, info
    raise ValueError(selection)


def run(prompt_path, selection, run_name, preview=0):
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    model = os.environ["MODEL_NAME"]
    prompt = PromptFile(prompt_path)
    build_messages = make_build_messages(prompt)
    truth_fn = ld.TRUTH[prompt.spec["scheme"]]
    run_dir = ROOT / "runs" / run_name
    ids, selection_rule, selection_info = resolve_selection(selection, run_dir)
    rows, row_count = ld.load_rows(ids)
    client = get_client()
    stats = {"api_calls": 0, "cache_hits": 0}

    if preview:
        for rid in ids[:preview]:
            r = classify_one(client, model, prompt, build_messages, rows[rid]["title"], rows[rid]["text"], stats)
            print(f"review_id={rid} status={r['parse_status']} raw={r['raw_responses']!r}")
        print("preview stats:", stats)
        return

    out = []
    for n, rid in enumerate(ids, 1):
        src = rows[rid]
        r = classify_one(client, model, prompt, build_messages, src["title"], src["text"], stats)
        out.append({"review_id": rid, "title": src["title"], "text": src["text"], **ld.metadata(src),
                    "rating": src["rating"], "truth": truth_fn(src["rating"]), **r})
        if n % 25 == 0:
            print(f"{n}/{len(ids)} done; stats={stats}", flush=True)

    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "predictions.jsonl", "w", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    served = sorted({r["served_model"] for r in out if r.get("served_model")})
    meta = {
        "run": run_name, "model": model, "served_model_reported": served, "endpoint": ENDPOINT_LABEL,
        "temperature": TEMPERATURE, "temperature_accepted": True, "max_tokens": prompt.spec["max_tokens"],
        "extra_body": EXTRA_BODY, "prompt_file": prompt.rel, "prompt_sha256": prompt.sha256,
        "label_scheme": prompt.spec["scheme"], "labels": prompt.spec["labels"],
        "emotion_requested": prompt.spec["emotion"], "seed": ld.RANDOM_SEED,
        "dataset_file": ld.DATA_PATH.name, "dataset_url": ld.DATA_URL, "dataset_sha256": ld.dataset_sha256(),
        "dataset_row_count": row_count, "inclusion_rule": ld.INCLUSION_RULE, "selection": selection,
        "selection_rule": selection_rule, "selection_info": selection_info, "n_rows": len(out),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "api_call_count": stats["api_calls"], "cache_hits": stats["cache_hits"],
        "parse_fail_count": sum(r["parse_status"] == "FAIL" for r in out),
        "api_error_count": sum(r["parse_status"] == "API_ERROR" for r in out),
        "rows_needing_retry": sum(len(r["raw_responses"]) > 1 for r in out),
    }
    (run_dir / "run_meta.json").write_text(json.dumps(meta, indent=2))
    # Fresh predictions carry no word-list fields; emotion metrics from an earlier pass would be stale.
    stale = run_dir / "emotion_metrics.json"
    if stale.exists():
        stale.unlink()
        print(f"removed stale {stale.relative_to(ROOT)}; re-run src/nrc_emotion.py {run_dir.relative_to(ROOT)}")
    print(json.dumps({k: meta[k] for k in ["run", "n_rows", "api_call_count", "cache_hits",
                                            "parse_fail_count", "api_error_count"]}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--prompt", required=True)
    p.add_argument("--selection", required=True, choices=["batch_100", "balanced_150"])
    p.add_argument("--run", required=True)
    p.add_argument("--preview", type=int, default=0)
    a = p.parse_args()
    run(a.prompt, a.selection, a.run, a.preview)
