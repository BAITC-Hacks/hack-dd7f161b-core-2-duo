import copy
from dataclasses import replace
from datetime import date

import pytest

from career_quest.dataset import load_base_dataset
from career_quest.engine import build_snapshot, employee_records, simulate


def test_duplicate_completion_keeps_skills_rewards_history_and_fingerprint():
    ds = load_base_dataset()
    completion = {"employee_id": "E0001", "event_id": "EV_005", "gaming": True}
    one = build_snapshot(ds, "E0001", {"completions": [completion]})
    duplicate = build_snapshot(ds, "E0001", {"completions": [completion, completion]})
    assert one["gamification"]["xp"] == 20
    for key in ("skills", "history", "gamification", "fingerprint"):
        assert duplicate[key] == one[key]


def test_source_completion_cannot_be_reclaimed_for_rewards_or_change_fingerprint():
    ds = load_base_dataset()
    before = build_snapshot(ds, "E0028", {})
    again = build_snapshot(
        ds,
        "E0028",
        {"completions": [{"employee_id": "E0028", "event_id": "EV_006", "gaming": True}]},
    )
    for key in ("skills", "history", "gamification", "fingerprint"):
        assert again[key] == before[key]


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        "invalid",
        [],
        {},
        {"employee_id": "E0001", "event_id": "missing"},
        {"employee_id": "E0001", "event_id": []},
        {"employee_id": "E0001", "event_id": "EV_005", "session_date": "bad-date"},
        {"employee_id": "E0001", "event_id": "EV_005", "session_date": 42},
        {"employee_id": "E0001", "event_id": "EV_036"},
    ],
)
def test_invalid_completion_is_ignored_in_all_employee_state(invalid):
    ds = load_base_dataset()
    before = build_snapshot(ds, "E0001", {})
    after = build_snapshot(ds, "E0001", {"completions": [invalid]})
    for key in ("skills", "history", "gamification", "fingerprint"):
        assert after[key] == before[key]


def test_invalid_and_duplicate_entries_do_not_shift_reward_opt_in():
    ds = load_base_dataset()
    completion = {"employee_id": "E0001", "event_id": "EV_005", "gaming": True}
    expected = build_snapshot(ds, "E0001", {"completions": [completion]})
    after_invalid = build_snapshot(
        ds,
        "E0001",
        {"completions": [{"employee_id": "E0001", "event_id": "missing"}, completion]},
    )
    assert after_invalid["gamification"] == expected["gamification"]
    assert after_invalid["fingerprint"] == expected["fingerprint"]
    opted_out = {**completion, "gaming": False}
    no_rewards = build_snapshot(ds, "E0001", {"completions": [opted_out]})
    duplicate_opt_in = build_snapshot(ds, "E0001", {"completions": [opted_out, completion]})
    assert no_rewards["gamification"]["xp"] == 0
    assert duplicate_opt_in["gamification"] == no_rewards["gamification"]
    assert duplicate_opt_in["fingerprint"] == no_rewards["fingerprint"]


def test_repeatable_completion_counts_once_per_session_across_source_and_app():
    ds = copy.deepcopy(load_base_dataset())
    ds.employees["E0001"]["skills"]["SK_PUBLIC_SPEAKING"] = 0
    source = replace(
        ds.history[0],
        employee_id="E0001",
        event_id="EV_036",
        date=date(2026, 9, 20),
        status="completed",
        completion_pct=100,
        session_date=None,
    )
    ds.history = [source]
    first = {
        "employee_id": "E0001",
        "event_id": "EV_036",
        "session_date": "2026-10-08",
        "gaming": True,
    }
    second = {**first, "session_date": "2026-10-22"}
    overlay = {
        "completions": [
            {**first, "session_date": "2026-09-20"},
            first,
            first,
            second,
            second,
        ]
    }
    records = employee_records(ds, "E0001", overlay)
    assert len(records) == 3
    assert [r.session_date for r in records if r.origin == "app"] == [
        date(2026, 10, 8),
        date(2026, 10, 22),
    ]
    snap = build_snapshot(ds, "E0001", overlay)
    skill = next(s for s in snap["skills"] if s["skill_id"] == "SK_PUBLIC_SPEAKING")
    assert skill["current"] == 3
    assert snap["gamification"]["xp"] == 40
    assert snap["gamification"]["badges"][1]["progress"] == 2


def test_fingerprint_depends_on_source_history_content():
    ds = copy.deepcopy(load_base_dataset())
    before = build_snapshot(ds, "E0028", {})
    index = next(i for i, r in enumerate(ds.history) if r.record_id == "R002692")
    ds.history[index] = replace(ds.history[index], status="no_show", completion_pct=0)
    after = build_snapshot(ds, "E0028", {})
    assert before["readiness"] != after["readiness"]
    assert before["fingerprint"] != after["fingerprint"]


def test_repeatable_completion_advances_recommendation_route_and_simulation():
    ds = load_base_dataset()
    first = {
        "employee_id": "E0005",
        "event_id": "EV_036",
        "session_date": "2026-10-08",
        "gaming": True,
    }
    overlay = {"completions": [first]}
    snap = build_snapshot(ds, "E0005", overlay)
    recommendation = next(c for c in snap["shortlist"] if c["event_id"] == "EV_036")
    assert recommendation["session"] == "2026-10-22"
    assert recommendation["path"]["steps"][0]["session"] == "2026-10-22"
    projection = simulate(ds, "E0005", overlay, ["EV_036"])
    assert projection["steps"][0]["estimated_start"] == "2026-10-22"

    second = {**first, "session_date": recommendation["session"]}
    after = build_snapshot(ds, "E0005", {"completions": [first, second]})
    skill = next(s for s in after["skills"] if s["skill_id"] == "SK_PUBLIC_SPEAKING")
    assert skill["current"] == 2
    assert after["gamification"]["xp"] == 40


def test_repeatable_completion_exhausts_available_sessions():
    ds = copy.deepcopy(load_base_dataset())
    ds.events["EV_036"].upcoming_sessions = [date(2026, 10, 8)]
    overlay = {
        "completions": [
            {"employee_id": "E0005", "event_id": "EV_036", "session_date": "2026-10-08"}
        ]
    }
    snap = build_snapshot(ds, "E0005", overlay)
    activity = next(c for c in snap["catalog"] if c["event_id"] == "EV_036")
    assert activity["eligible"] is False
    assert activity["session"] is None
    assert {r["code"] for r in activity["reasons"]} == {"NO_UPCOMING_SESSION"}
    assert all(c["event_id"] != "EV_036" for c in snap["shortlist"])
    projection = simulate(ds, "E0005", overlay, ["EV_036"])
    assert projection["error"]["code"] == "STEP_BLOCKED"
    assert {r["code"] for r in projection["error"]["reasons"]} == {"NO_UPCOMING_SESSION"}
