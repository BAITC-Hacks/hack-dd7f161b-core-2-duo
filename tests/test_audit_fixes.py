import copy

from career_quest.dataset import build_scenario, load_base_dataset, validate_scenario
from career_quest.engine import build_snapshot
from career_quest.hr import participation


def _skill(snap, sid):
    return next(s for s in snap["skills"] if s["skill_id"] == sid)["current"]


def test_duplicate_completion_counts_once():
    ds = load_base_dataset()
    one = {"completions": [{"employee_id": "E0001", "event_id": "EV_005"}]}
    two = {"completions": [{"employee_id": "E0001", "event_id": "EV_005"}] * 2}
    assert _skill(build_snapshot(ds, "E0001", one), "SK_SYSTEM_DESIGN") == _skill(
        build_snapshot(ds, "E0001", two), "SK_SYSTEM_DESIGN"
    )


def test_completion_of_already_completed_event_is_ignored():
    ds = load_base_dataset()
    base = build_snapshot(ds, "E0028", {})
    # EV_006 was completed in the source history (R002692)
    again = build_snapshot(
        ds, "E0028", {"completions": [{"employee_id": "E0028", "event_id": "EV_006"}]}
    )
    assert _skill(again, "SK_SYSTEM_DESIGN") == _skill(base, "SK_SYSTEM_DESIGN")


def _scenario(skill_level: int) -> dict:
    ds = load_base_dataset()
    emp = copy.deepcopy(ds.employees["E0028"])
    emp["skills"]["SK_SYSTEM_DESIGN"] = skill_level
    return {"name": "same-name", "employees": [emp], "history": []}


def test_fingerprint_depends_on_profile_content():
    base = load_base_dataset()
    a = build_snapshot(build_scenario(base, _scenario(2)), "E0028", {})
    b = build_snapshot(build_scenario(base, _scenario(0)), "E0028", {})
    assert a["fingerprint"] != b["fingerprint"]


def test_validator_rejects_values_the_engine_cannot_parse():
    base = load_base_dataset()
    emp = copy.deepcopy(base.employees["E0028"])
    emp["last_review_date"] = None
    errors, _ = validate_scenario(base, [emp], [])
    assert any(e["code"] == "BAD_DATE" for e in errors)

    emp = copy.deepcopy(base.employees["E0028"])
    row = {
        "record_id": "X1",
        "employee_id": "E0028",
        "event_id": "EV_005",
        "date": "2026-05-01",
        "due_date": "not-a-date",
        "status": "completed",
        "completion_pct": "100",
        "score": "abc",
        "feedback_rating": "9",
        "assigned_by": "self",
    }
    errors, _ = validate_scenario(base, [emp], [row])
    codes = {e["code"] for e in errors}
    assert {"BAD_DATE", "BAD_SCORE", "BAD_FEEDBACK"} <= codes


def test_bridge_coverage_only_when_path_improves_that_skill():
    ds = load_base_dataset()
    snap = build_snapshot(ds, "E0002", {})
    for cov in snap["coverage"]:
        if cov["status"] != "bridge":
            continue
        improving = [
            c
            for c in snap["shortlist"]
            if c["bridge"]
            and (c["path"] or {}).get("skills_after", {}).get(cov["skill_id"], 0) > cov["current"]
        ]
        assert improving, f"{cov['skill_id']} marked bridge without an improving path"


def test_participation_counts_app_completions_consistently():
    ds = load_base_dataset()
    before = next(r for r in participation(ds, {}) if r["event_id"] == "EV_005")
    overlay = {"completions": [{"employee_id": "E0001", "event_id": "EV_005"}] * 2}
    after = next(r for r in participation(ds, overlay) if r["event_id"] == "EV_005")
    assert after["counts"]["completed"] == before["counts"]["completed"] + 1
    assert after["completion_share"] > before["completion_share"]
