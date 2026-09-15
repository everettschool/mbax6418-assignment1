"""Data access for the Amazon Reviews '23 Gift Cards file.

review_id is the 0-based line index of a review in Gift_Cards.jsonl.gz. It is the
id in every output file, part of the cache key's row, and the sampling key.
"""
import gzip
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "Gift_Cards.jsonl.gz"
DATA_URL = ("https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/"
            "review_categories/Gift_Cards.jsonl.gz")
RANDOM_SEED = 42
PER_CLASS = 50

INCLUSION_RULE = "text is non-empty after stripping whitespace"
BATCH_100_RULE = "first 100 review_ids in file order that pass the inclusion rule"
BALANCED_RULE = ("for each three-class truth label, random.Random(42).sample(sorted included "
                 "review_ids of that class, 50); ids saved to sample_ids.json")

# Carried into predictions files for analysis only. Never sent to the model.
KEPT_METADATA = ["verified_purchase", "helpful_vote", "timestamp", "asin", "parent_asin"]


def iter_rows(path=DATA_PATH):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for review_id, line in enumerate(f):
            yield review_id, json.loads(line)


def is_included(row):
    return bool((row.get("text") or "").strip())


def dataset_sha256(path=DATA_PATH):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def metadata(row):
    kept = {k: row.get(k) for k in KEPT_METADATA}
    kept["images_count"] = len(row.get("images") or [])
    return kept


def truth_binary(rating):
    return "POSITIVE" if rating >= 4 else "NEGATIVE"


def truth_three(rating):
    r = int(rating)
    if r >= 4:
        return "POSITIVE"
    if r == 3:
        return "NEUTRAL"
    return "NEGATIVE"


TRUTH = {"binary": truth_binary, "three": truth_three}


def select_batch_100(n=100):
    """First n included review_ids; also how many excluded rows were passed over."""
    ids, skipped = [], 0
    for review_id, row in iter_rows():
        if is_included(row):
            ids.append(review_id)
            if len(ids) == n:
                break
        else:
            skipped += 1
    return ids, {"rows_skipped_by_inclusion_rule": skipped, "scanned_through_review_id": ids[-1]}


def select_balanced(per_class=PER_CLASS, seed=RANDOM_SEED):
    """~per_class ids per three-class label, sampled from the whole file."""
    by_class = {"NEGATIVE": [], "NEUTRAL": [], "POSITIVE": []}
    skipped = 0
    for review_id, row in iter_rows():
        if is_included(row):
            by_class[truth_three(row["rating"])].append(review_id)
        else:
            skipped += 1
    sampled = {c: sorted(random.Random(seed).sample(sorted(ids), per_class))
               for c, ids in by_class.items()}
    return sampled, {"rows_skipped_by_inclusion_rule": skipped,
                     "pool_size_by_class": {c: len(v) for c, v in by_class.items()}}


def load_rows(ids):
    """Rows for the given review_ids, plus the file's total row count."""
    wanted, rows, count = set(ids), {}, 0
    for review_id, row in iter_rows():
        count += 1
        if review_id in wanted:
            rows[review_id] = row
    missing = wanted - rows.keys()
    if missing:
        raise KeyError(f"review_ids not in file: {sorted(missing)[:5]}")
    return rows, count
