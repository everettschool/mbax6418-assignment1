"""Step 1 spot check: 10 reviews picked by reading title/text only (ratings unseen).

The expected label is what the reader judged from the words. Ratings are loaded
and printed only after all predictions are in.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classify as cl  # noqa: E402
import load_data as ld  # noqa: E402

EXPECTED_BY_READING = {
    1043: "POSITIVE", 1113: "POSITIVE", 1197: "POSITIVE", 1218: "POSITIVE", 1232: "POSITIVE",
    1453: "NEGATIVE", 1624: "NEGATIVE", 2473: "NEGATIVE", 3637: "NEGATIVE", 4511: "NEGATIVE",
}

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(cl.ROOT / ".env")
    model = os.environ["MODEL_NAME"]
    prompt = cl.PromptFile(cl.ROOT / "prompts" / "sentiment_v1.txt")
    bm = cl.make_build_messages(prompt)
    client = cl.get_client()
    stats = {"api_calls": 0, "cache_hits": 0}
    rows, _ = ld.load_rows(list(EXPECTED_BY_READING))

    out = []
    for rid, expected in EXPECTED_BY_READING.items():
        src = rows[rid]
        r = cl.classify_one(client, model, prompt, bm, src["title"], src["text"], stats)
        out.append({"review_id": rid, "title": src["title"], "text": src["text"],
                    "expected_by_reading": expected, **r})
        print(f"{rid}: expected={expected} predicted={r['prediction']} status={r['parse_status']} "
              f"raw={r['raw_responses']!r}")

    print("\n-- ratings revealed only now --")
    for row in out:
        rating = rows[row["review_id"]]["rating"]
        row["rating"] = rating
        row["truth_binary"] = ld.truth_binary(rating)
        print(f"{row['review_id']}: rating={rating} truth={row['truth_binary']} "
              f"reading_agrees={row['expected_by_reading'] == row['truth_binary']} "
              f"model_correct={row['prediction'] == row['truth_binary']}")
    hits = sum(r["prediction"] == r["expected_by_reading"] for r in out)
    print(f"\nmodel matches reading on {hits}/10; stats={stats}")
    Path(cl.ROOT / "reviews").mkdir(exist_ok=True)
    (cl.ROOT / "reviews" / "step1_spotcheck.json").write_text(json.dumps(
        {"prompt_file": prompt.rel, "prompt_sha256": prompt.sha256, "model": model,
         "matches_reading": hits, "stats": stats, "rows": out}, indent=2, ensure_ascii=False))
