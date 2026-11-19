"""The brief's own example: "UP", "Uttar Pradesh" and "Uttar-Pradesh" must be one state."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))

import pytest  # noqa: E402

import states  # noqa: E402
from classify import stage_of  # noqa: E402
from common import clean_title  # noqa: E402
from filter import decide  # noqa: E402
from normalize import ist_date  # noqa: E402


@pytest.mark.parametrize("text", [
    "UP govt launches AI mission",
    "U.P. cabinet approves AI policy",
    "Uttar-Pradesh to set up AI city",
    "Uttarpradesh AI push",
    "Uttar Pradesh AI policy",
    "उत्तर प्रदेश सरकार का एआई मिशन",
    "Lucknow to get AI centre",
])
def test_uttar_pradesh_variants(text):
    code, _flags, reason = states.assign(text, query_state="KA")
    assert reason is None and code == "UP"


def test_sets_up_is_not_uttar_pradesh():
    code, flags, _ = states.assign("Telangana sets up AI task force", query_state="UP")
    assert code == "TG" and "multi_state" not in flags


@pytest.mark.parametrize("text,expected", [
    ("Orissa cabinet clears AI policy", "OD"),
    ("Tamilnadu govt signs AI MoU", "TN"),
    ("TN to launch AI mission", "TN"),
    ("Bengaluru gets AI centre of excellence", "KA"),
])
def test_aliases(text, expected):
    assert states.assign(text, query_state="UP")[0] == expected


def test_no_state_falls_back_to_query_with_flag():
    code, flags, reason = states.assign("State cabinet approves AI policy", query_state="OD")
    assert (code, flags, reason) == ("OD", ["state_from_query"], None)


def test_out_of_scope_state_is_dropped():
    assert states.assign("Maharashtra unveils AI policy", query_state="KA")[2] == "out_of_scope_state"


def test_city_of_company_does_not_beat_acting_state():
    assert states.assign("Bengaluru firm signs AI MoU with Telangana govt", query_state="KA")[0] == "TG"


def test_ist_date_rolls_over():
    assert ist_date("2025-03-10T20:00:00+00:00") == ("2025-03-11", "published_day")
    assert ist_date(None) == ("", "missing")


def test_clean_title_strips_source():
    assert clean_title("Odisha clears AI policy - The New Indian Express", "The New Indian Express") == "Odisha clears AI policy"


def test_filter_keeps_minister_sharing_roadmap():
    keep, reason, _ = decide("Karnataka IT minister shares AI roadmap", "2025-06-01")
    assert keep, reason


def test_centre_of_excellence_is_not_central():
    keep, reason, _ = decide("Odisha govt opens AI Centre of Excellence", "2025-06-01")
    assert keep, reason


def test_central_only_is_dropped():
    assert decide("MeitY announces AI compute portal in Lucknow", "2025-06-01")[1] == "central_only"


def test_future_marker_beats_launch():
    assert stage_of("TN to launch AI mission next month") == "proposed"
    assert stage_of("Telangana launches AI mission") == "implemented"


def test_first_stage_verb_wins():
    assert stage_of("Karnataka signs MoU with ElevenLabs to develop voice AI") == "announced"
    assert stage_of("Karnataka to set up AI university, announces CM") == "proposed"


def test_state_named_as_actor_counts_as_government():
    keep, reason, _ = decide("Karnataka signs agreement with five tech companies to skill 63,200 students in AI", "2026-03-01")
    assert keep, reason


def test_partial_state_name_is_out_of_scope():
    assert states.assign("Bengal Education Department deploys AI security", query_state="KA")[2] == "out_of_scope_state"


def test_dedupe_guards():
    import dedupe

    def art(t):
        return {"title": t, "_orgs": dedupe.orgs(t), "_stage": stage_of(t)}
    assert dedupe.guard(art("UP signs Rs 25,000 crore AI MoU with Puch AI"), art("UP cancels Rs 25,000 crore MoU with Puch AI"))
    assert dedupe.guard(art("Karnataka to set up AI university"), art("Karnataka announces AI university")) is None
    assert dedupe.guard(art("Odisha to frame AI policy"), art("Odisha cabinet approves AI policy"))
