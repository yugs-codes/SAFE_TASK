# Indian State AI Policy Tracker

Tracks AI-related policy activity by Indian state governments. Five focus states get a news pipeline and detailed profiles; all other states and union territories appear in a lighter overview built from a policy-instrument dataset.

**Live dashboard:** _(GitHub Pages link goes here)_

## Scope

- **Inclusion rule:** a record counts if a **state government body is the actor**, **AI is the subject**, and **there is an action** (a policy, money, an institution, a deployment, an agreement or a rule). Talk about AI with no commitment is out.
- **Focus states (deep coverage):** Karnataka, Telangana, Tamil Nadu, Uttar Pradesh, Odisha.
- **All other states and UTs (overview):** policy instruments only.
- **Time window for news:** 1 January 2025 to today.

## Schema — `data/records.csv`

One row per news event (a cluster of articles about the same announcement).

| column | meaning |
|---|---|
| `date` | ISO `YYYY-MM-DD` (IST), earliest publication date in the cluster; empty if missing |
| `state` | normalized official English name |
| `title` | headline of the representative article, " - Source" suffix removed |
| `category` | topic, see taxonomy |
| `stage` | `proposed` / `announced` / `implemented` / `unknown` (heuristic) |
| `confidence` | corroboration of coverage: `high` / `medium` / `low` |
| `confidence_note` | one line saying why the label was given |
| `num_sources` | distinct outlets in the cluster |
| `source_name` | outlet of the representative article |
| `source_url` | link to the representative article |
| `summary` | one line |
| `id` | stable short hash |
| `date_precision` | `published_day` or `missing` |
| `source_type` | `official` / `major_outlet` / `other` |
| `flags` | `multi_state`, `state_from_query` |

## Decisions

_(author)_

## Assumptions

_(author)_

## Known holes

_(author — seeded list to come)_
