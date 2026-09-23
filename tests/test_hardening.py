import copy
import json
from dataclasses import replace
from datetime import date

import pytest
from fastapi.testclient import TestClient
from test_core import _mini_dataset, _rec

import api.index as api
from career_quest.dataset import (
    ValidationError,
    build_scenario,
    load_base_dataset,
    validate_scenario,
)
from career_quest.engine import build_snapshot, effective_completions, employee_records, simulate
from career_quest.hr import participation


def completion(event_id, **extra):
    return {"employee_id": "T001", "event_id": event_id, "gaming": True, **extra}


def assert_ignored(ds, completions):
    before = build_snapshot(ds, "T001", {})
    overlay = {"completions": completions}
    after = build_snapshot(ds, "T001", overlay)
    assert effective_completions(ds, "T001", overlay) == []
    for key in ("skills", "readiness", "history", "gamification", "fingerprint", "health"):
        assert after[key] == before[key], key
    assert participation(ds, overlay) == participation(ds, {})


@pytest.mark.parametrize(
    "change",
    [
        {"mandatory": True},
        {"target_roles": ["Other role"]},
        {"target_grades": ["Lead"]},
        {"prerequisites": {"SK_PY": 5}},
        {"upcoming_sessions": []},
    ],
)
def test_blocked_new_completion_is_ignored_everywhere(change):
    ds = _mini_dataset([])
    ds.events["EV_SD"] = replace(ds.events["EV_SD"], **change)
    assert_ignored(ds, [completion("EV_SD")])


@pytest.mark.parametrize("session", ["2026-09-20", "2026-10-21", "2027-10-20"])
@pytest.mark.parametrize("event_id", ["EV_SD", "EV_036"])
def test_completion_rejects_unavailable_session(event_id, session):
    ds = _mini_dataset([])
    ds.events[event_id] = replace(ds.events["EV_SD"], event_id=event_id)
    assert_ignored(ds, [completion(event_id, session_date=session)])


def test_prerequisites_use_only_preceding_effective_completions():
    ds = _mini_dataset([])
    ds.events["EV_PS"] = replace(ds.events["EV_PS"], prerequisites={"SK_SD": 3})
    blocked, bridge = completion("EV_PS"), completion("EV_SD")
    reverse = {"completions": [blocked, bridge]}
    forward = {"completions": [bridge, blocked]}
    assert [c["event_id"] for c in effective_completions(ds, "T001", reverse)] == ["EV_SD"]
    assert [c["event_id"] for c in effective_completions(ds, "T001", forward)] == [
        "EV_SD",
        "EV_PS",
    ]
    retried = {"completions": [blocked, bridge, blocked]}
    expected = build_snapshot(ds, "T001", forward)
    actual = build_snapshot(ds, "T001", retried)
    assert expected["gamification"]["xp"] == 40
    for key in ("skills", "history", "gamification", "fingerprint"):
        assert actual[key] == expected[key]


def test_rejected_completion_does_not_unlock_later_completion():
    ds = _mini_dataset([])
    ds.events["EV_SD"].mandatory = True
    ds.events["EV_PS"].prerequisites = {"SK_SD": 3}
    assert_ignored(ds, [completion("EV_SD"), completion("EV_PS")])


def test_continue_keeps_historical_admission_without_upcoming_session():
    ds = _mini_dataset([_rec("R1", "EV_SD", date(2026, 9, 1), "in_progress")])
    ds.events["EV_SD"] = replace(
        ds.events["EV_SD"],
        target_roles=["Other role"],
        target_grades=["Lead"],
        prerequisites={"SK_PY": 5},
        upcoming_sessions=[],
    )
    overlay = {"completions": [completion("EV_SD")]}
    snap = build_snapshot(ds, "T001", overlay)
    assert len(effective_completions(ds, "T001", overlay)) == 1
    assert snap["gamification"]["xp"] == 20
    assert next(s["current"] for s in snap["skills"] if s["skill_id"] == "SK_SD") == 3


def test_closed_in_progress_record_cannot_bypass_current_admission():
    ds = _mini_dataset(
        [
            _rec("R1", "EV_SD", date(2026, 9, 1), "in_progress"),
            _rec("R2", "EV_SD", date(2026, 9, 2), "dropped"),
        ]
    )
    ds.events["EV_SD"].prerequisites = {"SK_PY": 5}
    assert_ignored(ds, [completion("EV_SD")])


def test_mandatory_source_continuation_keeps_progress_without_game_rewards():
    ds = _mini_dataset([_rec("R1", "EV_SD", date(2026, 9, 1), "in_progress")])
    ds.events["EV_SD"] = replace(ds.events["EV_SD"], mandatory=True, target_roles=[])
    overlay = {"completions": [completion("EV_SD")]}
    snap = build_snapshot(ds, "T001", overlay)
    assert len(effective_completions(ds, "T001", overlay)) == 1
    assert next(s["current"] for s in snap["skills"] if s["skill_id"] == "SK_SD") == 3
    assert snap["gamification"]["xp"] == 0
    assert all(b["progress"] == 0 for b in snap["gamification"]["badges"])
    row = participation(ds, overlay)[0]
    assert row["counts"]["app_completed"] == 1
    assert row["completion_share"] is None


def test_source_history_is_not_revalidated_and_can_unlock_new_completion():
    ds = _mini_dataset([_rec("R1", "EV_SD", date(2026, 9, 1), "completed")])
    ds.events["EV_SD"] = replace(ds.events["EV_SD"], mandatory=True, target_roles=[])
    ds.events["EV_PS"].prerequisites = {"SK_SD": 3}
    overlay = {"completions": [completion("EV_PS")]}
    snap = build_snapshot(ds, "T001", overlay)
    assert len(employee_records(ds, "T001", overlay)) == 2
    assert next(s["current"] for s in snap["skills"] if s["skill_id"] == "SK_SD") == 3
    assert snap["gamification"]["xp"] == 20


def test_audit_blocked_overlay_does_not_change_real_profile():
    ds = load_base_dataset()
    before = build_snapshot(ds, "E0001", {})
    overlay = {"completions": [{"employee_id": "E0001", "event_id": "EV_006", "gaming": True}]}
    after = build_snapshot(ds, "E0001", overlay)
    for key in ("skills", "history", "gamification", "fingerprint"):
        assert after[key] == before[key]
    assert participation(ds, overlay) == participation(ds, {})


def recurring_dataset():
    ds = _mini_dataset([])
    ds.employees["T001"]["skills"] = {"SK_PS": 0}
    ds.role_profiles[("Backend Engineer", "Senior")] = ({"SK_PS": 3}, ["SK_PS"])
    ds.events = {
        "EV_036": replace(
            ds.events["EV_PS"],
            event_id="EV_036",
            upcoming_sessions=[date(2026, 10, 8), date(2026, 10, 22), date(2026, 11, 5)],
        )
    }
    return ds


def test_route_repeats_club_only_for_distinct_future_sessions():
    ds = recurring_dataset()
    snap = build_snapshot(ds, "T001", {})
    plan = snap["plan"]
    assert plan["status"] == "target_reached_in_plan"
    assert [(s["event_id"], s["session"]) for s in plan["best"]["steps"]] == [
        ("EV_036", "2026-10-08"),
        ("EV_036", "2026-10-22"),
        ("EV_036", "2026-11-05"),
    ]
    projected = simulate(ds, "T001", {}, ["EV_036"] * 3)
    assert plan["best"]["skills_after"] == projected["after"]["skills"]
    assert plan["best"]["effort_hours"] == projected["total_effort_hours"]


def test_route_skips_used_session_and_never_repeats_other_events():
    ds = recurring_dataset()
    ds.role_profiles[("Backend Engineer", "Senior")] = ({"SK_PS": 4}, ["SK_PS"])
    ds.events["EV_PS"] = replace(ds.events["EV_036"], event_id="EV_PS")
    overlay = {"completions": [completion("EV_036", session_date="2026-10-08")]}
    plan = build_snapshot(ds, "T001", overlay)["plan"]
    assert plan["status"] == "target_reached_in_plan"
    keys = [(s["event_id"], s["session"]) for s in plan["best"]["steps"]]
    assert len(keys) == len(set(keys))
    assert ("EV_036", "2026-10-08") not in keys
    assert sum(eid == "EV_PS" for eid, _ in keys) == 1


def test_club_continuation_consumes_only_its_registered_session():
    ds = recurring_dataset()
    ds.history = [
        replace(
            _rec("R1", "EV_036", date(2026, 9, 1), "in_progress"),
            session_date=date(2026, 10, 8),
        )
    ]
    later = completion("EV_036", session_date="2026-10-22")
    # A new participation is blocked while the registered one is still active.
    assert_ignored(ds, [later])
    continuation = completion("EV_036")
    overlay = {"completions": [continuation, later, continuation, later]}
    accepted = effective_completions(ds, "T001", overlay)
    assert [c["session_date"] for c in accepted] == ["2026-10-08", "2026-10-22"]
    assert build_snapshot(ds, "T001", overlay)["gamification"]["xp"] == 40


def test_club_continuation_bypasses_admission_only_for_original_session():
    ds = recurring_dataset()
    ds.history = [_rec("R1", "EV_036", date(2026, 9, 1), "in_progress")]
    ds.events["EV_036"].target_roles = []
    assert_ignored(ds, [completion("EV_036", session_date="2026-10-08")])
    overlay = {"completions": [completion("EV_036")]}
    assert effective_completions(ds, "T001", overlay)[0]["session_date"] == "2026-09-01"
    assert build_snapshot(ds, "T001", overlay)["gamification"]["xp"] == 20


def test_route_can_continue_club_then_use_a_different_session():
    ds = recurring_dataset()
    ds.history = [
        replace(
            _rec("R1", "EV_036", date(2026, 9, 1), "in_progress"),
            session_date=date(2026, 10, 8),
            completion_pct=50,
        )
    ]
    plan = build_snapshot(ds, "T001", {})["plan"]
    assert plan["status"] == "target_reached_in_plan"
    steps = plan["best"]["steps"]
    assert steps[0]["action_kind"] == "continue"
    assert [s["session"] for s in steps[1:]] == ["2026-10-22", "2026-11-05"]
    assert plan["best"]["effort_hours"] == 20


def test_single_club_session_cannot_be_reused_to_reach_target():
    ds = recurring_dataset()
    ds.events["EV_036"].upcoming_sessions = [date(2026, 10, 8)]
    plan = build_snapshot(ds, "T001", {})["plan"]
    assert plan["status"] == "partial_progress"
    assert len(plan["best"]["steps"]) == 1


def test_future_demo_sessions_count_once_and_do_not_advance_dataset_date():
    ds = recurring_dataset()
    first = completion("EV_036", session_date="2026-10-08")
    second = completion("EV_036", session_date="2026-10-22")
    overlay = {"completions": [first, first, second, second]}
    before = copy.deepcopy(ds)
    snap = build_snapshot(ds, "T001", overlay)
    assert next(s["current"] for s in snap["skills"] if s["skill_id"] == "SK_PS") == 2
    assert snap["gamification"]["xp"] == 40
    assert participation(ds, overlay)[0]["counts"] == {"completed": 2, "app_completed": 2}
    assert all(r.date == ds.as_of for r in employee_records(ds, "T001", overlay))
    assert ds == before


def test_rejected_completion_does_not_shift_gaming_flags():
    ds = _mini_dataset([])
    ds.events["EV_PS"].prerequisites = {"SK_SD": 5}
    expected = build_snapshot(ds, "T001", {"completions": [completion("EV_SD")]})
    overlay = {"completions": [completion("EV_PS", gaming=False), completion("EV_SD")]}
    after = build_snapshot(ds, "T001", overlay)
    assert expected["gamification"]["xp"] == 20
    for key in ("skills", "history", "gamification", "fingerprint"):
        assert after[key] == expected[key]


def test_skills_from_completions_on_review_day_do_not_unlock_other_events():
    ds = _mini_dataset([])
    ds.employees["T001"]["last_review_date"] = ds.as_of.isoformat()
    ds.events["EV_PS"].prerequisites = {"SK_SD": 3}
    overlay = {"completions": [completion("EV_SD"), completion("EV_PS")]}
    assert [c["event_id"] for c in effective_completions(ds, "T001", overlay)] == ["EV_SD"]
    snap = build_snapshot(ds, "T001", overlay)
    assert next(s["current"] for s in snap["skills"] if s["skill_id"] == "SK_SD") == 2
    assert snap["gamification"]["xp"] == 0


INVALID_PROFILE_FIELDS = [
    ("skills", [], "BAD_SKILLS"),
    ("skills", [1], "BAD_SKILLS"),
    ("career_goal", "Senior", "BAD_CAREER_GOAL"),
    ("employee_id", "", "BAD_EMPLOYEE_ID"),
    ("employee_id", "   ", "BAD_EMPLOYEE_ID"),
    ("skills", {"SK_SYSTEM_DESIGN": True}, "LEVEL_OUT_OF_RANGE"),
    ("skills", {"SK_SYSTEM_DESIGN": False}, "LEVEL_OUT_OF_RANGE"),
    ("manager_id", "E0028", "SELF_MANAGER"),
]


@pytest.mark.parametrize(("field", "value", "code"), INVALID_PROFILE_FIELDS)
def test_import_edge_forms_return_structured_errors(field, value, code):
    base = load_base_dataset()
    employee = {**copy.deepcopy(base.employees["E0028"]), field: value}
    errors, _ = validate_scenario(base, [employee], [])
    matching = [e for e in errors if e["code"] == code]
    assert matching
    assert matching[0]["path"].startswith(f"employees[0].{field}")
    assert isinstance(matching[0]["detail"], str)
    with pytest.raises(ValidationError) as exc:
        build_scenario(base, {"employees": [employee]})
    assert exc.value.errors == errors


@pytest.mark.parametrize(("field", "value", "code"), INVALID_PROFILE_FIELDS)
def test_import_edge_forms_return_http_report_without_500(field, value, code):
    employee = {**load_base_dataset().employees["E0028"], field: value}
    with TestClient(api.app, raise_server_exceptions=False) as client:
        login = client.post("/api/py/auth/login", json={"login": "hr", "password": "hr-demo"})
        assert login.status_code == 200
        response = client.post(
            "/api/py/hr/import/validate",
            headers={"Authorization": f"Bearer {login.json()['token']}"},
            files={
                "files": (
                    "employees.json",
                    json.dumps({"employees": [employee]}),
                    "application/json",
                )
            },
        )
    assert response.status_code == 200
    report = response.json()
    assert report["ok"] is False
    assert report["scenario"] is None
    assert any(e["code"] == code for e in report["errors"])
