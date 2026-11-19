"""Keyword relevance filter.

First collapses the same article returned by several queries (identical canonical
link). Then keeps an article only if its headline has an AI term AND a
state-government signal, and no private-sector exclusion phrase that outweighs it.
Every dropped article is written to data/dropped/filter.jsonl with its reason.
"""
from __future__ import annotations

from collections import Counter

import config
import states
from common import DATA, DROPPED, canonical_url, clean_title, log, read_jsonl, short_hash, update_stats, write_jsonl


def has_ai(text: str) -> bool:
    return bool(config.AI_CASE.search(text) or config.AI_CI.search(text) or any(t in text for t in config.AI_HINDI))


def gov_signal(text: str, date_iso: str | None) -> str | None:
    """'strong', 'weak' or None. Central-government phrases are removed first,
    so "Union Minister" does not count as a state actor."""
    t = config.CENTRAL.sub(" ", text)
    if (config.GOV_STRONG.search(t) or config.GOV_CM.search(t)
            or any(h in t for h in config.GOV_HINDI) or states.cm_mentioned(t, date_iso)):
        return "strong"
    if config.GOV_WEAK.search(config.GOV_WEAK_NOT.sub(" ", t)) and states.mentions_any_state(t):
        return "weak"
    return None


def decide(title: str, date_iso: str | None) -> tuple[bool, str | None, str | None]:
    """Return (keep, drop_reason, gov_signal) for one cleaned headline."""
    if not has_ai(title):
        return False, "no_ai_term", None
    sig = gov_signal(title, date_iso)
    m = config.EXCLUDE.search(title)
    if m and sig != "strong":
        return False, f"excluded:{m.group(0).lower()}", sig
    if sig is None and config.CENTRAL.search(title):
        return False, "central_only", None
    if sig is None:
        return False, "no_gov_term", None
    return True, None, sig


def run() -> None:
    raw = read_jsonl(DATA / "raw.jsonl")
    by_url: dict[str, dict] = {}
    for it in raw:
        if not it.get("link"):
            continue
        key = canonical_url(it["link"])
        if key in by_url:
            u = by_url[key]
            if it["query"] not in u["queries"]:
                u["queries"].append(it["query"])
            continue
        by_url[key] = {**it, "queries": [it["query"]], "canonical": key}
    unique = list(by_url.values())

    kept, dropped = [], []
    for it in unique:
        title = clean_title(it["title"], it.get("source_title", ""))
        date_iso = (it.get("published_utc") or "")[:10] or None
        keep, reason, sig = decide(title, date_iso)
        row = {
            "aid": short_hash(it["canonical"]),
            "title": title,
            "url": it["link"],
            "published_utc": it.get("published_utc"),
            "source_name": it.get("source_title", ""),
            "source_href": it.get("source_href", ""),
            "query_state": it["query_state"],
            "queries": it["queries"],
            "lang": it.get("lang", "en"),
        }
        if keep:
            kept.append({**row, "gov_signal": sig})
        else:
            dropped.append({**row, "reason": reason, "stage": "filter"})

    write_jsonl(DATA / "relevant.jsonl", kept)
    write_jsonl(DROPPED / "filter.jsonl", dropped)
    reasons = Counter(d["reason"].split(":")[0] for d in dropped)
    update_stats("filter", {
        "raw": len(raw),
        "raw_by_query_state": dict(Counter(r["query_state"] for r in raw)),
        "unique_articles": len(unique),
        "unique_by_query_state": dict(Counter(u["query_state"] for u in unique)),
        "relevant": len(kept),
        "relevant_by_query_state": dict(Counter(k["query_state"] for k in kept)),
        "dropped": dict(reasons),
    })
    log(f"raw {len(raw)} -> unique {len(unique)} -> relevant {len(kept)}; dropped {dict(reasons)}")


if __name__ == "__main__":
    run()
