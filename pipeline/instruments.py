"""Policy-instrument layer for the all-states overview.

Reads the research snapshot in data/instruments/source/policies.json (one record per
Act, policy, mission, guideline ...), keeps state and UT instruments whose text is
about AI, and derives each state's AI-policy status for the tile map. Union-level
records and AI-adjacent ones (data-centre, gig-work, general IT policy) are dropped
with a reason, so the inclusion rule is the same as for news.
"""
from __future__ import annotations

import csv
import re
from collections import Counter

import config
from common import DATA, DROPPED, log, read_json, update_stats, write_json, write_jsonl

SOURCE = DATA / "instruments" / "source"
AI_TEXT = re.compile(r"(?<![A-Za-z])(AI|GenAI)(?![A-Za-z])|\b(artificial intelligence|machine learning|deep ?fakes?|algorithm\w*|synthetic(ally)? generated)\b", re.I)
POLICY_TYPES = {"policy", "strategy", "mission", "framework"}
STATUS_GROUP = {
    "in-force": "adopted", "adopted": "adopted",
    "draft": "in_progress", "consultation": "in_progress", "proposed": "in_progress",
    "announced": "in_progress", "pending-assent": "in_progress", "under-litigation": "in_progress",
    "lapsed": "inactive", "withdrawn": "inactive", "superseded": "inactive",
}
# Ordinal levels for the tile map.
LEVELS = {
    3: "AI policy adopted",
    2: "AI policy drafted or announced",
    1: "Other AI measures only",
    0: "Nothing found",
}
PROVENANCE = "Research snapshot v2026.11.19 (data/instruments/source)"


PLACEHOLDER = re.compile(r"closest instrument|no AI policy", re.I)
POLICY_WORDS = re.compile(r"\b(polic(y|ies)|mission|strategy|roadmap|action plan)\b", re.I)
COURT = re.compile(r"\b(high court|supreme court|court|judiciary|judicial)\b", re.I)


def is_ai(p: dict) -> bool:
    text = " ".join([p.get("title", ""), p.get("summary", ""), " ".join(p.get("key_provisions", []))])
    return bool(AI_TEXT.search(text))


def is_ai_policy(p: dict) -> bool:
    """A state-wide AI policy, mission or strategy (by type or by title)."""
    t = p["title"]
    return bool(AI_TEXT.search(t)) and (p["instrument_type"] in POLICY_TYPES or bool(POLICY_WORDS.search(t)))


def drop_reason(p: dict) -> str | None:
    if p["jurisdiction"] == "IN":
        return "union_level"
    if PLACEHOLDER.search(p["title"]):
        return "placeholder_no_ai_instrument"
    if not config.INCLUDE_JUDICIARY and (p["instrument_type"] == "court-ruling" or COURT.search(p.get("issuing_body", ""))):
        return "judiciary_not_state_executive"
    if not is_ai(p):
        return "not_ai_specific"
    return None


def run() -> None:
    src = read_json(SOURCE / "policies.json", [])
    jur = read_json(SOURCE / "jurisdictions.json", [])
    kept, dropped = [], []
    for p in src:
        reason = drop_reason(p)
        if reason:
            dropped.append({"id": p["id"], "title": p["title"], "jurisdiction": p["jurisdiction"], "reason": reason})
            continue
        if "news.google.com" in p.get("source_url", ""):
            p = {**p, "confidence": "low"}
        kept.append({
            "id": p["id"],
            "state_code": p["jurisdiction"],
            "state": p["jurisdiction_name"],
            "title": p["title"],
            "type": p["instrument_type"],
            "status": p["status"],
            "status_group": STATUS_GROUP.get(p["status"], "in_progress"),
            "is_ai_policy": is_ai_policy(p),
            "binding": p.get("binding", ""),
            "issuing_body": p.get("issuing_body", ""),
            "date": p["date"],
            "date_precision": p.get("date_precision", "day"),
            "summary": p.get("summary", ""),
            "timeline": p.get("timeline", []),
            "source_url": p.get("source_url", ""),
            "source_type": p.get("source_type", ""),
            "confidence": p.get("confidence", "low"),
            "confidence_note": p.get("confidence_note", ""),
        })
    kept.sort(key=lambda x: (x["state"], x["date"]), reverse=False)

    level, best = {}, {}
    for code in {j["code"] for j in jur if j["code"] != "IN"}:
        items = [k for k in kept if k["state_code"] == code]
        pol = [k for k in items if k["is_ai_policy"]]
        rank = lambda k: (k["type"] in POLICY_TYPES, k["date"])  # noqa: E731  prefer a real policy/mission over guidelines
        if any(k["status_group"] == "adopted" for k in pol):
            level[code] = 3
            best[code] = max((k for k in pol if k["status_group"] == "adopted"), key=rank)["title"]
        elif pol:
            level[code] = 2
            best[code] = max(pol, key=rank)["title"]
        elif items:
            level[code] = 1
            best[code] = max(items, key=lambda k: k["date"])["title"]
        else:
            level[code] = 0
            best[code] = ""
    summary = [{
        "code": j["code"], "name": j["name"], "type": j["type"], "tile": j["tile"],
        "level": level[j["code"]], "level_label": LEVELS[level[j["code"]]],
        "headline_instrument": best[j["code"]],
        "instruments": sum(1 for k in kept if k["state_code"] == j["code"]),
        "focus": j["code"] in config.FOCUS_STATES,
    } for j in jur if j["code"] != "IN"]

    write_json(DATA / "instruments.json", {"provenance": PROVENANCE, "levels": LEVELS, "states": summary, "instruments": kept})
    with (DATA / "instruments.csv").open("w", encoding="utf-8-sig", newline="") as f:
        cols = ["state", "date", "date_precision", "title", "type", "status", "binding", "issuing_body", "summary",
                "source_url", "source_type", "confidence", "confidence_note", "id"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(kept)
    write_jsonl(DROPPED / "instruments.jsonl", dropped)
    update_stats("instruments", {
        "source_records": len(src),
        "kept": len(kept),
        "states_with_instruments": sum(1 for s in summary if s["instruments"]),
        "levels": dict(Counter(LEVELS[s["level"]] for s in summary)),
        "dropped": dict(Counter(d["reason"] for d in dropped)),
    })
    log(f"instruments: {len(src)} source -> {len(kept)} state/UT AI instruments; dropped {dict(Counter(d['reason'] for d in dropped))}")


if __name__ == "__main__":
    run()
