from datetime import date

import pytest

from career_quest.dataset import Dataset, Event, Record
from career_quest.hr import participation

AS_OF = date(2026, 10, 1)


def _dataset(history=(), *, event_id="EV_001", mandatory=False, event_format="online"):
    event = Event(
        event_id=event_id,
        title="Test activity",
        description="",
        type="workshop",
        format=event_format,
        duration_hours=2,
        mandatory=mandatory,
        target_roles=[],
        target_grades=[],
        develops_skills=[],
        prerequisites={},
        upcoming_sessions=[date(2026, 9, 1), date(2026, 9, 15)],
    )
    return Dataset(
        as_of=AS_OF,
        skills={},
        role_profiles={},
        employees={eid: {"employee_id": eid} for eid in ("A", "B", "C", "D")},
        events={event_id: event},
        history=list(history),
    )


def _record(employee_id, status, *, event_id="EV_001", completed_on=date(2026, 8, 1)):
    return Record(
        record_id=f"SOURCE-{employee_id}-{completed_on}",
        employee_id=employee_id,
        event_id=event_id,
        date=completed_on,
        due_date=None,
        status=status,
        completion_pct=100 if status == "completed" else 0,
        score=None,
        feedback_rating=4 if status == "completed" else None,
        assigned_by="self",
    )


def _completion(employee_id="A", event_id="EV_001", **extra):
    return {"employee_id": employee_id, "event_id": event_id, **extra}


def test_app_completion_updates_participation_rates_and_unique_employees():
    ds = _dataset([_record("A", "completed"), _record("B", "dropped"), _record("C", "no_show")])

    row = participation(ds, {"completions": [_completion("D")]})[0]

    assert row["counts"] == {"completed": 2, "dropped": 1, "no_show": 1, "app_completed": 1}
    assert row["unique_employees"] == 4
    assert row["observations"] == 4
    assert row["completion_share"] == pytest.approx(1 / 2)
    assert row["attendance_proxy"] == pytest.approx(2 / 3)
    assert row["avg_feedback"] == 4
    assert row["feedback_n"] == 1


def test_app_completion_creates_participation_for_event_without_source_history():
    ds = _dataset()

    rows = participation(ds, {"completions": [_completion()]})

    assert len(rows) == 1
    assert rows[0]["event_id"] == "EV_001"
    assert rows[0]["counts"] == {"completed": 1, "app_completed": 1}
    assert rows[0]["observations"] == 1
    assert rows[0]["unique_employees"] == 1
    assert rows[0]["completion_share"] == 1
    assert rows[0]["attendance_proxy"] == 1
    assert rows[0]["feedback_n"] == 0
    assert rows[0]["avg_feedback"] is None


def test_app_completion_of_source_completed_activity_does_not_change_participation():
    ds = _dataset([_record("A", "completed")])
    before = participation(ds, {})

    after = participation(ds, {"completions": [_completion()]})

    assert after == before
    assert len(ds.history) == 1


def test_duplicate_app_completions_count_once_without_adding_a_second_observation():
    ds = _dataset([_record("B", "no_show")])
    completion = _completion()

    row = participation(ds, {"completions": [completion, dict(completion)]})[0]

    assert row["counts"] == {"no_show": 1, "completed": 1, "app_completed": 1}
    assert row["observations"] == 2
    assert row["unique_employees"] == 2
    assert row["completion_share"] == pytest.approx(1 / 2)
    assert row["attendance_proxy"] == pytest.approx(1 / 2)


def test_recurring_club_counts_distinct_sessions_once_including_source_history():
    ds = _dataset([_record("A", "completed", event_id="EV_036")], event_id="EV_036")
    completions = [
        _completion(event_id="EV_036", session_date="2026-08-01"),
        _completion(event_id="EV_036", session_date="2026-09-01"),
        _completion(event_id="EV_036", session_date="2026-09-01"),
        _completion(event_id="EV_036", session_date="2026-09-15"),
    ]

    row = participation(ds, {"completions": completions})[0]

    assert row["counts"] == {"completed": 3, "app_completed": 2}
    assert row["observations"] == 3
    assert row["unique_employees"] == 1
    assert row["completion_share"] == 1
    assert row["feedback_n"] == 1


def test_invalid_and_unknown_overlay_entries_do_not_affect_participation():
    ds = _dataset([_record("B", "no_show")])
    completions = [
        None,
        "invalid",
        {},
        _completion(employee_id="UNKNOWN"),
        _completion(event_id="UNKNOWN"),
        _completion(session_date="not-a-date"),
    ]

    assert participation(ds, {"completions": completions}) == participation(ds, {})
    rows = participation(ds, {"completions": [*completions, _completion()]})

    assert rows == participation(ds, {"completions": [_completion()]})


@pytest.mark.parametrize(
    ("mandatory", "event_format", "completion_share", "attendance_proxy"),
    [(True, "online", None, 1), (False, "self_paced", 1, None)],
)
def test_app_completions_preserve_metric_applicability(
    mandatory, event_format, completion_share, attendance_proxy
):
    ds = _dataset(mandatory=mandatory, event_format=event_format)

    row = participation(ds, {"completions": [_completion()]})[0]

    assert row["completion_share"] == completion_share
    assert row["attendance_proxy"] == attendance_proxy
