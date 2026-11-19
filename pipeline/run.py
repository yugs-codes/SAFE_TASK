"""Run the whole pipeline.

usage:
  python pipeline/run.py              # collect live (cached responses are reused), then every stage
  python pipeline/run.py --offline    # skip collection; start from the committed data/raw.jsonl
  python pipeline/run.py --from dedupe
"""
from __future__ import annotations

import sys

import classify
import collect
import dedupe
import export
import filter as relevance
import instruments
import normalize
import validate
from common import DATA, log

STAGES = [
    ("collect", lambda: collect.run(use_cache=True)),
    ("filter", relevance.run),
    ("normalize", normalize.run),
    ("dedupe", dedupe.run),
    ("classify", classify.run),
    ("instruments", instruments.run),
    ("export", export.run),
]


def main(argv: list[str]) -> int:
    names = [n for n, _ in STAGES]
    start = 0
    if "--offline" in argv:
        if not (DATA / "raw.jsonl").exists():
            log("--offline needs data/raw.jsonl")
            return 1
        start = 1
    if "--from" in argv:
        stage = argv[argv.index("--from") + 1]
        if stage not in names:
            log(f"unknown stage {stage}; choose from {names}")
            return 1
        start = names.index(stage)
    for name, fn in STAGES[start:]:
        log(f"\n== {name}")
        fn()
    log("\n== validate")
    return validate.run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
