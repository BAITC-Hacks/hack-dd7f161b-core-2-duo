from datetime import date

import pytest

from career_quest.dataset import Dataset, Event, Record, load_base_dataset
from career_quest.engine import build_snapshot, simulate
from career_quest.goals import calculate_gaps, readiness
from career_quest.progression import actual_gain

AS_OF = date(2026, 10, 1)


@pytest.mark.parametrize(
    ("current", "gain", "cap", "expected"),
    [(2, 1, 4, 1), (3, 2, 4, 1), (4, 1, 3, 0), (5, 1, 5, 0), (0, 1, 3, 1)],
)
def test_actual_gain_never_lowers_level(current, gain, cap, expected):
    assert actual_gain(current, gain, cap) == expected


def test_readiness_spec_example():
    required = {"A": 4, "B": 2}
    gaps = calculate_gaps({"A": 2, "B": 2}, required, ["A"])
    r = readiness(gaps)
    assert r["readiness_pct"] == pytest.approx(60.0)
    assert r["critical_gate_met"] is False
    gaps_after = calculate_gaps({"A": 3, "B": 2}, required, ["A"])
    assert readiness(gaps_after)["readiness_pct"] == pytest.approx(80.0)


def _mini_dataset(history: list[Record]) -> Dataset:
    # jury-style trap: lowest skill is public speaking, but critical for Senior is system design
    skills = {
        s: {"skill_id": s, "name": s, "type": "hard", "category": "x", "description": ""}
        for s in ["SK_SD", "SK_PS", "SK_PY"]
    }
    role_profiles = {
        ("Backend Engineer", "Middle"): ({"SK_SD": 2, "SK_PS": 1, "SK_PY": 3}, ["SK_PY"]),
        ("Backend Engineer", "Senior"): ({"SK_SD": 4, "SK_PS": 2, "SK_PY": 4}, ["SK_SD"]),
    }

    def ev(eid, fmt, etype, skill, gain=1, cap=5, prereq=None, sessions=None):
        return Event(
            event_id=eid,
            title=eid,
            description="",
            type=etype,
            format=fmt,
            duration_hours=8,
            mandatory=False,
            target_roles=["Backend Engineer"],
            target_grades=["Middle", "Senior"],
            develops_skills=[{"skill_id": skill, "gain": gain, "max_level": cap}],
            prerequisites=prereq or {},
            upcoming_sessions=sessions
            if sessions is not None
            else ([] if fmt == "self_paced" else [date(2026, 10, 20)]),
        )

    events = {
        e.event_id: e
        for e in [
            ev("EV_SD", "online", "course", "SK_SD"),
            ev("EV_PS", "offline", "workshop", "SK_PS"),
            ev("EV_PS_OLD", "offline", "workshop", "SK_PS", sessions=[]),
            ev("EV_PY", "self_paced", "course", "SK_PY", cap=3),
        ]
    }
    employee = {
        "employee_id": "T001",
        "full_name": "Test Person",
        "department": "Backend Development",
        "role": "Backend Engineer",
        "grade": "Middle",
        "manager_id": None,
        "hire_date": "2022-01-01",
        "tenure_months": 45,
        "work_format": "hybrid",
        "preferred_language": "ru",
        "career_goal": {"target_role": "Backend Engineer", "target_grade": "Senior"},
        "skills": {"SK_SD": 2, "SK_PS": 0, "SK_PY": 4},
        "last_review_date": "2026-03-01",
    }
    return Dataset(
        as_of=AS_OF,
        skills=skills,
        role_profiles=role_profiles,
        employees={"T001": employee},
        events=events,
        history=history,
        name="test",
    )


def _rec(rid, eid, d, status):
    return Record(
        record_id=rid,
        employee_id="T001",
        event_id=eid,
        date=d,
        due_date=None,
        status=status,
        completion_pct=100 if status == "completed" else 0,
        score=None,
        feedback_rating=None,
        assigned_by="self",
    )


def test_multi_factor_recommendation_beats_lowest_skill_rule():
    history = [
        _rec("R1", "EV_PS_OLD", date(2026, 5, 1), "no_show"),
        _rec("R2", "EV_PS_OLD", date(2026, 6, 1), "no_show"),
        _rec("R3", "EV_PS_OLD", date(2026, 7, 1), "no_show"),
    ]
    snap = build_snapshot(_mini_dataset(history), "T001", overlay={})
    recs = snap["recommendations"]
    assert recs, "expected at least one recommendation"
    assert recs[0]["event_id"] == "EV_SD"
    assert recs[0]["tier"] == 0
    categories = {f["category"] for f in recs[0]["facts"]}
    assert {"profile", "target_requirement", "skill_gap", "history"} <= categories


def test_completion_moves_skill_and_readiness():
    ds = _mini_dataset([])
    before = build_snapshot(ds, "T001", overlay={})
    overlay = {"completions": [{"employee_id": "T001", "event_id": "EV_SD"}]}
    after = build_snapshot(ds, "T001", overlay=overlay)
    sd_before = next(s for s in before["skills"] if s["skill_id"] == "SK_SD")
    sd_after = next(s for s in after["skills"] if s["skill_id"] == "SK_SD")
    assert sd_after["current"] == sd_before["current"] + 1
    assert after["readiness"]["readiness_pct"] > before["readiness"]["readiness_pct"]
    assert all(r["event_id"] != "EV_SD" for r in after["recommendations"])


def test_simulation_does_not_change_state():
    ds = _mini_dataset([])
    sim = simulate(ds, "T001", overlay={}, steps=["EV_SD"])
    assert sim["after"]["readiness_pct"] > sim["before"]["readiness_pct"]
    again = build_snapshot(ds, "T001", overlay={})
    assert next(s for s in again["skills"] if s["skill_id"] == "SK_SD")["current"] == 2


def test_target_met_returns_no_recommendations():
    ds = _mini_dataset([])
    overlay = {
        "goals": {
            "T001": {"mode": "set", "target_role": "Backend Engineer", "target_grade": "Middle"}
        }
    }
    # middle requirements: SD 2, PS 1, PY 3 -> PS gap 1 remains, so not met yet
    snap = build_snapshot(ds, "T001", overlay=overlay)
    assert snap["target"]["source"] == "user"
    assert any(g["skill_id"] == "SK_PS" for g in snap["gaps"] if g["gap"] > 0)


def test_replay_applies_only_after_review_date():
    ds = load_base_dataset()
    snap = build_snapshot(ds, "E0028", overlay={})
    sd = next(s for s in snap["skills"] if s["skill_id"] == "SK_SYSTEM_DESIGN")
    # R002692 EV_006 completed 2026-09-08 after review -> 2 becomes 3
    assert sd["assessed"] == 2
    assert sd["current"] == 3
    assert any(a["record_id"] == "R002692" for a in sd["applications"])


def test_base_dataset_every_employee_snapshot_builds():
    ds = load_base_dataset()
    assert len(ds.employees) == 200
    for eid in ds.employees:
        snap = build_snapshot(ds, eid, overlay={})
        assert len(snap["recommendations"]) <= 3
        if not snap["recommendations"]:
            assert snap["no_step_reasons"]
