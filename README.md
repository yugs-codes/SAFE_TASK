# Indian State AI Policy Tracker

Tracks AI-related policy activity by Indian state governments, in two layers:

- **News events** for five focus states (Karnataka, Telangana, Tamil Nadu, Uttar Pradesh, Odisha), collected from Google News RSS by a re-runnable Python pipeline, filtered, normalised, deduplicated and labelled.
- **Policy instruments** (Acts, policies, missions, guidelines) for every state and union territory, used for the all-states overview and each state's AI-policy status.

**Live dashboard:** _(add the GitHub Pages URL here)_ · **Datasets:** [`data/records.csv`](data/records.csv) (news events) · [`data/instruments.csv`](data/instruments.csv) (policy instruments)

## Quick start

Python 3.12. No API keys.

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python pipeline/run.py --offline  # rebuild everything from the committed snapshot (no network)
python pipeline/run.py            # collect fresh news first (~240 requests, ~7 min), then rebuild
python -m pytest -q tests         # normalisation and filter tests

python -m http.server 8000 --directory docs   # dashboard at http://localhost:8000
```

`docs/index.html` also opens directly from disk: the page reads `docs/data.js`, not a fetched JSON file.

Other entry points: `python pipeline/run.py --from dedupe` restarts mid-pipeline; `python pipeline/audit.py sample|score` runs the manual audit.

## Current snapshot (collected 19 Nov 2026)

| Stage | Items |
|---|---|
| Collected (241 RSS slices) | 3,434 |
| Unique articles | 2,361 |
| Relevant (AI term + state-government signal) | 818 |
| In scope (a focus state, dated 2025 or later) | 772 |
| Events after dedupe | 657 |

- Events by state: Karnataka 187, Uttar Pradesh 155, Tamil Nadu 121, Telangana 117, Odisha 77.
- Dropped: no AI term 853, no state-government signal 667, another state 46, central government only 22, private-sector phrase 1.
- Dedupe: 115 merges, largest cluster 14 articles, 287 borderline pairs for review.
- Confidence: high 27, medium 423, low 207. Stage: proposed 171, announced 140, implemented 91, unclear 255.
- Flags: `state_from_query` 84 (no state named in the headline), `multi_state` 4. No missing dates.
- Recall example: Odisha's AI Policy cabinet approval (28 May 2025) is found, but as **two** events (TOI, 28 May, "State cabinet approves policy for implementing AI…"; New Indian Express, 29 May, "Odisha clears AI policy…"): their headlines share too few words to merge.

## Scope

- **Inclusion rule:** a record counts if a **state government body is the actor**, **AI is the subject**, and **there is an action** (a policy, money, an institution, a deployment, an agreement or a rule).
- **Focus states:** Karnataka, Telangana, Tamil Nadu (high activity: test precision and dedupe), Uttar Pradesh (name variants and a Hindi query), Odisha (low-coverage contrast, with a known event: the cabinet approved the Odisha AI Policy 2025 on 28 May 2025).
- **News window:** 1 January 2025 to the run date, IST.
- **All other states and UTs:** policy-instrument layer only.

## Pipeline

Each stage reads the previous stage's file and writes its own, so every count in the funnel can be traced.

| Stage | File | Writes | What it does |
|---|---|---|---|
| collect | `pipeline/collect.py` | `data/raw.jsonl`, `data/collect_log.json` | 6 query variants × 5 states × 8 quarters (`after:`/`before:`), monthly when a quarter is full; responses cached in `data/cache/` |
| filter | `pipeline/filter.py` | `data/relevant.jsonl`, `data/dropped/filter.jsonl` | Collapses the same article found by several queries; keeps headlines with an AI term and a state-government signal |
| normalize | `pipeline/normalize.py` | `data/normalized.jsonl`, `data/dropped/normalize.jsonl` | State from the headline (not the query); UTC → IST date; drops other states and pre-2025 items |
| dedupe | `pipeline/dedupe.py` | `data/deduped.jsonl`, `data/clusters.json`, `data/dedupe_report.txt`, `audit/dedupe_borderline.csv` | Clusters articles about the same announcement |
| classify | `pipeline/classify.py` | `data/classified.jsonl`, `data/dropped/override.jsonl` | Category, stage, source type, confidence and its note; applies `data/overrides.json` |
| instruments | `pipeline/instruments.py` | `data/instruments.json`, `data/instruments.csv`, `data/dropped/instruments.jsonl` | Filters the instrument snapshot to state-level AI instruments; derives each state's AI-policy status |
| export | `pipeline/export.py` | `data/records.csv`, `data/funnel.json`, `docs/data.json`, `docs/data.js`, CSV copies in `docs/` | Deliverables |
| validate | `pipeline/validate.py` | — | Fails the run on schema problems |

All rules and thresholds are in `pipeline/config.py`.

### Filter rules

- **AI term:** `AI`, `A.I.`, `GenAI` (case-sensitive, so never inside another word), artificial intelligence, machine learning, generative AI, deepfake, chatbot, LLM; Hindi एआई, आर्टिफिशियल इंटेलिजेंस, कृत्रिम बुद्धिमत्ता, डीपफेक (substring match, because regex word boundaries fail on Devanagari vowel signs).
- **State-government signal:** strong terms (government, govt, CM, chief minister, minister, cabinet, department, police, collector, assembly, state agencies such as KDEM, ELCOT, TNeGA, OCAC; the sitting Chief Minister's name, date-bounded), or a weak term (policy, mission, MoU, budget, scheme) together with a state name.
- **Dropped:** private-sector phrases (share price, funding round, IPO, layoffs …) unless a strong government term is present; central-government-only news (IndiaAI, MeitY, Union government, PM Modi …) with no state-government signal. Bare "Centre" is never used, because it matches "Centre of Excellence".

### State and date normalisation

- Names and cities are matched on a letters-only key over 1–3-word windows, so "Uttar Pradesh", "Uttar-Pradesh" and "UttarPradesh" are the same; `UP`, `U.P.`, `TN`, `T.N.` are matched case-sensitively as whole tokens, so "sets up" is never Uttar Pradesh. `MP` and `AP` are never used.
- A state name counts 2, a city 1, "{state} govt" adds 1. The heaviest focus state wins; if another state outweighs every focus state, the item is dropped. Ties go to the state whose query found the item; several focus states → flag `multi_state`; none → the query's state with flag `state_from_query`.
- Dates: the feed's UTC timestamp → IST calendar day (`published_day`). Missing dates stay empty (`missing`), never the collection date.

### Deduplication

Same state, within ±3 days of a cluster member, and similar *distinctive* words (state names and generic words removed): `token_set_ratio ≥ 85` when both titles have 3+ distinctive words, else `ratio ≥ 90`. Two titles never merge if they name different organisations (Microsoft vs Google) or if one is proposed and the other announced/implemented. A cluster spans at most 7 days. The representative article is the highest source tier (official > major outlet > other), then the earliest. Every merge is listed in `data/dedupe_report.txt`; near-misses (score 70+) go to `audit/dedupe_borderline.csv`. Record ids are stable: a cluster keeps the id one of its articles had in the previous run.

## Schema — `data/records.csv` (news events)

| column | meaning |
|---|---|
| `date` | ISO `YYYY-MM-DD` (IST), earliest publication date in the cluster; empty if missing |
| `state` | official English name |
| `title` | headline of the representative article, " - Source" removed |
| `category` | `regulation_ethics`, `budget_funding`, `policy_mission`, `institution`, `partnership_mou`, `skilling`, `governance_deployment`, `other` (first matching keyword rule wins, in this order) |
| `stage` | `proposed` / `announced` / `implemented` / `unknown` (keyword-based; future markers such as "to launch" are checked first) |
| `confidence` | corroboration of coverage: `high` = official source or 3+ outlets; `medium` = a major outlet or 2 outlets; `low` = one non-major outlet |
| `confidence_note` | why the label was given, e.g. "3 outlets: The Hindu, Deccan Herald, ET; no official source" |
| `num_sources` | distinct outlets in the cluster |
| `source_name`, `source_url` | representative article (a Google News link) |
| `summary` | one line built from the labels (the feed carries no article text) |
| `id` | stable short hash |
| `date_precision` | `published_day` or `missing` |
| `source_type` | `official` (gov.in / nic.in) / `major_outlet` (allow-list incl. regional English outlets) / `other` |
| `flags` | `multi_state`, `state_from_query` |

All articles in each cluster are in `data/clusters.json`.

## Schema — `data/instruments.csv` (policy instruments)

`state, date, date_precision (day/month/year), title, type, status, binding, issuing_body, summary, source_url, source_type, confidence, confidence_note, id`. A state's map level is: **3** an AI policy, mission or strategy adopted; **2** one drafted or announced; **1** other AI measures only; **0** nothing found.

### Data provenance

`data/instruments/source/policies.json` is a research snapshot (v2026.11.19) of 279 Union and state instruments compiled from official documents and press reports, with AI research assistance, by _(credit the source here)_. This project uses it as-is and filters it: Union-level records (145), court instruments (2), a placeholder record (1) and AI-adjacent records with no AI content (8) are excluded, leaving 123 state/UT instruments. Its dates and links were not re-verified record by record here; a sample of 16 links resolved.

## Audit

```bash
python pipeline/audit.py sample   # audit/sample_kept.csv (40 events), sample_dropped.csv (stratified by reason), known_events.csv
python pipeline/audit.py score    # writes audit/results.md with 95% Wilson intervals
```

Label `y`/`n` in `is_relevant`, `state_correct`, `category_correct` (kept), `is_relevant` (dropped), `same_event` (borderline pairs), `found` (known events). A wrong record that no rule change can fix goes into `data/overrides.json` with a reason.

## Updates

`.github/workflows/update.yml` runs daily at 08:00 IST: tests → full pipeline → if anything was collected, a pull request labelled `data-review` instead of a direct commit, so a person checks new records first.

## Deploy

GitHub Pages → Settings → Pages → Deploy from branch → `main` / `docs`. To show "report a correction" links, set `REPO_URL` in `pipeline/config.py` and re-run `python pipeline/run.py --offline`.

## Decisions

_(author: write in your own words — the inclusion line and its edge cases, why these five states, why Google News RSS, why two layers)_

## Assumptions

_(author)_

## Known holes

_(author: edit; seeded list)_

- English headlines only, apart from one Hindi query for Uttar Pradesh; Kannada, Telugu, Tamil and Odia press is missing, which hurts the low-coverage state most.
- News dates are publication dates, not event dates.
- No article text is fetched (Google News redirect links, paywalls), so category, stage and summary come from the headline; `source_url` is a Google News link, not the publisher URL.
- Google News RSS returns at most ~100 items per query; quarterly slicing and query variants are a partial fix, and Google's ranking is opaque.
- The news layer has no official state sources, so the `official` tier is almost empty and `high` confidence mostly means 3+ outlets.
- Syndicated wire copy inflates `num_sources`; confidence measures corroboration of coverage, not truth.
- Stage detection is keyword-based and noisy.
- Relevance rules are keyword-based; audited precision is in `audit/results.md`.
- Rules that use Chief Ministers' names expire: two focus states changed CM in 2026.
- A re-run on another day returns different articles; the committed `data/raw.jsonl` is the reproducible snapshot.
- The instrument layer is a third-party research snapshot; it is not refreshed by the pipeline.
