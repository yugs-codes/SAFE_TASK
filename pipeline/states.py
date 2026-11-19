"""State detection, shared by filter.py and normalize.py.

Names and cities are matched on a letters-only key over 1..N-word windows, so spacing,
hyphens and case don't matter. Abbreviations (UP, TN) are matched case-sensitively as
whole tokens, so "sets up" never becomes Uttar Pradesh. Hindi names are matched as
substrings because regex word boundaries break on Devanagari vowel signs.
"""
from __future__ import annotations

import re

import config
from common import DATA, read_json

STATE_NAME_W = 2
CITY_W = 1
GOVT_BONUS = 1


def letters_key(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


_JUR = read_json(DATA / "instruments" / "source" / "jurisdictions.json", [])
NAMES: dict[str, str] = {j["code"]: j["name"] for j in _JUR if j["code"] != "IN"}
for _c, _s in config.FOCUS_STATES.items():
    NAMES[_c] = _s["name"]
FOCUS = list(config.FOCUS_STATES)

# letters-only key -> (code, weight)
ALIASES: dict[str, tuple[str, int]] = {}


def _add(alias: str, code: str, w: int) -> None:
    k = letters_key(alias)
    if k and k not in ALIASES:
        ALIASES[k] = (code, w)


for _c, _s in config.FOCUS_STATES.items():
    for n in _s["names"]:
        _add(n, _c, STATE_NAME_W)
    for n in _s["cities"]:
        _add(n, _c, CITY_W)
for _c, _n in NAMES.items():
    if _c not in config.FOCUS_STATES:
        _add(_n, _c, STATE_NAME_W)
for _c, _ns in config.OTHER_STATE_EXTRA_NAMES.items():
    for n in _ns:
        _add(n, _c, STATE_NAME_W)
for _c, _ns in config.OTHER_STATE_CITIES.items():
    for n in _ns:
        _add(n, _c, CITY_W)

_MAX_WORDS = max(len(re.findall(r"[A-Za-z]+", a)) for a in
                 [n for s in config.FOCUS_STATES.values() for n in s["names"] + s["cities"]] + list(NAMES.values()))
_ABBR = {c: re.compile(r"(?<![A-Za-z.])(" + "|".join(re.escape(a) for a in s["abbr"]) + r")(?![A-Za-z])")
         for c, s in config.FOCUS_STATES.items() if s["abbr"]}
_GOVT_AFTER = {c: re.compile(r"\b(" + "|".join(re.escape(n) for n in s["names"]) + r")\s*(govt|government|cabinet|police|CM)\b", re.I)
               for c, s in config.FOCUS_STATES.items()}
_DATELINE = re.compile(r"\bNew Delhi\b")


def detect(text: str) -> dict[str, int]:
    """Return {state_code: weight} for every state or UT mentioned in the text."""
    text = _DATELINE.sub(" ", text or "")
    w: dict[str, int] = {}
    toks = re.findall(r"[A-Za-z]+", text)
    i = 0
    while i < len(toks):
        hit = None
        for n in range(min(_MAX_WORDS, len(toks) - i), 0, -1):
            k = "".join(t.lower() for t in toks[i:i + n])
            if k in ALIASES:
                hit = (n, ALIASES[k])
                break
        if hit:
            n, (code, weight) = hit
            w[code] = w.get(code, 0) + weight
            i += n
        else:
            i += 1
    for code, rx in _ABBR.items():
        cnt = len(rx.findall(text))
        if cnt:
            w[code] = w.get(code, 0) + STATE_NAME_W * cnt
    for code, s in config.FOCUS_STATES.items():
        for n in s["hindi"]:
            if n in text:
                w[code] = w.get(code, 0) + STATE_NAME_W
        for n in s["hindi_cities"]:
            if n in text:
                w[code] = w.get(code, 0) + CITY_W
        if _GOVT_AFTER[code].search(text):
            w[code] = w.get(code, 0) + GOVT_BONUS
    return w


def mentions_any_state(text: str) -> bool:
    return bool(detect(text))


def assign(text: str, query_state: str) -> tuple[str | None, list[str], str | None]:
    """Pick the acting state from the text, not the query.

    Returns (state_code, flags, drop_reason). drop_reason is set when only an
    out-of-scope state is mentioned, or when one outweighs every focus state.
    """
    w = detect(text)
    focus = {c: v for c, v in w.items() if c in config.FOCUS_STATES}
    other = {c: v for c, v in w.items() if c not in config.FOCUS_STATES}
    if not focus:
        if other:
            return None, [], "out_of_scope_state"
        return query_state, ["state_from_query"], None
    top_w = max(focus.values())
    if other and max(other.values()) > top_w:
        return None, [], "out_of_scope_state"
    top = [c for c in FOCUS if focus.get(c) == top_w]
    code = query_state if query_state in top else top[0]
    flags = ["multi_state"] if len(focus) > 1 else []
    return code, flags, None


_ACTOR_NAMES = re.compile(
    r"\b(" + "|".join(re.escape(n) for s in config.FOCUS_STATES.values() for n in s["names"]) + r")('s)?\s+" + config.STATE_ACTOR_VERBS + r"\b",
    re.I,
)
_ACTOR_ABBR = re.compile(
    r"(?<![A-Za-z.])(" + "|".join(re.escape(a) for s in config.FOCUS_STATES.values() for a in s["abbr"]) + r")('s)?\s+(?i:" + config.STATE_ACTOR_VERBS + r")\b"
)


def state_as_actor(text: str) -> bool:
    """'Karnataka signs ...', 'UP to back ...': the state's name stands for its government."""
    return bool(_ACTOR_NAMES.search(text or "") or _ACTOR_ABBR.search(text or ""))


def cm_mentioned(text: str, date_iso: str | None) -> bool:
    """A sitting Chief Minister of a focus state is named (date-bounded)."""
    for name, _code, start, end in config.CHIEF_MINISTERS:
        if re.search(r"\b" + re.escape(name) + r"\b", text or ""):
            if not date_iso:
                return True
            if date_iso >= start and (end is None or date_iso < end):
                return True
    return False
