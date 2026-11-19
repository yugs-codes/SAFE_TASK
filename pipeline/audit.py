"""Manual audit: draw samples to label by hand, then score the labels.

usage:
  python pipeline/audit.py sample   # writes audit/sample_kept.csv, sample_dropped.csv, known_events.csv
  python pipeline/audit.py score    # reads the labelled files, writes audit/results.md

Label columns: is_relevant / state_correct / category_correct / same_event / found take y or n.
"""
from __future__ import annotations

import csv
import random
import sys
from collections import defaultdict
from math import sqrt

from common import AUDIT, DATA, DROPPED, log, now_ist, read_jsonl

SEED = 20261119


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - m, c + m


def _write(path, cols, rows):
    if path.exists():
        log(f"{path.name} exists, not overwriting (delete it to resample)")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    log(f"wrote {path.name} ({len(rows)} rows)")


def sample() -> None:
    AUDIT.mkdir(exist_ok=True)
    rnd = random.Random(SEED)
    events = read_jsonl(DATA / "classified.jsonl")
    kept = rnd.sample(events, min(40, len(events)))
    _write(AUDIT / "sample_kept.csv",
           ["id", "state", "date", "title", "category", "stage", "url", "is_relevant", "state_correct", "category_correct", "note"],
           [{**e, "url": e["url"]} for e in kept])

    dropped = read_jsonl(DROPPED / "filter.jsonl") + read_jsonl(DROPPED / "normalize.jsonl")
    by_reason = defaultdict(list)
    for d in dropped:
        by_reason[d["reason"].split(":")[0]].append(d)
    picks = []
    per = max(1, 20 // max(1, len(by_reason)))
    for reason, rows in sorted(by_reason.items()):
        picks += [{**r, "reason": r["reason"]} for r in rnd.sample(rows, min(per, len(rows)))]
    _write(AUDIT / "sample_dropped.csv", ["aid", "reason", "query_state", "title", "url", "is_relevant", "note"], picks[:24])
    _write(AUDIT / "known_events.csv", ["state", "event", "date", "found", "record_id"], [
        {"state": "Odisha", "event": "Cabinet approves Odisha AI Policy 2025", "date": "2025-05-28"},
    ])


def _labels(path, col):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if (r.get(col) or "").strip().lower() in ("y", "n")]


def _pct(k, n):
    if n == 0:
        return "not labelled yet"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.0%} (95% CI {lo:.0%}–{hi:.0%})"


def score() -> None:
    kept = _labels(AUDIT / "sample_kept.csv", "is_relevant")
    rel = sum(r["is_relevant"].strip().lower() == "y" for r in kept)
    st = [r for r in kept if (r.get("state_correct") or "").strip().lower() in ("y", "n")]
    ca = [r for r in kept if (r.get("category_correct") or "").strip().lower() in ("y", "n")]
    dropped = _labels(AUDIT / "sample_dropped.csv", "is_relevant")
    misses = defaultdict(lambda: [0, 0])
    for r in dropped:
        k = r["reason"].split(":")[0]
        misses[k][1] += 1
        misses[k][0] += r["is_relevant"].strip().lower() == "y"
    pairs = _labels(AUDIT / "dedupe_borderline.csv", "same_event")
    known = _labels(AUDIT / "known_events.csv", "found")

    lines = [
        "# Audit results", "",
        f"Scored {now_ist().date().isoformat()}. Intervals are 95% Wilson intervals.", "",
        "| Measure | Result |", "|---|---|",
        f"| Precision of kept events | {_pct(rel, len(kept))} |",
        f"| State correct (kept sample) | {_pct(sum(r['state_correct'].strip().lower() == 'y' for r in st), len(st))} |",
        f"| Category correct (kept sample) | {_pct(sum(r['category_correct'].strip().lower() == 'y' for r in ca), len(ca))} |",
        f"| Dropped items that were relevant (misses) | {_pct(sum(v[0] for v in misses.values()), len(dropped))} |",
        f"| Borderline pairs that were the same event | {_pct(sum(r['same_event'].strip().lower() == 'y' for r in pairs), len(pairs))} |",
        f"| Recall spot-check (known events found) | {_pct(sum(r['found'].strip().lower() == 'y' for r in known), len(known))} |",
        "", "## Misses by drop reason", "", "| Reason | Relevant / labelled |", "|---|---|",
    ] + [f"| {k} | {v[0]}/{v[1]} |" for k, v in sorted(misses.items())]
    (AUDIT / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log("\n".join(lines))


if __name__ == "__main__":
    {"sample": sample, "score": score}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: log(__doc__))()
