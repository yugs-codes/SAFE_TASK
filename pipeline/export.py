"""Write the deliverables: data/records.csv, data/funnel.json, docs/data.json and docs/data.js."""
from __future__ import annotations

import csv
import json
import shutil

import config
from audit import wilson
from common import AUDIT, DATA, DOCS, log, now_ist, read_json, read_jsonl, write_json

COLUMNS = ["date", "state", "title", "category", "stage", "confidence", "confidence_note", "num_sources",
           "source_name", "source_url", "summary", "id", "date_precision", "source_type", "flags", "hand_check"]


def _labelled(name: str, col: str) -> list[dict]:
    path = AUDIT / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if (r.get(col) or "").strip().lower() in ("y", "n")]


def hand_checks() -> tuple[dict, dict]:
    """Per-record results of the manual audit, and the sample-level summary for the site."""
    yes = lambda r, c: (r.get(c) or "").strip().lower() == "y"  # noqa: E731
    no = lambda r, c: (r.get(c) or "").strip().lower() == "n"  # noqa: E731

    def rate(rows, ok):
        k, n = sum(1 for r in rows if ok(r)), len(rows)
        lo, hi = wilson(k, n)
        return {"k": k, "n": n, "lo": round(lo, 3), "hi": round(hi, 3)}

    kept = _labelled("sample_kept.csv", "is_relevant")
    per = {}
    for r in kept:
        if no(r, "is_relevant"):
            status = "wrong"
        elif no(r, "state_correct") or no(r, "category_correct"):
            status = "partly"
        else:
            status = "ok"
        per[r["id"]] = {"s": status, "note": (r.get("note") or "").strip()}
    st = [r for r in kept if (r.get("state_correct") or "").strip().lower() in ("y", "n")]
    ca = [r for r in kept if (r.get("category_correct") or "").strip().lower() in ("y", "n")]
    dropped = _labelled("sample_dropped.csv", "is_relevant")
    pairs = _labelled("dedupe_borderline.csv", "same_event")
    known = _labelled("known_events.csv", "found")
    summary = {
        "sample_size": 40,
        "relevant": rate(kept, lambda r: yes(r, "is_relevant")),
        "state": rate(st, lambda r: yes(r, "state_correct")),
        "category": rate(ca, lambda r: yes(r, "category_correct")),
        "dropped_ok": rate(dropped, lambda r: no(r, "is_relevant")),
        "pairs_split_ok": rate(pairs, lambda r: no(r, "same_event")),
        "known_found": rate(known, lambda r: yes(r, "found")),
    }
    return per, summary


def funnel(stats: dict) -> dict:
    f, n, d, c = stats.get("filter", {}), stats.get("normalize", {}), stats.get("dedupe", {}), stats.get("classify", {})
    per_state = {}
    for code in config.FOCUS_STATES:
        per_state[code] = {
            "raw": f.get("raw_by_query_state", {}).get(code, 0),
            "unique_articles": f.get("unique_by_query_state", {}).get(code, 0),
            "relevant": f.get("relevant_by_query_state", {}).get(code, 0),
            "in_scope": n.get("in_scope_by_state", {}).get(code, 0),
            "events": c.get("events_by_state", {}).get(code, 0),
        }
    drops = {}
    for section in ("filter", "normalize", "classify"):
        for k, v in stats.get(section, {}).get("dropped", {}).items():
            drops[k] = drops.get(k, 0) + v
    return {
        "stages": [
            {"key": "raw", "label": "Collected", "count": f.get("raw", 0)},
            {"key": "unique_articles", "label": "Unique articles", "count": f.get("unique_articles", 0)},
            {"key": "relevant", "label": "Relevant", "count": f.get("relevant", 0)},
            {"key": "in_scope", "label": "In scope", "count": n.get("in_scope", 0)},
            {"key": "events", "label": "Events", "count": c.get("events", 0)},
        ],
        "per_state": per_state,
        "dropped": drops,
        "note": "Raw, unique and relevant are counted by the state whose query found the article; in scope and events by the state named in the headline.",
        "merges": d.get("merges", 0),
        "largest_cluster": d.get("largest_cluster", 0),
        "flags": n.get("flags", {}),
        "missing_dates": n.get("missing_dates", 0),
    }


def run() -> None:
    events = read_jsonl(DATA / "classified.jsonl")
    stats = read_json(DATA / "stats.json", {}) or {}
    inst = read_json(DATA / "instruments.json", {}) or {}
    now = now_ist()
    version = "v" + now.strftime("%Y.%m.%d")

    # Human verification: audit labels per record, and corrections made by hand.
    checks, check_summary = hand_checks()
    for e in events:
        if e.get("override_reason"):
            e["check"] = {"s": "fixed", "note": e["override_reason"]}
        elif e["id"] in checks:
            e["check"] = checks[e["id"]]
        else:
            e["check"] = None
    check_word = {"ok": "checked_ok", "partly": "checked_label_wrong", "wrong": "checked_not_relevant", "fixed": "corrected_by_hand"}

    with (DATA / "records.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for e in events:
            w.writerow([e["date"], e["state"], e["title"], e["category"], e["stage"], e["confidence"], e["confidence_note"],
                        e["num_sources"], e["source_name"], e["url"], e["summary"], e["id"], e["date_precision"],
                        e["source_type"], ";".join(e["flags"]), check_word[e["check"]["s"]] if e["check"] else ""])

    fun = funnel(stats)
    write_json(DATA / "funnel.json", {**fun, "last_updated": now.isoformat(timespec="minutes"), "version": version})

    site = {
        "version": version,
        "last_updated": now.isoformat(timespec="minutes"),
        "start_date": config.START_DATE,
        "repo_url": config.REPO_URL,
        "focus": [{"code": c, "name": s["name"]} for c, s in config.FOCUS_STATES.items()],
        "categories": config.CATEGORY_LABELS,
        "levels": inst.get("levels", {}),
        "funnel": fun,
        "states": inst.get("states", []),
        "events": [{
            "id": e["id"], "date": e["date"], "state": e["state"], "code": e["state_code"], "title": e["title"],
            "category": e["category"], "stage": e["stage"], "confidence": e["confidence"],
            "confidence_note": e["confidence_note"], "n": e["num_sources"], "source": e["source_name"],
            "url": e["url"], "summary": e["summary"], "flags": e["flags"], "st": e["source_type"], "chk": e["check"],
            "members": [{"t": m["title"], "s": m["source"], "u": m["url"], "d": m["date"]} for m in e["members"]],
        } for e in events],
        "instruments": [{
            "id": i["id"], "date": i["date"], "precision": i["date_precision"], "state": i["state"], "code": i["state_code"],
            "title": i["title"], "type": i["type"], "status": i["status"], "group": i["status_group"], "aip": i["is_ai_policy"],
            "summary": i["summary"], "url": i["source_url"], "confidence": i["confidence"], "st": i["source_type"],
            "confidence_note": i["confidence_note"], "timeline": i["timeline"],
        } for i in inst.get("instruments", [])],
        "instrument_provenance": inst.get("provenance", ""),
        "instrument_drops": stats.get("instruments", {}).get("dropped", {}),
        "hand_check": check_summary,
        "collect": {k: v for k, v in (read_json(DATA / "collect_log.json", {}) or {}).items() if k != "slices"},
    }
    DOCS.mkdir(exist_ok=True)
    # GitHub Pages serves docs/ only, so the CSV downloads live there too.
    for name in ("records.csv", "instruments.csv"):
        if (DATA / name).exists():
            shutil.copyfile(DATA / name, DOCS / name)
    write_json(DOCS / "data.json", site)
    (DOCS / "data.js").write_text("window.DATA = " + json.dumps(site, ensure_ascii=False, separators=(",", ":")) + ";\n",
                                  encoding="utf-8", newline="\n")
    log(f"exported {len(events)} events, {len(site['instruments'])} instruments ({version})")


if __name__ == "__main__":
    run()
