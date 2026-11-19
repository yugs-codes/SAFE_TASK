"""Shared helpers: paths, IO, time, URL canonicalisation."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# Windows consoles default to cp1252 and crash on Hindi titles.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DROPPED = DATA / "dropped"
AUDIT = ROOT / "audit"
DOCS = ROOT / "docs"
CACHE = DATA / "cache"

# IST has no daylight saving, so a fixed offset is exact (and avoids tzdata on Windows).
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    return datetime.now(IST)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def canonical_url(url: str) -> str:
    """Drop query string, fragment and trailing slash; lowercase the host."""
    p = urlsplit(url.strip())
    path = p.path.rstrip("/") or "/"
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, "", ""))


def short_hash(text: str, n: int = 10) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def domain_of(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', " ": " "})


def clean_title(title: str, source: str = "") -> str:
    """Strip Google News' trailing ' - Source', normalise quotes and whitespace."""
    t = (title or "").translate(_QUOTES)
    if source and t.endswith(" - " + source):
        t = t[: -len(" - " + source)]
    t = " ".join(t.split())
    return t.rstrip(" |-").strip()


def update_stats(section: str, values: dict) -> None:
    """Each stage records its own counts in data/stats.json; export builds the funnel from it."""
    path = DATA / "stats.json"
    stats = read_json(path, {}) or {}
    stats[section] = values
    write_json(path, stats)
