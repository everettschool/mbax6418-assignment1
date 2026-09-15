"""Audit that the model never saw the rating or any field other than title and text.

For every runs/*/predictions.jsonl (and any extra files given on the command line):
  1. build_messages takes exactly (title, text).
  2. The prompt file's hash matches the run's recorded hash.
  3. Every stored message equals build_messages(source title, source text) exactly,
     so nothing but the prompt template, the title, and the text was sent.
  4. The template part of the messages (everything except the review's own title
     and text) contains none of: rating, star, stars, helpful, verified.
  5. No non-title/text field value of the row appears in the template part, and the
     distinctive ones (asin, parent_asin, user_id, timestamp) appear nowhere at all.
  6. Titles or texts that are only a star phrase ("Five Stars") were blanked, never sent.
  7. No sent title or text is a star count in another spelling ("5 stars", "Three stars.").
Occurrences of the forbidden words inside a review's own words are counted and
reported, not failed: they are the customer's text, not a leak.
"""
import inspect
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classify as cl  # noqa: E402
import load_data as ld  # noqa: E402

FORBIDDEN = re.compile(r"\b(rating|star|stars|helpful|verified)\b", re.IGNORECASE)
# Wider than the exact blanking rule: a sent title or text that is only a star count in any spelling
# ("5 stars", "Three stars.", "zero star") would be the rating itself reaching the model.
STAR_VARIANT = re.compile(r"^\W*(zero|one|two|three|four|five|[0-5](\.\d)?)\s*-?\s*stars?\W*$", re.IGNORECASE)
DISTINCTIVE = ["asin", "parent_asin", "user_id", "timestamp"]


def audit(pred_path, prompt_file, prompt_sha=None):
    prompt = cl.PromptFile(cl.ROOT / prompt_file)
    errors = []
    if prompt_sha and prompt.sha256 != prompt_sha:
        errors.append(f"prompt sha mismatch for {prompt_file}")
    build_messages = cl.make_build_messages(prompt)
    params = list(inspect.signature(build_messages).parameters)
    if params != ["title", "text"]:
        errors.append(f"build_messages parameters are {params}")

    template_part = prompt.system + "\n" + cl.PLACEHOLDER.sub("", prompt.user_template)
    if FORBIDDEN.search(template_part):
        errors.append(f"forbidden word in prompt template: {FORBIDDEN.search(template_part).group(0)}")

    preds = [json.loads(l) for l in open(pred_path, encoding="utf-8")]
    source, _ = ld.load_rows([p["review_id"] for p in preds])
    own_word_hits = star_titles = 0
    for p in preds:
        src = source[p["review_id"]]
        rid = p["review_id"]
        if p["title"] != src["title"] or p["text"] != src["text"]:
            errors.append(f"{rid}: stored title/text differ from source")
        if p["messages"] != build_messages(src["title"], src["text"]):
            errors.append(f"{rid}: stored messages are not build_messages(title, text)")
        full = "\n".join(m["content"] for m in p["messages"])
        for field in ("title", "text"):
            if cl.STAR_TITLE.match(src[field]) and f"<<<{src[field]}>>>" in full:
                errors.append(f"{rid}: star-phrase {field} '{src[field]}' was sent to the model")
        for field, value in (("title", cl.model_title(src["title"])), ("text", cl.model_text(src["text"]))):
            if STAR_VARIANT.match(value):
                errors.append(f"{rid}: sent {field} '{value}' is a star-count phrase the blanking rule missed")
        star_titles += bool(cl.STAR_TITLE.match(src["title"]) or cl.STAR_TITLE.match(src["text"]))
        own_word_hits += bool(FORBIDDEN.search(cl.model_title(src["title"]) + "\n" + cl.model_text(src["text"])))
        for field, value in src.items():
            if field in ("title", "text"):
                continue
            forms = {str(value), json.dumps(value)}
            if isinstance(value, float) and value.is_integer():
                forms.add(str(int(value)))
            for form in forms:
                if form and re.search(rf"(?<![\w.]){re.escape(form)}(?![\w])", template_part):
                    errors.append(f"{rid}: value of '{field}' ({form}) appears in the template")
            if field in DISTINCTIVE and str(value) in full:
                errors.append(f"{rid}: value of '{field}' appears in a message")
    return len(preds), own_word_hits, star_titles, errors


def main(extra):
    targets = []
    for meta_path in sorted((cl.ROOT / "runs").glob("*/run_meta.json")):
        meta = json.loads(meta_path.read_text())
        targets.append((meta_path.parent / "predictions.jsonl", meta["prompt_file"], meta["prompt_sha256"]))
    for path in extra:
        path = Path(path).resolve()
        doc = json.loads(path.read_text())
        cl.CACHE_DIR.mkdir(exist_ok=True)
        tmp = cl.CACHE_DIR / f"leakcheck_{path.stem}.jsonl"
        tmp.write_text("".join(json.dumps(r) + "\n" for r in doc["rows"]))
        targets.append((tmp, doc["prompt_file"], doc["prompt_sha256"]))
    failed = False
    for pred_path, prompt_file, sha in targets:
        n, own, star_titles, errors = audit(pred_path, prompt_file, sha)
        rel = pred_path.relative_to(cl.ROOT)
        print(f"{'FAIL' if errors else 'PASS'} {rel}: {n} rows, prompt {prompt_file}; "
              f"{star_titles} rows had a star-phrase title/text blanked; {own} reviews use a forbidden word "
              f"in their own sent title/text (customer's words, allowed)")
        for e in errors[:20]:
            print("   ", e)
        failed |= bool(errors)
    if not targets:
        print("no runs found")
    sys.exit(1 if failed or not targets else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
