#!/usr/bin/env python3
"""Воспроизводимая локальная оценка Career Quest без сетевых вызовов по умолчанию."""

import argparse
import asyncio
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from career_quest.dataset import (  # noqa: E402
    Dataset,
    load_base_dataset,
    parse_events,
    parse_history_rows,
    parse_skills,
    read_csv_text,
)
from career_quest.engine import (  # noqa: E402
    PLANNER,
    POLICY_VERSION,
    build_snapshot,
    employee_records,
    simulate,
)
from career_quest.hr import hr_dashboard  # noqa: E402
from career_quest.progression import apply_activity, replay  # noqa: E402

# Независимая копия правила датасета, не импорт из eligibility движка.
REPEATABLE = {"EV_036"}
GRADES = ("Junior", "Middle", "Senior", "Lead")
DATA_FILES = ("employees.json", "events.json", "skills.json", "activity_history.csv")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hashes(paths):
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def ratio(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def quantiles(values):
    """Линейная интерполяция позиции (n−1)·p; единица измерения: миллисекунда."""
    ordered = sorted(values)

    def percentile(p):
        if not ordered:
            return None
        position = (len(ordered) - 1) * p
        lo, hi = math.floor(position), math.ceil(position)
        return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo), 4)

    return {
        "samples": len(values),
        "p50_ms": percentile(0.5),
        "p95_ms": percentile(0.95),
        "total_ms": round(sum(values), 4),
    }


class Audit:
    def __init__(self):
        self.metrics = {}
        self.failures = []

    def check(self, name, passed, employee_id=None, event_id=None, **details):
        metric = self.metrics.setdefault(name, {"numerator": 0, "denominator": 0})
        metric["denominator"] += 1
        metric["numerator"] += int(bool(passed))
        if not passed:
            self.failures.append(
                {
                    "check": name,
                    "employee_id": employee_id,
                    "event_id": event_id,
                    "details": details,
                }
            )
        return bool(passed)

    def results(self):
        return {k: ratio(**v) for k, v in sorted(self.metrics.items())}


def reference_apply(skills, event):
    """Оракул прироста; не использует actual_gain/apply_activity движка."""
    result = dict(skills)
    effects = []
    for effect in event.develops_skills:
        sid = effect["skill_id"]
        before = result.get(sid, 0)
        delta = max(0, min(effect["gain"], effect["max_level"] - before, 5 - before))
        result[sid] = before + delta
        effects.append(
            {
                "skill_id": sid,
                "before": before,
                "after": before + delta,
                "actual": delta,
                "gain": effect["gain"],
                "cap": effect["max_level"],
            }
        )
    return result, effects


def reference_state(ds, employee_id):
    employee = ds.employees[employee_id]
    records = [r for r in ds.history if r.employee_id == employee_id]
    skills = dict.fromkeys(ds.skills, 0) | employee.get("skills", {})
    review = date.fromisoformat(employee["last_review_date"])
    for record in sorted(records, key=lambda r: (r.date, r.record_id)):
        if record.status == "completed" and review < record.date <= ds.as_of:
            skills, _ = reference_apply(skills, ds.events[record.event_id])
    completed = {r.event_id for r in records if r.status == "completed"}
    latest = {}
    for record in sorted(records, key=lambda r: (r.date, r.record_id)):
        latest[record.event_id] = record
    active = {
        eid
        for eid, r in latest.items()
        if r.status == "in_progress" and eid not in completed and not ds.events[eid].mandatory
    }
    goal = employee.get("career_goal")
    if goal:
        target = (goal["target_role"], goal["target_grade"])
    else:
        target = (employee["role"], GRADES[min(GRADES.index(employee["grade"]) + 1, 3)])
    required, critical = ds.role_profiles[target]
    return {
        "skills": skills,
        "completed": completed,
        "active": active,
        "required": required,
        "critical": critical,
        "employee": employee,
    }


def reference_readiness(skills, required, critical):
    denominator = sum((2 if sid in critical else 1) * level for sid, level in required.items())
    numerator = sum(
        (2 if sid in critical else 1) * min(skills.get(sid, 0), level)
        for sid, level in required.items()
    )
    return 100 * numerator / denominator if denominator else 100.0


def eligibility(ds, state, event, kind, session=None, available_from=None):
    """Независимый допуск: §9.1 для start, исключения §9.2 для continue."""
    reasons = []
    eid = event.event_id
    if event.mandatory:
        reasons.append("MANDATORY")
    if eid in state["completed"] and eid not in REPEATABLE:
        reasons.append("ALREADY_COMPLETED")
    if kind == "continue":
        if eid not in state["active"]:
            reasons.append("NO_CURRENT_IN_PROGRESS")
        return reasons
    if kind != "start":
        reasons.append("UNKNOWN_ACTION_KIND")
    employee = state["employee"]
    if employee["role"] not in event.target_roles or employee["grade"] not in event.target_grades:
        reasons.append("AUDIENCE_MISMATCH")
    if any(state["skills"].get(sid, 0) < level for sid, level in event.prerequisites.items()):
        reasons.append("PREREQUISITES_UNMET")
    if eid in state["active"]:
        reasons.append("ACTIVE_REQUIRES_CONTINUE")
    if event.format != "self_paced":
        sessions = [s for s in event.upcoming_sessions if s >= (available_from or ds.as_of)]
        if not sessions:
            reasons.append("NO_UPCOMING_SESSION")
        elif session is not None and session != min(sessions).isoformat():
            reasons.append("INVALID_SELECTED_SESSION")
    return reasons


def selection(ds, state, event_id, kind=None):
    if event_id is None:
        return None
    event = ds.events[event_id]
    kind = kind or ("continue" if event_id in state["active"] else "start")
    after, effects = reference_apply(state["skills"], event)
    useful = {
        sid: min(
            max(0, level - state["skills"].get(sid, 0)),
            after.get(sid, 0) - state["skills"].get(sid, 0),
        )
        for sid, level in state["required"].items()
    }
    return {
        "event_id": event_id,
        "action_kind": kind,
        "format": event.format,
        "eligibility_problems": eligibility(ds, state, event, kind),
        "target_gain": sum(useful.values()),
        "critical_gain": sum(v for sid, v in useful.items() if sid in state["critical"]),
        "readiness_after_pct": reference_readiness(after, state["required"], state["critical"]),
        "effects": effects,
    }


def naive_baseline(ds, state):
    opened = [
        sid for sid, level in state["required"].items() if state["skills"].get(sid, 0) < level
    ]
    lowest = min(opened, key=lambda sid: (state["skills"].get(sid, 0), sid), default=None)
    for event in ds.events.values():
        if any(e["skill_id"] == lowest and e["gain"] > 0 for e in event.develops_skills):
            candidate = selection(ds, state, event.event_id)
            if not candidate["eligibility_problems"]:
                return lowest, candidate
    return lowest, None


def useful_action(ds, state, candidate):
    event = ds.events[candidate["event_id"]]
    if eligibility(ds, state, event, candidate["action_kind"], candidate.get("session")):
        return False
    if (
        candidate["action_kind"] == "start"
        and event.format != "self_paced"
        and not candidate.get("session")
    ):
        return False
    chosen = selection(ds, state, candidate["event_id"], candidate["action_kind"])
    if chosen["eligibility_problems"]:
        return False
    if chosen["target_gain"] > 0:
        return True
    path = (candidate.get("path") or {}).get("steps", [])
    if len(path) < 2 or path[0]["event_id"] != candidate["event_id"]:
        return False
    current = {**state, "skills": dict(state["skills"]), "completed": set(state["completed"])}
    first_after, _ = reference_apply(current["skills"], ds.events[candidate["event_id"]])
    helps_prerequisite = False
    available = ds.as_of
    for i, step in enumerate(path):
        event = ds.events[step["event_id"]]
        if eligibility(ds, current, event, step["action_kind"], step.get("session"), available):
            return False
        if i:
            helps_prerequisite |= any(
                state["skills"].get(sid, 0) < level <= first_after.get(sid, 0)
                for sid, level in event.prerequisites.items()
            )
        current["skills"], _ = reference_apply(current["skills"], event)
        current["completed"].add(event.event_id)
        current["active"] = current["active"] - {event.event_id}
        if step["action_kind"] == "continue":
            active_record = max(
                (
                    r
                    for r in ds.history_of(state["employee"]["employee_id"])
                    if r.event_id == event.event_id
                ),
                key=lambda r: (r.date, r.record_id),
            )
            hours = event.duration_hours * (1 - active_record.completion_pct / 100)
            available = ds.as_of + timedelta(days=max(1, math.ceil(hours / 4)))
        elif event.format == "self_paced":
            available += timedelta(days=max(1, math.ceil(event.duration_hours / 4)))
        else:
            if not step.get("session"):
                return False
            available = date.fromisoformat(step["session"]) + timedelta(
                days=max(1, math.ceil(event.duration_hours / 8))
            )
        if available > ds.as_of + timedelta(days=PLANNER["horizon_days"]):
            return False
    before = reference_readiness(state["skills"], state["required"], state["critical"])
    after = reference_readiness(current["skills"], state["required"], state["critical"])
    return helps_prerequisite and after > before


def evaluate_base(ds):
    audit = Audit()
    diagnostics = Audit()
    snapshots = {}
    rows = []
    latency = []
    reasons = Counter()
    no_step_ids, target_met_ids, useful_ids = [], [], []
    effect_count = above_cap_count = 0
    # Один явный прогрев не входит в выборку latency.
    build_snapshot(ds, sorted(ds.employees)[0], {})
    for index, employee_id in enumerate(sorted(ds.employees), 1):
        started = perf_counter()
        try:
            snap = build_snapshot(ds, employee_id, {})
        except Exception as exc:
            audit.check("snapshot_built", False, employee_id, error_type=type(exc).__name__)
            rows.append({"employee_id": employee_id, "error_type": type(exc).__name__})
            continue
        latency.append(
            {"employee_id": employee_id, "elapsed_ms": (perf_counter() - started) * 1000}
        )
        audit.check("snapshot_built", True, employee_id)
        snapshots[employee_id] = snap
        state = reference_state(ds, employee_id)
        initial_engine = replay(
            ds, ds.employees[employee_id], employee_records(ds, employee_id, {})
        )["current"]
        audit.check(
            "initial_skills_match_reference", initial_engine == state["skills"], employee_id
        )
        expected_readiness = reference_readiness(
            state["skills"], state["required"], state["critical"]
        )
        audit.check(
            "initial_readiness_matches_reference",
            math.isclose(
                snap["readiness"]["readiness_pct"], expected_readiness, abs_tol=1e-9, rel_tol=0
            ),
            employee_id,
            expected=expected_readiness,
            actual=snap["readiness"]["readiness_pct"],
        )
        met = all(state["skills"].get(sid, 0) >= level for sid, level in state["required"].items())
        if met:
            target_met_ids.append(employee_id)
        recommendations = snap["recommendations"]
        audit.check(
            "unique_recommendations",
            len({c["event_id"] for c in recommendations}) == len(recommendations),
            employee_id,
        )
        if not recommendations:
            no_step_ids.append(employee_id)
            codes = sorted({r["code"] for r in snap["no_step_reasons"]})
            reasons.update(codes)
            audit.check("no_step_has_reason", bool(codes), employee_id)
        else:
            codes = []
        rec_rows = []
        useful = False
        for rank, candidate in enumerate(recommendations, 1):
            event_id = candidate["event_id"]
            event = ds.events[event_id]
            issues = eligibility(
                ds, state, event, candidate["action_kind"], candidate.get("session")
            )
            if (
                candidate["action_kind"] == "start"
                and event.format != "self_paced"
                and not candidate.get("session")
            ):
                issues.append("SELECTED_SESSION_MISSING")
            audit.check(
                "eligible_recommendations", not issues, employee_id, event_id, reasons=issues
            )
            categories = sorted({f["category"] for f in candidate.get("facts", [])})
            audit.check(
                "facts_at_least_3_categories",
                len(categories) >= 3,
                employee_id,
                event_id,
                categories=categories,
            )
            audit.check(
                "facts_at_least_4_including_history",
                len(categories) >= 4 and "history" in categories,
                employee_id,
                event_id,
                categories=categories,
            )
            is_useful = useful_action(ds, state, candidate)
            audit.check("useful_recommendations", is_useful, employee_id, event_id)
            useful |= is_useful
            expected, effects = reference_apply(state["skills"], event)
            actual, changes = apply_activity(state["skills"], event)
            audit.check(
                "step_gain_matches_reference",
                actual == expected and changes == effects,
                employee_id,
                event_id,
                expected=effects,
                actual=changes,
            )
            audit.check(
                "displayed_gain_matches_reference",
                candidate.get("changes") == effects,
                employee_id,
                event_id,
                expected=effects,
                actual=candidate.get("changes"),
            )
            for effect_index, effect in enumerate(effects):
                change = changes[effect_index] if effect_index < len(changes) else {}
                effect_count += 1
                above_cap_count += effect["before"] > effect["cap"]
                audit.check(
                    "cap_and_gain_effects",
                    bool(change)
                    and 0 <= change["actual"] <= effect["gain"]
                    and effect["before"] <= change["after"] <= max(effect["before"], effect["cap"])
                    and change["after"] <= 5,
                    employee_id,
                    event_id,
                    effect=change,
                )
            overlay = {
                "completions": [
                    {
                        "employee_id": employee_id,
                        "event_id": event_id,
                        "session_date": candidate.get("session"),
                    }
                ]
            }
            after = build_snapshot(ds, employee_id, overlay)
            after_skills = replay(
                ds, ds.employees[employee_id], employee_records(ds, employee_id, overlay)
            )["current"]
            audit.check(
                "completion_gain_matches_reference",
                after_skills == expected,
                employee_id,
                event_id,
                mismatches={
                    s: {"expected": expected.get(s, 0), "actual": after_skills.get(s, 0)}
                    for s in expected
                    if expected.get(s, 0) != after_skills.get(s, 0)
                },
            )
            expected_after = reference_readiness(expected, state["required"], state["critical"])
            audit.check(
                "completion_readiness_matches_reference",
                math.isclose(
                    after["readiness"]["readiness_pct"], expected_after, abs_tol=1e-9, rel_tol=0
                ),
                employee_id,
                event_id,
                expected=expected_after,
                actual=after["readiness"]["readiness_pct"],
            )
            if event_id not in REPEATABLE:
                audit.check(
                    "nonrepeatable_not_recommended_again",
                    event_id not in {c["event_id"] for c in after["recommendations"]},
                    employee_id,
                    event_id,
                )
                repeated = simulate(ds, employee_id, {}, [event_id, event_id])
                error = repeated.get("error", {})
                audit.check(
                    "nonrepeatable_second_simulated_step_blocked",
                    error.get("code") == "STEP_BLOCKED"
                    and any(r["code"] == "ALREADY_COMPLETED" for r in error.get("reasons", [])),
                    employee_id,
                    event_id,
                    error=error,
                )
                duplicate_overlay = {"completions": overlay["completions"] * 2}
                duplicate_skills = replay(
                    ds,
                    ds.employees[employee_id],
                    employee_records(ds, employee_id, duplicate_overlay),
                )["current"]
                diagnostics.check(
                    "duplicate_overlay_is_idempotent",
                    duplicate_skills == after_skills,
                    employee_id,
                    event_id,
                    mismatches={
                        sid: {
                            "once": after_skills.get(sid, 0),
                            "twice": duplicate_skills.get(sid, 0),
                        }
                        for sid in after_skills
                        if duplicate_skills.get(sid, 0) != after_skills.get(sid, 0)
                    },
                )
            elif candidate.get("session"):
                repeats_session = any(
                    c["event_id"] == event_id and c.get("session") == candidate["session"]
                    for c in after["recommendations"]
                )
                diagnostics.check(
                    "completed_session_not_recommended_again",
                    not repeats_session,
                    employee_id,
                    event_id,
                    completed_session=candidate["session"],
                    next_sessions=[
                        c.get("session")
                        for c in after["recommendations"]
                        if c["event_id"] == event_id
                    ],
                )
            if candidate["action_kind"] == "continue":
                continuation = simulate(ds, employee_id, {}, [event_id])
                latest_active = max(
                    (r for r in ds.history_of(employee_id) if r.event_id == event_id),
                    key=lambda r: (r.date, r.record_id),
                )
                remaining = event.duration_hours * (1 - latest_active.completion_pct / 100)
                actual_effort = continuation.get("total_effort_hours")
                diagnostics.check(
                    "continue_simulation_uses_remaining_effort",
                    actual_effort is not None
                    and math.isclose(actual_effort, remaining, rel_tol=0, abs_tol=1e-9),
                    employee_id,
                    event_id,
                    expected_hours=remaining,
                    actual_hours=actual_effort,
                    completion_pct=latest_active.completion_pct,
                )
            if rank == 1:
                projection = simulate(ds, employee_id, {}, [event_id])
                projected_readiness = projection.get("after", {}).get("readiness_pct")
                consistent = projected_readiness is not None and math.isclose(
                    projected_readiness,
                    after["readiness"]["readiness_pct"],
                    abs_tol=1e-9,
                    rel_tol=0,
                )
                audit.check(
                    "main_what_if_completion_readiness",
                    consistent,
                    employee_id,
                    event_id,
                    projection=projected_readiness,
                    completion=after["readiness"]["readiness_pct"],
                    error=projection.get("error"),
                )
                audit.check(
                    "main_what_if_completion_skills",
                    projection.get("after", {}).get("skills") == after_skills,
                    employee_id,
                    event_id,
                )
            rec_rows.append(
                {
                    "rank": rank,
                    "event_id": event_id,
                    "action_kind": candidate["action_kind"],
                    "categories": categories,
                    "eligible": not issues,
                    "useful": is_useful,
                    "effects": effects,
                    "readiness_after_pct": after["readiness"]["readiness_pct"],
                }
            )
        if useful:
            useful_ids.append(employee_id)
        rows.append(
            {
                "employee_id": employee_id,
                "readiness_pct": snap["readiness"]["readiness_pct"],
                "target_met": met,
                "no_step_reasons": codes,
                "recommendations": rec_rows,
            }
        )
        if index % 50 == 0:
            print(f"Проверены сотрудники: {index}/{len(ds.employees)}", flush=True)
    started = perf_counter()
    dashboard = hr_dashboard(ds, {})
    hr_ms = (perf_counter() - started) * 1000
    audit.check(
        "hr_population_matches",
        dashboard["population"] == len(ds.employees),
        actual=dashboard["population"],
        expected=len(ds.employees),
    )
    coverage = {
        "employees_with_useful_action": ratio(len(useful_ids), len(ds.employees)),
        "employees_with_recommendations": ratio(
            sum(bool(s["recommendations"]) for s in snapshots.values()), len(ds.employees)
        ),
        "target_met": ratio(len(target_met_ids), len(ds.employees)),
        "without_recommendations": ratio(len(no_step_ids), len(ds.employees)),
        "unmet_without_recommendations": ratio(
            len(set(no_step_ids) - set(target_met_ids)), len(ds.employees)
        ),
        "no_step_reason_distribution": {
            code: ratio(count, len(no_step_ids)) for code, count in sorted(reasons.items())
        },
        "distinct_no_step_reason_count": len(reasons),
        "no_step_employee_ids": no_step_ids,
        "target_met_employee_ids": target_met_ids,
        "useful_employee_ids": useful_ids,
        "effects_already_above_cap": ratio(above_cap_count, effect_count),
    }
    timing = {
        "snapshot": quantiles([r["elapsed_ms"] for r in latency]),
        "snapshot_samples": latency,
        "hr_dashboard": {"samples": 1, "population": dashboard["population"], "elapsed_ms": hr_ms},
    }
    return (
        {
            "metrics": audit.results(),
            "coverage": coverage,
            "employees": rows,
            "failed_cases": audit.failures,
            "additional_diagnostics": {
                "metrics": diagnostics.results(),
                "failed_cases": diagnostics.failures,
            },
        },
        timing,
        snapshots,
    )


def load_fixture(directory):
    raw = {
        name: json.loads((directory / name).read_text())
        for name in DATA_FILES
        if name.endswith(".json")
    }
    skills, profiles = parse_skills(raw["skills.json"])
    return Dataset(
        as_of=date.fromisoformat(raw["employees.json"]["meta"]["as_of_date"]),
        skills=skills,
        role_profiles=profiles,
        employees={e["employee_id"]: e for e in raw["employees.json"]["employees"]},
        events=parse_events(raw["events.json"]["events"]),
        history=parse_history_rows(read_csv_text((directory / "activity_history.csv").read_text())),
        name=directory.name,
    )


def fixture_pass(ds, state, pick, candidate, criterion):
    if pick is None or pick["eligibility_problems"]:
        return False
    kind = criterion["kind"]
    if kind == "avoid_negative_format":
        misses = [
            r
            for r in ds.history
            if r.status == "no_show"
            and ds.events[r.event_id].format == criterion["negative_format"]
            and 0 <= (ds.as_of - r.date).days <= criterion["history_window_days"]
        ]
        peers = [ds.events[eid] for eid in criterion["equal_effect_event_ids"]]
        same_effect = all(
            e.develops_skills == peers[0].develops_skills
            and e.duration_hours == peers[0].duration_hours
            and e.upcoming_sessions == peers[0].upcoming_sessions
            for e in peers
        )
        return (
            len(misses) >= criterion["minimum_no_show_count"]
            and same_effect
            and pick["target_gain"] >= criterion["minimum_target_gain"]
            and pick["format"] != criterion["negative_format"]
        )
    if kind == "close_critical_gap":
        return pick["critical_gain"] >= criterion["minimum_critical_gain"]
    if kind == "positive_target_gain":
        return pick["target_gain"] >= criterion["minimum_target_gain"]
    if kind == "unlock_target_path":
        after, _ = reference_apply(state["skills"], ds.events[pick["event_id"]])
        target = ds.events[criterion["target_event_id"]]
        before_unmet = any(
            state["skills"].get(s, 0) < level for s, level in target.prerequisites.items()
        )
        after_met = all(after.get(s, 0) >= level for s, level in target.prerequisites.items())
        next_state = {
            **state,
            "skills": after,
            "completed": state["completed"] | {pick["event_id"]},
        }
        next_pick = selection(ds, next_state, target.event_id)
        return (
            before_unmet
            and after_met
            and not next_pick["eligibility_problems"]
            and next_pick["target_gain"] >= criterion["minimum_target_gain_after_followup"]
            and criterion["maximum_path_steps"] >= 2
        )
    if kind == "continue_existing":
        if pick["action_kind"] != criterion["required_action_kind"]:
            return False
        record = max(
            (r for r in ds.history if r.event_id == pick["event_id"]),
            key=lambda r: (r.date, r.record_id),
        )
        hours = ds.events[pick["event_id"]].duration_hours * (1 - record.completion_pct / 100)
        comparison = selection(ds, state, criterion["comparison_new_event_id"])
        return (
            pick["target_gain"] >= criterion["minimum_target_gain"]
            and hours <= criterion["maximum_remaining_hours"]
            and hours < ds.events[criterion["comparison_new_event_id"]].duration_hours
            and pick["target_gain"] == comparison["target_gain"]
            and (candidate is None or candidate["remaining_hours"] == hours)
        )
    if kind == "neutral_empty_history":
        neutral = not candidate or (
            candidate["history"]["insufficient"]
            and candidate["history"]["affinity"] == criterion["expected_affinity"]
            and any(
                f["code"] == criterion["required_history_fact_code"] for f in candidate["facts"]
            )
        )
        return (
            len(ds.history) == criterion["expected_history_records"]
            and pick["target_gain"] >= criterion["minimum_target_gain"]
            and neutral
        )
    raise ValueError(f"Неизвестный критерий: {kind}")


def evaluate_fixtures():
    rows = []
    for path in sorted((ROOT / "scripts/eval_fixtures").glob("*/manifest.json")):
        manifest = json.loads(path.read_text())
        ds = load_fixture(path.parent)
        state = reference_state(ds, manifest["employee_id"])
        snap = build_snapshot(ds, manifest["employee_id"], {})
        main = next(iter(snap["recommendations"]), None)
        chosen = selection(ds, state, main["event_id"], main["action_kind"]) if main else None
        lowest, baseline = naive_baseline(ds, state)
        criterion = manifest["criterion"]
        engine_passed = fixture_pass(ds, state, chosen, main, criterion)
        baseline_passed = fixture_pass(ds, state, baseline, None, criterion)
        rows.append(
            {
                "id": manifest["id"],
                "title": manifest["title"],
                "description": manifest["description"],
                "criterion": criterion,
                "limitations": manifest["limitations"],
                "lowest_open_target_skill": lowest,
                "engine": chosen,
                "baseline": baseline,
                "engine_passed": engine_passed,
                "baseline_passed": baseline_passed,
                "engine_history": main["history"] if main else None,
                "engine_path_event_ids": [
                    s["event_id"] for s in (main.get("path") or {}).get("steps", [])
                ]
                if main
                else [],
                "no_step_reasons": snap["no_step_reasons"],
            }
        )
    if len(rows) < 6:
        raise ValueError(f"Нужно минимум 6 синтетических случаев; найдено {len(rows)}")
    return {
        "cases": rows,
        "engine_passed": ratio(sum(r["engine_passed"] for r in rows), len(rows)),
        "baseline_passed": ratio(sum(r["baseline_passed"] for r in rows), len(rows)),
        "engine_only_passed": ratio(
            sum(r["engine_passed"] and not r["baseline_passed"] for r in rows), len(rows)
        ),
        "both_passed": ratio(
            sum(r["engine_passed"] and r["baseline_passed"] for r in rows), len(rows)
        ),
    }


async def evaluate_ai(ds, snapshots, requested):
    result = {"requested": requested, "calls": [], "status": "не запрошено", "locale": "ru"}
    if not requested:
        return result
    if not os.environ.get("OPENAI_API_KEY"):
        result["status"] = "пропущено: OPENAI_API_KEY не установлен"
        return result
    from career_quest.ai import select_actions

    eligible = [eid for eid in sorted(snapshots) if snapshots[eid].get("shortlist")]
    skill_names = {sid: value["name"] for sid, value in ds.skills.items()}
    for index, eid in enumerate(eligible[:requested], 1):
        started = perf_counter()
        try:
            response = await select_actions(snapshots[eid], skill_names, "ru")
            row = {
                key: response[key]
                for key in ("ai_status", "model", "prompt_version", "validation", "error")
                if key in response
            }
            row["choices_count"] = len(response.get("choices", []))
        except Exception as exc:
            row = {"ai_status": "ошибка вызова", "error_type": type(exc).__name__}
        row.update(employee_id=eid, elapsed_ms=(perf_counter() - started) * 1000)
        result["calls"].append(row)
        print(f"AI: {index}/{min(requested, len(eligible))}, статус {row['ai_status']}", flush=True)
    calls = result["calls"]
    result.update(
        status="выполнено",
        available_employees=len(eligible),
        live_validated=ratio(sum(r["ai_status"] == "live_validated" for r in calls), len(calls)),
        fallback=ratio(sum(r["ai_status"].startswith("fallback_") for r in calls), len(calls)),
        latency=quantiles([r["elapsed_ms"] for r in calls]),
        validation_problems=dict(Counter(p for r in calls for p in r.get("validation", []))),
        statuses=dict(Counter(r["ai_status"] for r in calls)),
    )
    return result


METRIC_LABELS = {
    "snapshot_built": "Построен снимок сотрудника",
    "initial_skills_match_reference": "Начальные навыки совпадают с независимым пересчётом",
    "initial_readiness_matches_reference": "Начальная готовность совпадает с независимым расчётом",
    "unique_recommendations": "В наборе карточек нет повторяющихся событий",
    "eligible_recommendations": "Рекомендация независимо допущена",
    "facts_at_least_3_categories": "В фактах ≥3 категорий",
    "facts_at_least_4_including_history": "В фактах ≥4 категорий, включая историю",
    "useful_recommendations": "Есть полезный прямой эффект либо проверенный путь через prerequisites",
    "step_gain_matches_reference": "Применение шага совпадает с независимой формулой",
    "displayed_gain_matches_reference": "Показанный прирост совпадает с независимой формулой",
    "cap_and_gain_effects": "Эффект соблюдает gain, cap, шкалу 0–5 и монотонность",
    "completion_gain_matches_reference": "Навыки после completion-overlay совпадают с ожидаемыми",
    "completion_readiness_matches_reference": "Готовность после completion-overlay совпадает с ожидаемой",
    "nonrepeatable_not_recommended_again": "Завершённый неповторяемый шаг не рекомендован повторно",
    "nonrepeatable_second_simulated_step_blocked": "Повтор неповторяемого шага в simulate отклонён",
    "main_what_if_completion_readiness": "Главный шаг: готовность what-if совпадает с completion",
    "main_what_if_completion_skills": "Главный шаг: все навыки what-if совпадают с completion",
    "no_step_has_reason": "Отсутствие рекомендаций снабжено причиной",
    "hr_population_matches": "HR охватывает весь исходный набор",
    "duplicate_overlay_is_idempotent": "Дублированный completion-overlay не даёт дополнительный прирост",
    "completed_session_not_recommended_again": "Завершённая сессия повторяемого клуба не рекомендована снова",
    "continue_simulation_uses_remaining_effort": "Прогноз continue использует остаточную нагрузку",
}


def fraction(value):
    n, d = value["numerator"], value["denominator"]
    return f"{n}/{d}" + (f" ({100 * n / d:.2f}%)" if d else " (не применимо)")


def markdown(report):
    conditions, base, fixtures = report["conditions"], report["results"], report["fixtures"]
    coverage, timing = base["coverage"], report["latency"]
    lines = [
        "# Оценка рекомендаций Career Quest",
        "",
        "Отчёт автоматически создан `scripts/evaluate.py`. Повторный запуск обновляет этот файл и JSON.",
        "",
        "## Запуск и условия",
        "",
        "```bash",
        "uv run python scripts/evaluate.py",
        "# Необязательно: реальные AI-вызовы при ключе в окружении",
        "uv run python scripts/evaluate.py --ai 5",
        "```",
        "",
        "Код возврата 0 означает завершённую оценку, даже если найдены нарушения. "
        "`--fail-on-violations` возвращает 1 при нарушениях инвариантов, дополнительных диагностик или критериев движка; ошибка исполнения возвращает ненулевой код.",
        "",
        f"Запуск UTC: `{conditions['generated_at_utc']}`. Ветка `{conditions['git_branch']}`, коммит `{conditions['git_commit']}`. "
        f"Правила `{POLICY_VERSION}`. Набор версии `{report['dataset']['version']}`, срез `{ds_date(report)}`: "
        f"{report['dataset']['employees']} сотрудников, {report['dataset']['events']} событий, "
        f"{report['dataset']['skills']} навыков, {report['dataset']['history_records']} записей истории.",
        "",
        f"Локальная машина: {conditions['platform']}, {conditions['machine']}, Python {conditions['python']}, "
        f"логических CPU: {conditions['cpu_count']}. Это измерение Python-ядра на данной машине; HTTP, UI и production не измерялись.",
        "",
        f"SHA-256 набора: `{report['dataset']['sha256']}`. SHA-256 качественных результатов: `{report['quality_sha256']}`. "
        "Хеши каждого входного файла, движка, скрипта и fixtures сохранены в JSON. Время и AI исключены из хеша качества.",
        "",
        "## Методика",
        "",
        "Все сотрудники обходятся по ID; overlay пуст, история включена, цели наследуются из профиля. "
        "Датой расчёта служит as_of_date набора, а не календарная дата запуска. Проверяются все показанные рекомендации top-3, "
        "каждая применяется отдельно к исходному состоянию: карточки являются альтернативами.",
        "",
        "Допуск независимо проверяет обязательность, текущую роль/грейд, AND-prerequisites, завершения и сессии. "
        "Для continue нужен актуальный in_progress; согласно §9.2 аудитория, prerequisites и прошедшая сессия "
        "не проверяются задним числом. Исключение повторяемости: EV_036. Snooze отсутствует в исходном overlay.",
        "",
        "Начальные навыки, цель, готовность и формула gain вычисляются отдельно от функций движка. "
        "Проверяется `delta=max(0,min(gain,max_level-before,5-before))`. Если исходный навык уже выше cap события, "
        "он сохраняется: корректная верхняя граница after равна max(before, cap), при шкале ≤5. "
        f"Таких исходных эффектов: {fraction(coverage['effects_already_above_cap'])}.",
        "",
        "Полезность означает положительное сокращение целевого разрыва либо допустимую цепочку, в которой "
        "первый шаг закрывает prerequisite следующего события и итог уменьшает целевой разрыв. Это операционный "
        "критерий, а не измеренная польза сотруднику. Категории считаются по структурным facts, не по тексту LLM. "
        "HISTORY_INSUFFICIENT считается честным контекстом истории.",
        "",
        "Для каждого главного шага сравниваются готовность simulate и полного build_snapshot после completion-overlay "
        "с допуском 1e-9 процентного пункта; отдельно сравниваются все навыки. "
        "Для каждого неповторяемого рекомендованного события проверяются повторная выдача и simulate([event,event]).",
        "",
        "## Проверки исходного набора",
        "",
        "| Проверка | Успешно / проверено |",
        "|---|---:|",
    ]
    lines += [
        f"| {METRIC_LABELS.get(name, name)} | {fraction(value)} |"
        for name, value in base["metrics"].items()
    ]
    lines += ["", "## Покрытие", "", "| Показатель | Числитель / сотрудники |", "|---|---:|"]
    for key, label in (
        ("employees_with_recommendations", "Есть рекомендация"),
        ("employees_with_useful_action", "Есть ≥1 полезная рекомендация"),
        ("target_met", "Требования цели выполнены"),
        ("without_recommendations", "Нет рекомендаций, включая выполненные цели"),
        ("unmet_without_recommendations", "Цель не выполнена и нет рекомендаций"),
    ):
        lines.append(f"| {label} | {fraction(coverage[key])} |")
    lines += [
        "",
        f"Различных диагностических кодов: {coverage['distinct_no_step_reason_count']}. "
        "Ниже знаменатель включает всех сотрудников без рекомендаций, включая выполненные цели. "
        "Причины пересекаются, сумма долей может превышать 100%.",
        "",
        "| Причина | Сотрудники / без рекомендаций |",
        "|---|---:|",
    ]
    lines += [
        f"| `{code}` | {fraction(value)} |"
        for code, value in coverage["no_step_reason_distribution"].items()
    ]
    lines += [
        "",
        "## Синтетические сравнения",
        "",
        "Baseline выбирает самый низкий текущий навык среди открытых целевых разрывов "
        "(равенство разрешается по skill_id), затем первое допустимое событие в порядке events.json "
        "с номинальным gain>0 для этого навыка. Caps, критичность и история не ранжируются; "
        "если события нет, baseline останавливается. Continue допускается по тем же правилам. "
        "Критерии заданы в manifest.json каждого случая; ожидаемые ID не используются как оракул.",
        "",
        "| Случай и критерий | Baseline | Движок | Результат критерия |",
        "|---|---|---|---|",
    ]
    for row in fixtures["cases"]:

        def pick(value):
            return f"`{value['event_id']}` ({value['action_kind']})" if value else "нет шага"

        outcome = (
            "оба выполняют критерий"
            if row["engine_passed"] and row["baseline_passed"]
            else "только движок выполняет критерий"
            if row["engine_passed"]
            else "только baseline выполняет критерий"
            if row["baseline_passed"]
            else "оба не выполняют критерий"
        )
        lines.append(
            f"| {row['title']}: {row['criterion']['description']} | {pick(row['baseline'])} | {pick(row['engine'])} | {outcome} |"
        )
    lines += [
        "",
        f"Критерий выполнен движком: {fraction(fixtures['engine_passed'])}; baseline: {fraction(fixtures['baseline_passed'])}. "
        f"Только движок: {fraction(fixtures['engine_only_passed'])}; оба: {fraction(fixtures['both_passed'])}. "
        "Это результаты специально сконструированных случаев, не ML accuracy и не оценка скрытых профилей жюри.",
        "",
    ]
    for row in fixtures["cases"]:
        engine_gain = row["engine"]["target_gain"] if row["engine"] else 0
        naive_gain = row["baseline"]["target_gain"] if row["baseline"] else 0
        lines.append(
            f"- **{row['title']}.** {row['description']} Прямое сокращение разрывов: движок {engine_gain}, "
            f"baseline {naive_gain} уровней навыков. Ограничение: {' '.join(row['limitations'])}"
        )
    lines += [
        "",
        "## Локальная задержка",
        "",
        "Один прогрев снимка исключён. Далее один последовательный измеряемый build_snapshot(with_plan=True) "
        "на сотрудника; дополнительные проверки не входят в latency. HR измерен одним полным вызовом после "
        "проверок. Загрузка файлов/импорт не входят. Квантили вычисляются линейной интерполяцией позиции (n−1)·p. "
        "Повторные запуски меняют timing; это не SLA и не нагрузочный тест.",
        "",
        "| Операция | Число измерений | p50, мс | p95, мс | Всего, мс |",
        "|---|---:|---:|---:|---:|",
        f"| build_snapshot | {timing['snapshot']['samples']}/{report['dataset']['employees']} сотрудников | {timing['snapshot']['p50_ms']} | {timing['snapshot']['p95_ms']} | {timing['snapshot']['total_ms']} |",
        f"| hr_dashboard, {timing['hr_dashboard']['population']} сотрудников | 1 вызов | не оценён | не оценён | {timing['hr_dashboard']['elapsed_ms']:.4f} |",
        "",
        "## AI",
        "",
    ]
    ai = report["ai"]
    lines.append(
        f"Статус: {ai['status']}. Запрошено {ai['requested']}, вызовов select_actions: {len(ai['calls'])}."
    )
    if ai["calls"]:
        lines += [
            "",
            f"live_validated: {fraction(ai['live_validated'])}; fallback: {fraction(ai['fallback'])}. "
            f"p50/p95: {ai['latency']['p50_ms']}/{ai['latency']['p95_ms']} мс по {ai['latency']['samples']} вызовам. "
            "Выбраны первые ID с непустым shortlist, язык ru; это не случайная выборка. "
            "Статус live_validated допускает исправления сервером и не доказывает семантическую точность текста.",
            "",
            "Проблемы валидации (число сообщений, несколько возможны в одном вызове): "
            + canonical(ai["validation_problems"]),
        ]
    else:
        lines.append(
            "Доли live_validated/fallback и задержки AI не измерены; отсутствие вызовов не считается успешной проверкой AI."
        )
    lines += [
        "",
        "## Неуспешные случаи",
        "",
        f"Нарушений исходных проверок: {len(base['failed_cases'])} из {sum(m['denominator'] for m in base['metrics'].values())} проверок. "
        "Числитель здесь отражает нарушения, одно событие может нарушить несколько инвариантов.",
    ]
    if base["failed_cases"]:
        lines += ["", "| Проверка | Сотрудник | Событие | Подробности |", "|---|---|---|---|"]
        for failure in base["failed_cases"]:
            details = canonical(failure["details"]).replace("|", "\\|")
            lines.append(
                f"| {METRIC_LABELS.get(failure['check'], failure['check'])} | {failure['employee_id'] or 'нет'} | {failure['event_id'] or 'нет'} | {details} |"
            )
    failed_fixtures = [r["id"] for r in fixtures["cases"] if not r["engine_passed"]]
    lines += [
        "",
        f"Невыполненных критериев движка на fixtures: {len(failed_fixtures)}/{len(fixtures['cases'])}. "
        + ", ".join(failed_fixtures),
        "",
        "## Дополнительные диагностики движка",
        "",
        "Эти проверки отделены от допуска исходных top-3, их прироста и совпадения готовности. "
        "После завершения каждой рекомендованной сессии EV_036 проверяется её повторная выдача. "
        "Для неповторяемых событий отдельно сравниваются навыки при одном и двух одинаковых completion в overlay. "
        "Для всех continue сравнивается total_effort_hours прогноза с независимой оценкой оставшихся часов.",
        "",
        "| Проверка | Успешно / проверено | Нарушения / проверено |",
        "|---|---:|---:|",
    ]
    diagnostics = base["additional_diagnostics"]
    for name, value in diagnostics["metrics"].items():
        violations = ratio(value["denominator"] - value["numerator"], value["denominator"])
        lines.append(f"| {METRIC_LABELS[name]} | {fraction(value)} | {fraction(violations)} |")
    lines += [
        "",
        "Полный перечень неуспешных пар сотрудник/событие с наблюдениями находится в "
        "`artifacts/evaluation.json → results.additional_diagnostics.failed_cases`. "
        "Ниже по одному конкретному примеру каждого нарушения:",
        "",
    ]
    for name in diagnostics["metrics"]:
        example = next((f for f in diagnostics["failed_cases"] if f["check"] == name), None)
        if example:
            lines.append(
                f"- {METRIC_LABELS[name]}: `{example['employee_id']}` / `{example['event_id']}`; {canonical(example['details'])}."
            )
    if not diagnostics["failed_cases"]:
        lines.append("Нарушений дополнительных диагностик не обнаружено.")
    lines += [
        "",
        "## Ограничения",
        "",
        "В наборе нет размеченных лучших рекомендаций и результатов вмешательства. "
        "Не оценивались рост завершений, удержание, повышение, семантическая истинность всех фактов/объяснений, "
        "авторизация, UI и производительность сети. Проверка категорий устанавливает их наличие, а не достаточность объяснения. "
        "В базовом прогоне не менялись цель, snooze, настройки истории. "
        "Диагностика дублированного overlay проверяет ядро напрямую и не означает, что UI отправляет такие дубли; "
        "проверка EV_036 ограничена сессиями исходных рекомендаций. "
        "Планировщик ограничен глубиной и шириной поиска; отсутствие найденного пути не доказывает невозможность развития. "
        "Метрики относятся к указанным хешам кода и данных; после слияния исправлений отчёт нужно пересоздать. "
        "Сравнение касается только описанных synthetic fixtures и не характеризует другие команды.",
        "",
    ]
    return "\n".join(lines)


def ds_date(report):
    return report["dataset"]["as_of_date"]


def git_value(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ai",
        type=int,
        default=0,
        metavar="N",
        help="вызвать AI для первых N сотрудников с кандидатами",
    )
    parser.add_argument(
        "--fail-on-violations",
        action="store_true",
        help="код 1 при нарушении инвариантов или критериев движка",
    )
    args = parser.parse_args()
    if args.ai < 0:
        parser.error("--ai должен быть неотрицательным")
    ds = load_base_dataset()
    base, latency, snapshots = evaluate_base(ds)
    fixtures = evaluate_fixtures()
    ai = asyncio.run(evaluate_ai(ds, snapshots, args.ai))
    inputs = file_hashes([ROOT / "data/dataset" / name for name in DATA_FILES])
    fixture_paths = sorted(
        p for p in (ROOT / "scripts/eval_fixtures").rglob("*") if p.suffix in {".json", ".csv"}
    )
    metadata = json.loads((ROOT / "data/dataset/employees.json").read_text())["meta"]
    report = {
        "schema_version": 1,
        "conditions": {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "git_commit": git_value("rev-parse", "HEAD"),
            "git_branch": git_value("branch", "--show-current"),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "policy_version": POLICY_VERSION,
            "planner": PLANNER,
            "overlay": {},
            "history_enabled": True,
            "employee_order": "ID по возрастанию",
            "warmup_calls": 1,
            "snapshot_calls_per_employee": 1,
            "percentile_method": "линейная интерполяция позиции (n−1)·p",
            "readiness_tolerance_pp": 1e-9,
            "source_hashes": file_hashes(
                sorted((ROOT / "career_quest").glob("*.py")) + [Path(__file__).resolve()]
            ),
            "fixture_hashes": file_hashes(fixture_paths),
        },
        "dataset": {
            **metadata,
            "employees": len(ds.employees),
            "events": len(ds.events),
            "skills": len(ds.skills),
            "history_records": len(ds.history),
            "files": inputs,
            "sha256": digest(inputs),
        },
        "results": base,
        "fixtures": fixtures,
        "latency": latency,
        "ai": ai,
        "quality_sha256": digest({"results": base, "fixtures": fixtures}),
    }
    for directory in ("artifacts", "docs"):
        (ROOT / directory).mkdir(exist_ok=True)
    (ROOT / "artifacts/evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "docs/EVALUATION.md").write_text(markdown(report), encoding="utf-8")
    violations = (
        len(base["failed_cases"])
        + len(base["additional_diagnostics"]["failed_cases"])
        + sum(not r["engine_passed"] for r in fixtures["cases"])
    )
    print(
        f"Готово: сотрудников {len(ds.employees)}, fixtures {len(fixtures['cases'])}, нарушений {violations}."
    )
    print(f"Хеш качественных результатов: {report['quality_sha256']}")
    print("Отчёты: artifacts/evaluation.json и docs/EVALUATION.md")
    return 1 if args.fail_on_violations and violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
