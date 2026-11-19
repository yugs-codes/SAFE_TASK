"""Fail loudly if the outputs break the schema. Run last; CI runs it too."""
from __future__ import annotations

import csv
import re
import sys

import config
from common import DATA, DOCS, log, read_json

STAGES = {"proposed", "announced", "implemented", "unknown"}
CONF = {"high", "medium", "low"}
SRC = {"official", "major_outlet", "other"}


def run() -> int:
    errors: list[str] = []
    with (DATA / "records.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    names = {s["name"] for s in config.FOCUS_STATES.values()}
    ids = set()
    for r in rows:
        rid = r["id"]
        for k in ("id", "state", "title", "category", "stage", "confidence", "source_url", "date_precision"):
            if not r.get(k):
                errors.append(f"{rid}: missing {k}")
        if rid in ids:
            errors.append(f"duplicate id {rid}")
        ids.add(rid)
        if r["date"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"]):
            errors.append(f"{rid}: bad date {r['date']}")
        if not r["date"] and r["date_precision"] != "missing":
            errors.append(f"{rid}: empty date but precision {r['date_precision']}")
        if r["date"] and r["date"] < config.START_DATE:
            errors.append(f"{rid}: date before window {r['date']}")
        if r["state"] not in names:
            errors.append(f"{rid}: state not in focus list: {r['state']}")
        if r["category"] not in config.CATEGORY_LABELS:
            errors.append(f"{rid}: bad category {r['category']}")
        if r["stage"] not in STAGES:
            errors.append(f"{rid}: bad stage {r['stage']}")
        if r["confidence"] not in CONF:
            errors.append(f"{rid}: bad confidence {r['confidence']}")
        if r["source_type"] not in SRC:
            errors.append(f"{rid}: bad source_type {r['source_type']}")
    clusters = read_json(DATA / "clusters.json", {}) or {}
    for cid in clusters:
        if cid not in ids:
            errors.append(f"clusters.json key {cid} has no record")
    for oid, patch in (read_json(DATA / "overrides.json", {}) or {}).items():
        if not oid.startswith("_") and not str(patch.get("reason", "")).strip():
            errors.append(f"override {oid} has no reason")
    if not (DOCS / "data.js").exists():
        errors.append("docs/data.js missing")
    if errors:
        log("\n".join(errors[:50]))
        log(f"\nvalidate: {len(errors)} problems")
        return 1
    log(f"validate: ok ({len(rows)} records)")
    return 0


if __name__ == "__main__":
    sys.exit(run())
