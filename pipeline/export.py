"""Write the deliverables: data/records.csv, data/funnel.json, docs/data.json and docs/data.js."""
from __future__ import annotations

import csv
import json
import shutil

import config
from common import DATA, DOCS, log, now_ist, read_json, read_jsonl, write_json

COLUMNS = ["date", "state", "title", "category", "stage", "confidence", "confidence_note", "num_sources",
           "source_name", "source_url", "summary", "id", "date_precision", "source_type", "flags"]


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

    with (DATA / "records.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for e in events:
            w.writerow([e["date"], e["state"], e["title"], e["category"], e["stage"], e["confidence"], e["confidence_note"],
                        e["num_sources"], e["source_name"], e["url"], e["summary"], e["id"], e["date_precision"],
                        e["source_type"], ";".join(e["flags"])])

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
            "url": e["url"], "summary": e["summary"], "flags": e["flags"], "st": e["source_type"],
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
