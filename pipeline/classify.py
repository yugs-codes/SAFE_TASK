"""Category, stage, source type, confidence and confidence note per event; overrides applied last.

All rules are keyword rules from config.py, first match wins, so each label can be traced.
"""
from __future__ import annotations

import re
from collections import Counter

import config
from common import DATA, DROPPED, log, read_json, read_jsonl, update_stats, write_jsonl

_CATS = [(name, re.compile(rx, re.I)) for name, rx in config.CATEGORIES]
_SECTORS = [(name, re.compile(rx, re.I)) for name, rx in config.SECTORS]
_STAGES = [(name, re.compile(rx, re.I)) for name, rx in config.STAGES]
TIER = {"official": 3, "major_outlet": 2, "other": 1}


def stage_of(title: str) -> str:
    for name, rx in _STAGES:
        if rx.search(title):
            return name
    return "unknown"


def category_of(title: str) -> str:
    for name, rx in _CATS:
        if rx.search(title):
            return name
    return "other"


def sector_of(title: str) -> str | None:
    for name, rx in _SECTORS:
        if rx.search(title):
            return name
    return None


def source_type_of(domain: str) -> str:
    d = (domain or "").lower()
    if d.endswith(config.OFFICIAL_SUFFIXES):
        return "official"
    if any(d == m or d.endswith("." + m) for m in config.MAJOR_OUTLETS):
        return "major_outlet"
    return "other"


def confidence_of(members: list[dict]) -> tuple[str, str]:
    """Corroboration of coverage, not truth."""
    outlets = []
    for m in members:
        if m["source"] and m["source"] not in outlets:
            outlets.append(m["source"])
    types = [source_type_of(m.get("domain", "")) for m in members]
    n = len(outlets)
    official = [m["domain"] for m, t in zip(members, types) if t == "official"]
    if official or n >= 3:
        level = "high"
    elif "major_outlet" in types or n == 2:
        level = "medium"
    else:
        level = "low"
    names = ", ".join(outlets[:3]) + (f" and {n - 3} more" if n > 3 else "")
    if n == 1 and level == "low":
        note = f"1 outlet ({names}, not on the major-outlet list); not corroborated"
    else:
        note = f"{n} outlet{'s' if n != 1 else ''}: {names}; " + (f"official source: {official[0]}" if official else "no official source")
    return level, note


def summary_of(category: str, sector: str | None, stage: str, n: int) -> str:
    """The feed carries no article text, so the one-line summary is built from the labels."""
    label = config.CATEGORY_LABELS[category]
    if category == "governance_deployment" and sector:
        label = f"AI in {sector}"
    stage_txt = {"proposed": "proposed", "announced": "announced", "implemented": "implemented", "unknown": "stage unclear"}[stage]
    return f"{label}; {stage_txt}; reported by {n} outlet{'s' if n != 1 else ''}."


def run() -> None:
    events = read_jsonl(DATA / "deduped.jsonl")
    out = []
    for e in events:
        title = e["title"]
        cat = category_of(title)
        sector = sector_of(title)
        stage = stage_of(title)
        conf, note = confidence_of(e["members"])
        out.append({
            **e,
            "category": cat,
            "sector": sector,
            "stage": stage,
            "source_type": source_type_of(e["source_domain"]),
            "confidence": conf,
            "confidence_note": note,
            "summary": summary_of(cat, sector, stage, e["num_sources"]),
        })

    # Hand corrections keyed by stable id; every one must carry a reason.
    overrides = read_json(DATA / "overrides.json", {}) or {}
    by_id = {e["id"]: e for e in out}
    dropped, applied, unknown = [], 0, []
    for oid, patch in overrides.items():
        if oid.startswith("_"):
            continue
        e = by_id.get(oid)
        if not e:
            unknown.append(oid)
            continue
        applied += 1
        if patch.get("drop"):
            dropped.append({"id": oid, "title": e["title"], "state": e["state"], "reason": f"override: {patch.get('reason', '')}", "stage": "override"})
            del by_id[oid]
        else:
            e.update(patch.get("set", {}))
            e["override_reason"] = patch.get("reason", "")
    out = [e for e in out if e["id"] in by_id]
    for oid in unknown:
        log(f"override for unknown id {oid} (ignored)")

    write_jsonl(DATA / "classified.jsonl", out)
    write_jsonl(DROPPED / "override.jsonl", dropped)
    update_stats("classify", {
        "events": len(out),
        "events_by_state": dict(Counter(e["state_code"] for e in out)),
        "category": dict(Counter(e["category"] for e in out)),
        "stage": dict(Counter(e["stage"] for e in out)),
        "confidence": dict(Counter(e["confidence"] for e in out)),
        "overrides_applied": applied,
        "dropped": {"override": len(dropped)} if dropped else {},
    })
    log(f"classified {len(out)} events; categories {dict(Counter(e['category'] for e in out))}")


if __name__ == "__main__":
    run()
