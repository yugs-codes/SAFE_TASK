"""Normalise state and date.

State comes from the headline text, not from the query that found it (see states.py).
Dates are converted from the feed's UTC timestamp to an IST calendar date; a missing
date stays missing. Items dated before the window start are dropped.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

import config
import states
from common import DATA, DROPPED, IST, domain_of, log, read_jsonl, update_stats, write_jsonl


def ist_date(published_utc: str | None) -> tuple[str, str]:
    """Return (YYYY-MM-DD in IST, date_precision)."""
    if not published_utc:
        return "", "missing"
    dt = datetime.fromisoformat(published_utc)
    return dt.astimezone(IST).date().isoformat(), "published_day"


def run() -> None:
    rows = read_jsonl(DATA / "relevant.jsonl")
    out, dropped = [], []
    for r in rows:
        date, precision = ist_date(r.get("published_utc"))
        if date and date < config.START_DATE:
            dropped.append({**r, "reason": "out_of_window", "stage": "normalize"})
            continue
        code, flags, reason = states.assign(r["title"], r["query_state"])
        if reason:
            dropped.append({**r, "reason": reason, "stage": "normalize"})
            continue
        out.append({
            "aid": r["aid"],
            "title": r["title"],
            "url": r["url"],
            "date": date,
            "date_precision": precision,
            "state_code": code,
            "state": config.FOCUS_STATES[code]["name"],
            "flags": flags,
            "source_name": r["source_name"],
            "source_href": r["source_href"],
            "source_domain": domain_of(r["source_href"]) if r["source_href"] else "",
            "query_state": r["query_state"],
            "queries": r["queries"],
            "lang": r.get("lang", "en"),
        })
    write_jsonl(DATA / "normalized.jsonl", out)
    write_jsonl(DROPPED / "normalize.jsonl", dropped)
    reasons = Counter(d["reason"] for d in dropped)
    update_stats("normalize", {
        "in_scope": len(out),
        "in_scope_by_state": dict(Counter(o["state_code"] for o in out)),
        "flags": dict(Counter(f for o in out for f in o["flags"])),
        "missing_dates": sum(1 for o in out if o["date_precision"] == "missing"),
        "dropped": dict(reasons),
    })
    log(f"relevant {len(rows)} -> in scope {len(out)}; dropped {dict(reasons)}")


if __name__ == "__main__":
    run()
