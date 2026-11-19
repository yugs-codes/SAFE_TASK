"""Collapse articles about the same announcement into one event.

Pass 1 (identical canonical URL) already happened in filter.py.
Pass 2: same state, within +/-3 days of a cluster member, similar distinctive title,
no conflicting organisations, no proposed-vs-done conflict, and a cluster may not
span more than 7 days. Borderline pairs go to audit/dedupe_borderline.csv and every
decision to data/dedupe_report.txt.
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from datetime import date

from rapidfuzz import fuzz

import config
import states
from classify import TIER, source_type_of, stage_of
from common import AUDIT, DATA, canonical_url, log, read_json, read_jsonl, short_hash, update_stats, write_json, write_jsonl

_STATE_WORDS = {w.lower() for s in config.FOCUS_STATES.values() for n in s["names"] + s["cities"] for w in re.findall(r"[A-Za-z]+", n)}
_STATE_WORDS |= {w.lower() for n in states.NAMES.values() for w in re.findall(r"[A-Za-z]+", n)}
_ORG_RX = [(o, re.compile(r"(?<![A-Za-z])" + re.escape(o) + r"(?![A-Za-z])", re.I)) for o in config.ORGS]


def distinctive(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return " ".join(w for w in words if w not in config.GENERIC_WORDS and w not in _STATE_WORDS)


def orgs(title: str) -> set[str]:
    return {o for o, rx in _ORG_RX if rx.search(title)}


def similarity(a: dict, b: dict) -> tuple[float, float]:
    """(score, threshold) on distinctive titles."""
    da, db = a["_dist"], b["_dist"]
    if len(da.split()) >= config.MIN_TOKENS and len(db.split()) >= config.MIN_TOKENS:
        return fuzz.token_set_ratio(da, db), config.TOKEN_SET_MIN
    return fuzz.ratio(da, db), config.RATIO_MIN


_DECISION = re.compile(config.DECISION_VERBS, re.I)
_REVERSAL = re.compile(config.REVERSAL, re.I)


def guard(a: dict, b: dict) -> str | None:
    """Reason two similar titles must not merge, or None."""
    oa, ob = a["_orgs"], b["_orgs"]
    if oa and ob and not (oa & ob):
        return "different organisations"
    if bool(_REVERSAL.search(a["title"])) != bool(_REVERSAL.search(b["title"])):
        return "reversal vs original"
    sa, sb = a["_stage"], b["_stage"]
    if {sa, sb} == {"proposed", "implemented"}:
        return "plan vs delivery"
    if {sa, sb} == {"proposed", "announced"}:
        decided = a if sa == "announced" else b
        if _DECISION.search(decided["title"]):
            return "plan vs decision"
    return None


def days(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def run() -> None:
    arts = read_jsonl(DATA / "normalized.jsonl")
    for a in arts:
        a["_dist"] = distinctive(a["title"])
        a["_orgs"] = orgs(a["title"])
        a["_stage"] = stage_of(a["title"])
        a["_tier"] = TIER[source_type_of(a["source_domain"])]

    clusters: list[list[dict]] = []
    merges, reviews = [], []
    by_state: dict[str, list[dict]] = {}
    for a in arts:
        by_state.setdefault(a["state_code"], []).append(a)

    for code, items in by_state.items():
        dated = sorted((a for a in items if a["date"]), key=lambda a: (a["date"], a["aid"]))
        undated = [a for a in items if not a["date"]]
        state_clusters: list[list[dict]] = []
        for a in dated:
            best = None  # (score, cluster, member)
            for cl in state_clusters:
                if days(a["date"], cl[0]["date"]) > config.CLUSTER_SPAN_DAYS:
                    continue
                for m in cl:
                    if days(a["date"], m["date"]) > config.DEDUPE_DAYS:
                        continue
                    score, thr = similarity(a, m)
                    if score >= thr:
                        why = guard(a, m)
                        if why:
                            reviews.append((score, a, m, f"blocked: {why}"))
                        elif best is None or score > best[0]:
                            best = (score, cl, m)
                    elif score >= config.BORDERLINE_MIN:
                        reviews.append((score, a, m, "below threshold"))
            if best:
                best[1].append(a)
                merges.append((best[0], a, best[2], best[1]))
            else:
                state_clusters.append([a])
        state_clusters.extend([a] for a in undated)  # undated items merge only by URL
        clusters.extend(state_clusters)

    # Stable ids: inherit the id a member had in the previous run, else hash the first-seen member.
    prev = read_json(DATA / "clusters.json", {}) or {}
    url_to_old = {canonical_url(m["url"]): cid for cid, ms in prev.items() for m in ms}
    used, events, cluster_members = set(), [], {}
    for cl in clusters:
        old = Counter(url_to_old[c] for c in (canonical_url(m["url"]) for m in cl) if c in url_to_old)
        cid = next((o for o, _ in old.most_common() if o not in used), None)
        if not cid:
            first = min(cl, key=lambda m: (m["date"] or "9999", m["aid"]))
            base, salt = canonical_url(first["url"]), 0
            cid = short_hash(base)
            while cid in used:  # an old cluster split in two: the second half gets a fresh id
                salt += 1
                cid = short_hash(f"{base}#{salt}")
        used.add(cid)
        rep = max(cl, key=lambda m: (m["_tier"], -int((m["date"] or "9999-12-31").replace("-", "")), m["aid"]))
        dated_members = [m["date"] for m in cl if m["date"]]
        members = [{"title": m["title"], "source": m["source_name"], "domain": m["source_domain"], "url": m["url"], "date": m["date"]}
                   for m in sorted(cl, key=lambda m: (m["date"] or "9999", m["aid"]))]
        outlets = {m["source_name"] or m["source_domain"] for m in cl}
        events.append({
            "id": cid,
            "state_code": rep["state_code"],
            "state": rep["state"],
            "date": min(dated_members) if dated_members else "",
            "date_precision": "published_day" if dated_members else "missing",
            "title": rep["title"],
            "url": rep["url"],
            "source_name": rep["source_name"],
            "source_domain": rep["source_domain"],
            "num_sources": len(outlets),
            "num_articles": len(cl),
            "flags": sorted({f for m in cl for f in m["flags"]}),
            "lang": rep["lang"],
            "members": members,
        })
        cluster_members[cid] = members
        for m in cl:
            m["_cid"] = cid

    events.sort(key=lambda e: (e["date"] or "0000", e["id"]), reverse=True)
    write_jsonl(DATA / "deduped.jsonl", events)
    write_json(DATA / "clusters.json", cluster_members)

    lines = [f"# dedupe report: {len(arts)} articles -> {len(events)} events", ""]
    for score, a, m, _cl in sorted(merges, key=lambda x: x[1]["_cid"]):
        lines.append(f'MERGED {a["_cid"]} ({score:.0f}): "{a["title"]}"  <=  "{m["title"]}"')
    lines.append("")
    seen = set()
    AUDIT.mkdir(exist_ok=True)
    # Keep hand labels from the previous file, keyed by the pair of titles.
    old_labels = {}
    if (AUDIT / "dedupe_borderline.csv").exists():
        with (AUDIT / "dedupe_borderline.csv").open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("same_event") or "").strip():
                    old_labels[frozenset((r["title_a"], r["title_b"]))] = r["same_event"].strip()
    with (AUDIT / "dedupe_borderline.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["score", "note", "state", "date_a", "title_a", "date_b", "title_b", "same_event"])
        for score, a, m, note in sorted(reviews, key=lambda x: -x[0]):
            key = tuple(sorted((a["aid"], m["aid"])))
            if key in seen or a.get("_cid") == m.get("_cid"):
                continue
            seen.add(key)
            lines.append(f'REVIEW ({score:.0f}, {note}): "{a["title"]}"  ~  "{m["title"]}"')
            w.writerow([f"{score:.0f}", note, a["state"], a["date"], a["title"], m["date"], m["title"],
                        old_labels.get(frozenset((a["title"], m["title"])), "")])
    (DATA / "dedupe_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    update_stats("dedupe", {
        "articles": len(arts),
        "events": len(events),
        "events_by_state": dict(Counter(e["state_code"] for e in events)),
        "merges": len(merges),
        "borderline_pairs": len(seen),
        "largest_cluster": max((e["num_articles"] for e in events), default=0),
    })
    log(f"in scope {len(arts)} -> events {len(events)}; {len(merges)} merges, {len(seen)} borderline pairs")


if __name__ == "__main__":
    run()
