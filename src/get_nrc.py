"""Fetch the NRC Emotion Lexicon (EmoLex) word-level file into data/nrc/.

Primary source: the official download from Saif M. Mohammad's NRC lexicon page.
Fallback (only if the official zip cannot be fetched non-interactively): the copy
bundled inside the NRCLex PyPI package. The lexicon itself is never committed;
runs/nrc_lexicon_meta.json records which source was used, hashes, and word counts.

Usage: python src/get_nrc.py
"""
import hashlib
import io
import json
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "nrc"
LEXICON = OUT_DIR / "NRC-Emotion-Lexicon-Wordlevel.txt"
META = ROOT / "runs" / "nrc_lexicon_meta.json"
OFFICIAL_PAGE = "https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm"
OFFICIAL_ZIP = "https://saifmohammad.com/WebDocs/Lexicons/NRC-Emotion-Lexicon.zip"
EMOTIONS = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]
SENTIMENT_COLUMNS = ["negative", "positive"]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def download(url):
    """Official zip bytes. The host answers Python's default urllib client with HTTP 406,
    so first identify this script honestly; if still refused, use the system curl client,
    which the host serves. Both fetch the same official URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "mbax6418-assignment1-get_nrc/1.0 (python urllib)"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read(), "urllib"
    except urllib.error.HTTPError as e:
        print(f"urllib fetch refused (HTTP {e.code}); retrying the same URL with curl", file=sys.stderr)
    tmp = OUT_DIR / "NRC-Emotion-Lexicon.zip.part"
    subprocess.run(["curl", "-sS", "-L", "--fail", "--max-time", "300", "-o", str(tmp), url], check=True)
    blob = tmp.read_bytes()
    tmp.unlink()
    return blob, "curl"


def from_official():
    blob, client = download(OFFICIAL_ZIP)
    (OUT_DIR / "NRC-Emotion-Lexicon.zip").write_bytes(blob)
    zf = zipfile.ZipFile(io.BytesIO(blob))
    members = [n for n in zf.namelist()
               if "wordlevel" in n.lower() and n.lower().endswith(".txt") and "__macosx" not in n.lower()]
    if not members:
        raise RuntimeError(f"no word-level .txt in zip; members: {zf.namelist()[:20]}")
    member = sorted(members, key=len)[0]
    text = zf.read(member).decode("utf-8")
    license_files = [n for n in zf.namelist() if any(k in n.lower() for k in ("readme", "terms", "license"))
                     and "__macosx" not in n.lower()]
    return text, {"source": "official", "download_client": client, "download_url": OFFICIAL_ZIP, "source_page": OFFICIAL_PAGE,
                  "zip_sha256": sha256(blob), "zip_member": member, "license_files_in_zip": license_files}


def from_nrclex():
    import importlib.util
    spec = importlib.util.find_spec("nrclex")
    if spec is None:
        raise RuntimeError("NRCLex is not installed (pip install NRCLex)")
    bundled = Path(spec.origin).parent / "nrc_en.json"
    data = json.loads(bundled.read_text())
    lines = [f"{w}\t{e}\t{int(e in emos)}" for w, emos in sorted(data.items()) for e in EMOTIONS + SENTIMENT_COLUMNS]
    return "\n".join(lines) + "\n", {"source": "nrclex_bundled_fallback", "bundled_file": str(bundled.name)}


def summarize(text):
    words, columns = {}, set()
    for line in text.splitlines():
        parts = line.strip().split("\t")
        if len(parts) != 3 or parts[2] not in ("0", "1"):
            continue
        word, emotion, flag = parts
        columns.add(emotion)
        words.setdefault(word, set())
        if flag == "1":
            words[word].add(emotion)
    return words, columns


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        text, info = from_official()
    except Exception as e:  # network/zip problems → documented fallback
        print(f"official download failed ({type(e).__name__}: {e}); trying NRCLex bundle", file=sys.stderr)
        text, info = from_nrclex()
        info["official_error"] = f"{type(e).__name__}: {e}"
    LEXICON.write_text(text, encoding="utf-8")
    words, columns = summarize(text)
    missing = [e for e in EMOTIONS if e not in columns]
    if missing:
        raise SystemExit(f"lexicon lacks emotion columns {missing}; columns found {sorted(columns)}")
    meta = {
        **info,
        "lexicon_file": str(LEXICON.relative_to(ROOT)),
        "lexicon_sha256": sha256(text.encode("utf-8")),
        "columns_found": sorted(columns),
        "word_count": len(words),
        "words_with_any_of_8_emotions": sum(bool(v & set(EMOTIONS)) for v in words.values()),
        "citation": "Saif M. Mohammad and Peter D. Turney. Crowdsourcing a Word-Emotion Association Lexicon. "
                    "Computational Intelligence, 29(3): 436-465, 2013.",
        "committed": False,
    }
    META.write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
