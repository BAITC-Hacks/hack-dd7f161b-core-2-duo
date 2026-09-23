import copy
from datetime import date

import pytest

from career_quest.dataset import (
    ValidationError,
    build_scenario,
    load_base_dataset,
    validate_scenario,
)


@pytest.fixture
def scenario():
    base = load_base_dataset()
    return {
        "employees": [copy.deepcopy(base.employees["E0028"])],
        "history": [
            {
                "record_id": "IMPORT1",
                "employee_id": "E0028",
                "event_id": "EV_005",
                "date": "2026-05-01",
                "due_date": "2026-06-01",
                "status": "completed",
                "completion_pct": "100",
                "score": "100",
                "feedback_rating": "5",
            }
        ],
    }


@pytest.mark.parametrize("field", ["last_review_date", "date"])
@pytest.mark.parametrize("value", [None, "", "2026-02-30", "not-a-date", 20260501, False, []])
def test_required_dates_reject_unparseable_values(scenario, field, value):
    target = scenario["employees"][0] if field == "last_review_date" else scenario["history"][0]
    target[field] = value
    expected_path = "employees[0]" if field == "last_review_date" else "activity_history.csv:2"

    with pytest.raises(ValidationError) as exc:
        build_scenario(load_base_dataset(), scenario)

    assert any(
        error["code"] == "BAD_DATE" and error["path"] == expected_path for error in exc.value.errors
    )


@pytest.mark.parametrize("field", ["last_review_date", "date"])
def test_missing_required_dates_report_bad_date(scenario, field):
    target = scenario["employees"][0] if field == "last_review_date" else scenario["history"][0]
    del target[field]

    with pytest.raises(ValidationError) as exc:
        build_scenario(load_base_dataset(), scenario)

    assert any(error["code"] == "BAD_DATE" for error in exc.value.errors)


@pytest.mark.parametrize(
    ("field", "code", "value"),
    [
        ("due_date", "BAD_DATE", "not-a-date"),
        ("due_date", "BAD_DATE", "2026-02-30"),
        ("due_date", "BAD_DATE", 20260601),
        ("due_date", "BAD_DATE", []),
        ("score", "BAD_SCORE", -1),
        ("score", "BAD_SCORE", "101"),
        ("score", "BAD_SCORE", "abc"),
        ("score", "BAD_SCORE", "99.5"),
        ("score", "BAD_SCORE", 99.5),
        ("score", "BAD_SCORE", 100.0),
        ("score", "BAD_SCORE", True),
        ("score", "BAD_SCORE", []),
        ("feedback_rating", "BAD_FEEDBACK", "0"),
        ("feedback_rating", "BAD_FEEDBACK", 6),
        ("feedback_rating", "BAD_FEEDBACK", "abc"),
        ("feedback_rating", "BAD_FEEDBACK", "4.5"),
        ("feedback_rating", "BAD_FEEDBACK", 4.5),
        ("feedback_rating", "BAD_FEEDBACK", 5.0),
        ("feedback_rating", "BAD_FEEDBACK", True),
        ("feedback_rating", "BAD_FEEDBACK", {}),
    ],
)
def test_invalid_optional_fields_report_code_and_csv_line(scenario, field, code, value):
    invalid_row = copy.deepcopy(scenario["history"][0])
    invalid_row["record_id"] = "IMPORT2"
    invalid_row[field] = value
    scenario["history"].append(invalid_row)

    errors, _ = validate_scenario(load_base_dataset(), scenario["employees"], scenario["history"])

    assert any(
        error["code"] == code and error["path"] == "activity_history.csv:3" for error in errors
    )


@pytest.mark.parametrize("field", ["due_date", "score", "feedback_rating"])
@pytest.mark.parametrize("empty", [None, "", "missing"])
def test_optional_fields_can_be_empty(scenario, field, empty):
    if empty == "missing":
        del scenario["history"][0][field]
    else:
        scenario["history"][0][field] = empty

    imported = build_scenario(load_base_dataset(), scenario)

    assert getattr(imported.history[0], field) is None


@pytest.mark.parametrize("score", [0, "0", 100, "100"])
@pytest.mark.parametrize("rating", [1, "1", 5, "5"])
def test_optional_integer_boundaries_build_scenario(scenario, score, rating):
    scenario["history"][0].update(score=score, feedback_rating=rating)

    imported = build_scenario(load_base_dataset(), scenario)

    assert imported.history[0].score == int(score)
    assert imported.history[0].feedback_rating == int(rating)
    assert imported.history[0].date == date(2026, 5, 1)
    assert imported.history[0].due_date == date(2026, 6, 1)
