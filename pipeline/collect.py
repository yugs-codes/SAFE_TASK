"""Collect Google News RSS items for each focus state.

Each query is run once per quarter (after:/before:) so every slice gets its own
~100-item budget; a quarter that comes back full is re-run month by month.
Raw responses are cached in data/cache/ so re-runs don't hit Google again.

usage: python pipeline/collect.py [--no-cache]
"""
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from urllib.parse import quote_plus

import feedparser

import config
from common import CACHE, DATA, IST, log, now_ist, short_hash, write_json, write_jsonl


def quarter_slices(start: date, end: date) -> list[tuple[date, date]]:
    out, y, q = [], start.year, (start.month - 1) // 3
    while True:
        a = date(y, q * 3 + 1, 1)
        b = date(y + (q + 1) // 4, ((q + 1) % 4) * 3 + 1, 1)
        if a > end:
            break
        out.append((a, b))
        y, q = (y + 1, 0) if q == 3 else (y, q + 1)
    return out


def month_slices(a: date, b: date) -> list[tuple[date, date]]:
    out, cur = [], a
    while cur < b:
        nxt = date(cur.year + cur.month // 12, cur.month % 12 + 1, 1)
        out.append((cur, min(nxt, b)))
        cur = nxt
    return out


def fetch(url: str, use_cache: bool) -> tuple[bytes, bool]:
    """Return (body, from_cache). Retries 429/5xx with backoff."""
    path = CACHE / f"{short_hash(url, 16)}.xml"
    if use_cache and path.exists():
        return path.read_bytes(), True
    delay = 5
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            return body, False
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 3:
                log(f"  HTTP {e.code}, retrying in {delay}s")
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except urllib.error.URLError:
            if attempt < 3:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("unreachable")


def entries_of(body: bytes) -> list[dict]:
    feed = feedparser.parse(body)
    rows = []
    for e in feed.entries:
        pp = e.get("published_parsed")
        published_utc = datetime(*pp[:6], tzinfo=timezone.utc).isoformat() if pp else None
        src = e.get("source") or {}
        rows.append({
            "title": e.get("title", "").strip(),
            "link": e.get("link", "").strip(),
            "published": e.get("published"),
            "published_utc": published_utc,
            "description": e.get("summary", ""),
            "source_title": (src.get("title") or "").strip(),
            "source_href": (src.get("href") or "").strip(),
        })
    return rows


def run(use_cache: bool = True) -> None:
    start = date.fromisoformat(config.START_DATE)
    today = now_ist().date()
    jobs = []  # (state_code, query, lang, after, before)
    for code, s in config.FOCUS_STATES.items():
        for tpl in config.QUERY_TEMPLATES:
            q = tpl.format(state=s["name"])
            for a, b in quarter_slices(start, today):
                jobs.append((code, q, "en", a, b))
    for code, q in config.HINDI_QUERIES:
        jobs.append((code, q, "hi", start, date(today.year + 1, 1, 1)))

    raw, log_rows, live = [], [], 0
    queue = list(jobs)
    while queue:
        code, q, lang, a, b = queue.pop(0)
        full_q = f"{q} after:{a.isoformat()} before:{b.isoformat()}"
        url = (config.RSS_HI if lang == "hi" else config.RSS_EN).format(q=quote_plus(full_q))
        try:
            body, cached = fetch(url, use_cache)
        except Exception as e:  # keep going; a missing slice is logged, not fatal
            log(f"FAIL {code} | {full_q} | {e}")
            log_rows.append({"state": code, "query": q, "lang": lang, "after": a.isoformat(), "before": b.isoformat(), "items": None, "error": str(e)[:200]})
            continue
        if not cached:
            live += 1
            time.sleep(config.SLEEP_SECONDS)
        items = entries_of(body)
        span_days = (b - a).days
        if len(items) >= config.SLICE_SPLIT_AT and span_days > 35:
            log(f"split  {code} | {full_q} | {len(items)} items -> monthly")
            queue[:0] = [(code, q, lang, ma, mb) for ma, mb in month_slices(a, b)]
            continue
        log(f"{len(items):4d}  {code} | {full_q}{'  (cache)' if cached else ''}")
        log_rows.append({"state": code, "query": q, "lang": lang, "after": a.isoformat(), "before": b.isoformat(), "items": len(items)})
        for it in items:
            it.update({"query": q, "query_state": code, "lang": lang, "slice": f"{a.isoformat()}..{b.isoformat()}"})
            raw.append(it)

    write_jsonl(DATA / "raw.jsonl", raw)
    write_json(DATA / "collect_log.json", {
        "collected_at": now_ist().isoformat(timespec="seconds"),
        "requests": len(log_rows),
        "live_requests": live,
        "items": len(raw),
        "slices": log_rows,
    })
    log(f"\nraw items: {len(raw)} from {len(log_rows)} slices ({live} live requests)")
    # Show what the RSS description actually contains, so the summary decision is informed.
    for it in raw[:3]:
        log(f"sample description: {it['description'][:160]!r}")


if __name__ == "__main__":
    run(use_cache="--no-cache" not in sys.argv)
