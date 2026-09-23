import json
from pathlib import Path

from career_quest.dataset import build_scenario, load_base_dataset
from career_quest.engine import build_snapshot, simulate

FIXTURE = Path(__file__).with_name("fixtures_continue_repro.json")


def _scenario():
    data = json.loads(FIXTURE.read_text("utf-8"))
    return build_scenario(load_base_dataset(), {"name": "continue", **data})


def test_route_counts_only_remaining_hours_of_started_course():
    # EV_018 is 24 h and 75% done, so only 6 h remain
    snap = build_snapshot(_scenario(), "E9007", {})
    best = snap["plan"]["best"]
    first = best["steps"][0]
    assert first["event_id"] == "EV_018" and first["action_kind"] == "continue"
    later = sum(_scenario().events[s["event_id"]].duration_hours for s in best["steps"][1:])
    assert best["effort_hours"] == 6 + later


def test_simulation_of_started_course_matches_route():
    ds = _scenario()
    snap = build_snapshot(ds, "E9007", {})
    route_finish = snap["plan"]["best"]["steps"][0]["estimated_finish"]
    sim = simulate(ds, "E9007", {}, ["EV_018"])
    assert sim["total_effort_hours"] == 6
    assert sim["steps"][0]["estimated_finish"] == route_finish
