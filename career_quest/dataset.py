import csv
import io
import json
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "dataset"

GRADES = ["Junior", "Middle", "Senior", "Lead"]
STATUSES = {"completed", "in_progress", "dropped", "no_show", "declined", "overdue"}
# dataset rule: EV_036 is a recurring club, everything else is not repeated after completion
REPEATABLE_EVENTS = {"EV_036"}


@dataclass
class Event:
    event_id: str
    title: str
    description: str
    type: str
    format: str
    duration_hours: float
    mandatory: bool
    target_roles: list[str]
    target_grades: list[str]
    develops_skills: list[dict]
    prerequisites: dict[str, int]
    upcoming_sessions: list[date]

    @property
    def scheduled(self) -> bool:
        return self.format != "self_paced"


@dataclass
class Record:
    record_id: str
    employee_id: str
    event_id: str
    date: date
    due_date: date | None
    status: str
    completion_pct: int
    score: int | None
    feedback_rating: int | None
    assigned_by: str
    origin: str = "source"
    session_date: date | None = None


@dataclass
class Dataset:
    as_of: date
    skills: dict[str, dict]
    role_profiles: dict[tuple[str, str], tuple[dict[str, int], list[str]]]
    employees: dict[str, dict]
    events: dict[str, Event]
    history: list[Record]
    name: str = "base"
    proficiency_scale: dict[str, str] = field(default_factory=dict)

    def history_of(self, employee_id: str) -> list[Record]:
        return [r for r in self.history if r.employee_id == employee_id]


class ValidationError(Exception):
    def __init__(self, errors: list[dict]):
        super().__init__(f"{len(errors)} validation errors")
        self.errors = errors


def _d(value: str | None) -> date | None:
    if value in (None, ""):
        return None
    return date.fromisoformat(value)


def _int_or_none(value: str | None) -> int | None:
    return None if value in (None, "") else int(value)


def parse_events(raw: list[dict]) -> dict[str, Event]:
    events = {}
    for e in raw:
        events[e["event_id"]] = Event(
            event_id=e["event_id"],
            title=e["title"],
            description=e.get("description", ""),
            type=e["type"],
            format=e["format"],
            duration_hours=float(e["duration_hours"]),
            mandatory=bool(e["mandatory"]),
            target_roles=list(e.get("target_roles", [])),
            target_grades=list(e.get("target_grades", [])),
            develops_skills=list(e.get("develops_skills", [])),
            prerequisites=dict(e.get("prerequisites", {})),
            upcoming_sessions=sorted(date.fromisoformat(s) for s in e.get("upcoming_sessions", [])),
        )
    return events


def parse_skills(raw: dict) -> tuple[dict, dict]:
    skills = {s["skill_id"]: s for s in raw["skills"]}
    profiles = {
        (p["role"], p["grade"]): (dict(p["required_skills"]), list(p["critical_skills"]))
        for p in raw["role_profiles"]
    }
    return skills, profiles


def parse_history_rows(rows: list[dict]) -> list[Record]:
    return [
        Record(
            record_id=r["record_id"],
            employee_id=r["employee_id"],
            event_id=r["event_id"],
            date=_d(r["date"]),
            due_date=_d(r.get("due_date")),
            status=r["status"],
            completion_pct=int(r.get("completion_pct") or 0),
            score=_int_or_none(r.get("score")),
            feedback_rating=_int_or_none(r.get("feedback_rating")),
            assigned_by=r.get("assigned_by") or "self",
        )
        for r in rows
    ]


def read_csv_text(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))


@lru_cache(maxsize=1)
def load_base_dataset() -> Dataset:
    skills_raw = json.loads((DATA_DIR / "skills.json").read_text("utf-8"))
    employees_raw = json.loads((DATA_DIR / "employees.json").read_text("utf-8"))
    events_raw = json.loads((DATA_DIR / "events.json").read_text("utf-8"))
    history_rows = read_csv_text((DATA_DIR / "activity_history.csv").read_text("utf-8"))
    skills, profiles = parse_skills(skills_raw)
    return Dataset(
        as_of=date.fromisoformat(employees_raw["meta"]["as_of_date"]),
        skills=skills,
        role_profiles=profiles,
        employees={e["employee_id"]: e for e in employees_raw["employees"]},
        events=parse_events(events_raw["events"]),
        history=parse_history_rows(history_rows),
        name="base",
        proficiency_scale=skills_raw.get("proficiency_scale", {}),
    )


def validate_scenario(
    base: Dataset, employees: list[dict], history_rows: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Validate uploaded jury profiles and history against the base catalog.

    Returns (errors, warnings); errors block the import.
    """
    errors: list[dict] = []
    warnings: list[dict] = []
    ids: set[str] = set()
    required = ["employee_id", "role", "grade", "skills", "last_review_date"]
    for i, e in enumerate(employees):
        path = f"employees[{i}]"
        missing = [k for k in required if k not in e]
        if missing:
            errors.append({"path": path, "code": "MISSING_FIELDS", "detail": ", ".join(missing)})
            continue
        eid = str(e["employee_id"])
        if eid in ids:
            errors.append({"path": path, "code": "DUPLICATE_EMPLOYEE_ID", "detail": eid})
        ids.add(eid)
        if (e["role"], e["grade"]) not in base.role_profiles:
            errors.append(
                {
                    "path": path,
                    "code": "UNKNOWN_ROLE_GRADE",
                    "detail": f"{e['role']} / {e['grade']}",
                }
            )
        for sid, lvl in (e.get("skills") or {}).items():
            if sid not in base.skills:
                errors.append(
                    {"path": f"{path}.skills.{sid}", "code": "UNKNOWN_SKILL", "detail": sid}
                )
            elif not isinstance(lvl, int) or not 0 <= lvl <= 5:
                errors.append(
                    {
                        "path": f"{path}.skills.{sid}",
                        "code": "LEVEL_OUT_OF_RANGE",
                        "detail": str(lvl),
                    }
                )
        try:
            _d(e["last_review_date"])
        except ValueError:
            errors.append({"path": path, "code": "BAD_DATE", "detail": str(e["last_review_date"])})
        goal = e.get("career_goal")
        if goal is None:
            warnings.append({"path": path, "code": "CAREER_GOAL_EMPTY", "detail": eid})
        elif (goal.get("target_role"), goal.get("target_grade")) not in base.role_profiles:
            errors.append(
                {"path": f"{path}.career_goal", "code": "UNKNOWN_TARGET", "detail": str(goal)}
            )
        if (
            e.get("manager_id")
            and e["manager_id"] not in ids
            and e["manager_id"] not in {x.get("employee_id") for x in employees}
        ):
            warnings.append(
                {
                    "path": path,
                    "code": "MANAGER_REFERENCE_UNRESOLVED",
                    "detail": str(e["manager_id"]),
                }
            )
    if not history_rows:
        warnings.append({"path": "activity_history", "code": "HISTORY_NOT_PROVIDED", "detail": ""})
    record_ids: set[str] = set()
    for i, r in enumerate(history_rows):
        line = f"activity_history.csv:{i + 2}"
        if r.get("employee_id") not in ids:
            errors.append(
                {"path": line, "code": "UNKNOWN_EMPLOYEE", "detail": str(r.get("employee_id"))}
            )
        if r.get("event_id") not in base.events:
            errors.append({"path": line, "code": "UNKNOWN_EVENT", "detail": str(r.get("event_id"))})
        if r.get("status") not in STATUSES:
            errors.append({"path": line, "code": "BAD_STATUS", "detail": str(r.get("status"))})
        if r.get("record_id") in record_ids:
            errors.append(
                {"path": line, "code": "DUPLICATE_RECORD_ID", "detail": str(r.get("record_id"))}
            )
        record_ids.add(r.get("record_id"))
        try:
            d = _d(r.get("date"))
            if r.get("status") == "completed" and d and d > base.as_of:
                errors.append({"path": line, "code": "HISTORY_AFTER_SNAPSHOT", "detail": str(d)})
        except ValueError:
            errors.append({"path": line, "code": "BAD_DATE", "detail": str(r.get("date"))})
        try:
            pct = int(r.get("completion_pct") or 0)
            if not 0 <= pct <= 100:
                raise ValueError
        except ValueError:
            errors.append(
                {"path": line, "code": "BAD_COMPLETION_PCT", "detail": str(r.get("completion_pct"))}
            )
    return errors, warnings


def build_scenario(base: Dataset, scenario: dict[str, Any]) -> Dataset:
    """Isolated jury scenario: base catalog + only the uploaded employees and history."""
    employees = scenario.get("employees") or []
    rows = scenario.get("history") or []
    errors, _ = validate_scenario(base, employees, rows)
    if errors:
        raise ValidationError(errors)
    return Dataset(
        as_of=base.as_of,
        skills=base.skills,
        role_profiles=base.role_profiles,
        employees={e["employee_id"]: e for e in employees},
        events=base.events,
        history=parse_history_rows(rows),
        name=scenario.get("name") or "scenario",
        proficiency_scale=base.proficiency_scale,
    )
