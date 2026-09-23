#!/usr/bin/env python3
"""Воспроизводимые локальные измерения для защиты, без API/LLM и изменения кода.

Из корня worktree:
    PYTHONDONTWRITEBYTECODE=1 python3 docs/measure_demo.py

Скрипт перебирает весь исходный набор и выбирает профили по явным условиям.
Результат записывается только в docs/evidence/local_measurements.json.
Время выполнения относится к этому Python-процессу, а не к production/UI.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from career_quest.dataset import load_base_dataset  # noqa: E402
from career_quest.engine import (  # noqa: E402
    PLANNER,
    POLICY_VERSION,
    build_snapshot,
    employee_records,
    simulate,
)
from career_quest.hr import hr_dashboard  # noqa: E402
from career_quest.progression import replay  # noqa: E402


def main_step(snapshot: dict) -> dict | None:
    return next(iter(snapshot["recommendations"]), None)


def lowest_open(snapshot: dict) -> dict | None:
    """Тот же порядок, что в WhyNot: минимальный current, затем skill_id."""
    return min(
        (s for s in snapshot["skills"] if s["in_target"] and s["gap"] > 0),
        key=lambda s: (s["current"], s["skill_id"]),
        default=None,
    )


def current_skills(dataset, employee_id: str, overlay: dict) -> dict:
    return replay(
        dataset,
        dataset.employees[employee_id],
        employee_records(dataset, employee_id, overlay),
    )["current"]


def completion_overlay(employee_id: str, candidate: dict) -> dict:
    return {
        "completions": [
            {
                "employee_id": employee_id,
                "event_id": candidate["event_id"],
                "session_date": candidate["session"],
                "gaming": False,
            }
        ]
    }


def short_snapshot(snapshot: dict) -> dict:
    """Проверяемый итог для каждого сотрудника без повторения всего каталога."""
    main = main_step(snapshot)
    lowest = lowest_open(snapshot)
    minimum_level = lowest["current"] if lowest else None
    lowest_ids = [
        s["skill_id"]
        for s in snapshot["skills"]
        if s["in_target"] and s["gap"] > 0 and s["current"] == minimum_level
    ]
    return {
        "employee_id": snapshot["employee"]["employee_id"],
        "full_name": snapshot["employee"]["full_name"],
        "role": snapshot["employee"]["role"],
        "grade": snapshot["employee"]["grade"],
        "target": snapshot["target"],
        "readiness": snapshot["readiness"],
        "lowest_open_target_skill": lowest,
        "all_lowest_open_target_skill_ids": lowest_ids,
        "recommendation_ids": [c["event_id"] for c in snapshot["recommendations"]],
        "main_event_id": main["event_id"] if main else None,
        "main_tier": main["tier"] if main else None,
        "main_useful": main["useful"] if main else None,
        "main_history_insufficient": main["history"]["insufficient"] if main else None,
        "main_history_fit": main["breakdown"]["history_fit"] if main else None,
        "lowest_differs_from_main": bool(
            main and lowest and lowest["skill_id"] not in main["useful"]
        ),
        "all_lowest_differ_from_main": bool(
            main and lowest and not set(lowest_ids) & set(main["useful"])
        ),
        "main_bridge": bool(main and main["bridge"]),
        "cross_role": snapshot["employee"]["role"] != snapshot["target"]["role"],
        "no_step_reasons": snapshot["no_step_reasons"],
        "route_status": snapshot["plan"]["status"],
        "route_event_ids": [
            s["event_id"] for s in (snapshot["plan"]["best"] or {}).get("steps", [])
        ],
    }


def run() -> dict:
    started_at = datetime.now(UTC).isoformat()
    started = time.perf_counter()
    dataset = load_base_dataset()
    snapshots = {}
    snapshot_times_ms = []
    for employee_id in dataset.employees:
        before = time.perf_counter()
        snapshots[employee_id] = build_snapshot(dataset, employee_id, {})
        snapshot_times_ms.append((time.perf_counter() - before) * 1000)

    summary = {eid: short_snapshot(s) for eid, s in snapshots.items()}
    main_projections = {
        eid: simulate(dataset, eid, {}, [main_step(s)["event_id"]])
        for eid, s in snapshots.items()
        if main_step(s)
    }

    # Условия фиксируются до записи ID: низкий навык не улучшается, есть
    # критический эффект и положительный наблюдаемый вклад истории.
    multi = [
        eid
        for eid, row in summary.items()
        if row["all_lowest_differ_from_main"]
        and row["main_tier"] == 0
        and not row["lowest_open_target_skill"]["critical"]
        and not row["main_history_insufficient"]
        and row["main_history_fit"] > 0
    ]
    multi.sort(
        key=lambda eid: (
            not main_projections[eid]["after"]["critical_gate_met"],
            -(
                main_projections[eid]["after"]["readiness_pct"]
                - main_projections[eid]["before"]["readiness_pct"]
            ),
            -summary[eid]["main_history_fit"],
            eid,
        )
    )
    bridge = [
        eid
        for eid, row in summary.items()
        if row["main_bridge"]
        and row["route_event_ids"][0] == row["main_event_id"]
        and set(main_step(snapshots[eid])["unlocks"]) & set(row["route_event_ids"][1:])
    ]
    bridge.sort(key=lambda eid: (len(summary[eid]["route_event_ids"]), eid))
    no_step = [
        eid
        for eid, row in summary.items()
        if not row["recommendation_ids"]
        and not row["readiness"]["all_requirements_met"]
        and any(r["proof_level"] == "catalog_fact" for r in row["no_step_reasons"])
    ]
    no_step.sort(
        key=lambda eid: (
            any(r["code"] == "AUDIENCE_MISMATCH" for r in summary[eid]["no_step_reasons"]),
            len(summary[eid]["no_step_reasons"]),
            eid,
        )
    )
    cross_role = [
        eid
        for eid, row in summary.items()
        if row["cross_role"] and row["main_tier"] == 0 and row["grade"] == row["target"]["grade"]
    ]
    cross_role.sort()
    candidates = {
        "multi_factor": multi,
        "bridge": bridge,
        "no_step_catalog": no_step,
        "cross_role": cross_role,
    }
    if any(not ids for ids in candidates.values()):
        raise RuntimeError(f"Не найдены все демонстрационные условия: {candidates}")
    selected_ids = {name: ids[0] for name, ids in candidates.items()}

    # Одна реальная отметка главного шага для каждого профиля, у которого он есть.
    completion_checks = []
    for eid, projection in main_projections.items():
        candidate = main_step(snapshots[eid])
        overlay = completion_overlay(eid, candidate)
        completed = build_snapshot(dataset, eid, overlay)
        skills = current_skills(dataset, eid, overlay)
        completion_checks.append(
            {
                "employee_id": eid,
                "event_id": candidate["event_id"],
                "what_if_matches_completion_readiness": "after" in projection
                and projection["after"]["readiness_pct"] == completed["readiness"]["readiness_pct"],
                "what_if_matches_completion_all_skills": "after" in projection
                and projection["after"]["skills"] == skills,
                "grade_unchanged": completed["employee"]["grade"]
                == snapshots[eid]["employee"]["grade"],
                "simulate_error": projection.get("error"),
            }
        )

    selected = {}
    for name, eid in selected_ids.items():
        before = snapshots[eid]
        candidate = main_step(before)
        plan_ids = summary[eid]["route_event_ids"]
        reason_event_ids = [
            event_id
            for reason in before["no_step_reasons"]
            for event_id in reason.get("event_ids", [])
        ]
        history_off = build_snapshot(dataset, eid, {"history_off": {eid: True}})
        data = {
            "employee_id": eid,
            "summary": summary[eid],
            "before": before,
            "history_disabled": {
                "recommendations": history_off["recommendations"],
                "readiness": history_off["readiness"],
            },
            "route_what_if": simulate(dataset, eid, {}, plan_ids) if plan_ids else None,
            "events": {
                event_id: asdict(dataset.events[event_id])
                for event_id in sorted(
                    set(
                        plan_ids
                        + reason_event_ids
                        + [c["event_id"] for c in before["recommendations"]]
                    )
                )
            },
        }
        if candidate:
            overlay = completion_overlay(eid, candidate)
            after = build_snapshot(dataset, eid, overlay)
            repeated_same_state = build_snapshot(dataset, eid, overlay)
            duplicate = {"completions": overlay["completions"] * 2}
            duplicate_state = build_snapshot(dataset, eid, duplicate)
            data.update(
                {
                    "completion_overlay": overlay,
                    "main_what_if": main_projections[eid],
                    "after_completion": after,
                    "same_overlay_reload": {
                        "readiness_equal": repeated_same_state["readiness"] == after["readiness"],
                        "skills_equal": repeated_same_state["skills"] == after["skills"],
                        "fingerprint_equal": repeated_same_state["fingerprint"]
                        == after["fingerprint"],
                    },
                    "duplicate_completion_probe": {
                        "note_ru": "Проверка недоверенного overlay с двумя одинаковыми отметками; это не повторная загрузка страницы.",
                        "overlay": duplicate,
                        "readiness": duplicate_state["readiness"],
                        "skills": duplicate_state["skills"],
                        "has_additional_skill_gain": current_skills(dataset, eid, duplicate)
                        != current_skills(dataset, eid, overlay),
                    },
                }
            )
        selected[name] = data

    # Проверяем eligibility и категории evidence у каждого возвращённого кандидата.
    recommendation_checks = []
    for eid, snapshot in snapshots.items():
        catalog = {c["event_id"]: c for c in snapshot["catalog"]}
        for candidate in snapshot["recommendations"]:
            event = dataset.events[candidate["event_id"]]
            categories = sorted({f["category"] for f in candidate["facts"]})
            recommendation_checks.append(
                {
                    "employee_id": eid,
                    "event_id": candidate["event_id"],
                    "action_kind": candidate["action_kind"],
                    "allowed_as_new_or_active_continuation": catalog[event.event_id]["eligible"]
                    or (
                        candidate["action_kind"] == "continue"
                        and event.event_id in snapshot["active"]
                    ),
                    "mandatory": event.mandatory,
                    "evidence_categories": categories,
                    "has_history_evidence": "history" in categories,
                    "changes_obey_growth_rule": all(
                        c["after"] - c["before"]
                        == max(0, min(c["gain"], c["cap"] - c["before"], 5 - c["before"]))
                        for c in candidate["changes"]
                    ),
                }
            )
    dashboard = hr_dashboard(dataset, {})
    multi_id = selected_ids["multi_factor"]
    hr_after_completion = hr_dashboard(dataset, selected["multi_factor"]["completion_overlay"])
    reason_counts = Counter(
        reason["code"] for snapshot in snapshots.values() for reason in snapshot["no_step_reasons"]
    )
    files_to_hash = sorted((ROOT / "career_quest").glob("*.py")) + sorted(
        (ROOT / "data" / "dataset").glob("*")
    )
    file_hashes = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in files_to_hash
        if path.is_file()
    }
    labels_source = (ROOT / "lib" / "i18n.ts").read_text("utf-8").split("const en:")[0]
    ui_labels = dict(re.findall(r'^  (\w+): "([^"\n]+)",', labels_source, re.MULTILINE))
    recommendation_count = len(recommendation_checks)
    completion_count = len(completion_checks)
    return {
        "provenance": {
            "command": "PYTHONDONTWRITEBYTECODE=1 python3 docs/measure_demo.py",
            "cwd": str(ROOT),
            "started_at_utc": started_at,
            "finished_at_utc": datetime.now(UTC).isoformat(),
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "git_head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "dataset": dataset.name,
            "dataset_as_of": dataset.as_of.isoformat(),
            "policy_version": POLICY_VERSION,
            "baseline_overlay": {},
            "llm_called": False,
            "file_sha256": file_hashes,
            "limitations_ru": [
                "Все результаты - локальное ядро, без вызова LLM; это не оценка качества скрытых профилей жюри.",
                "Однопроцессные времена ниже не являются latency production или UI.",
                "Выбор профилей сделан полным перебором исходного набора по указанным условиям, без изменения датасета.",
                "Отметка будущей сессии - демонстрационная операция, не подтверждённое посещение.",
                "Загрузка того же overlay и добавление дублированной отметки - разные проверки.",
            ],
        },
        "dataset_counts": {
            "employees": len(dataset.employees),
            "events": len(dataset.events),
            "skills": len(dataset.skills),
            "history_rows": len(dataset.history),
            "role_profiles": len(dataset.role_profiles),
            "roles": len({e["role"] for e in dataset.employees.values()}),
            "grades": sorted({e["grade"] for e in dataset.employees.values()}),
        },
        "runtime_policy": {"planner": PLANNER},
        "selection": {
            "selected_ids": selected_ids,
            "qualifying_candidates": candidates,
            "criteria_ru": {
                "multi_factor": "Главный tier=0 не улучшает ни один самый низкий открытый навык цели; самый низкий некритический; история достаточна и имеет положительный вклад. Предпочтение закрытию критического порога, затем большему приросту готовности, затем большему вкладу истории.",
                "bridge": "Главный bridge=true совпадает с первым шагом лучшего маршрута и открывает prerequisite следующего шага этого маршрута. Предпочтение кратчайшему маршруту.",
                "no_step_catalog": "Нет рекомендации, требования не выполнены, присутствует причина уровня catalog_fact. Предпочтение отсутствию AUDIENCE_MISMATCH и меньшему числу разных причин.",
                "cross_role": "Целевая роль отличается от текущей, грейд тот же, главный tier=0. Первый ID в отсортированном полном наборе подходящих профилей.",
            },
        },
        "coverage": {
            "employee_denominator": len(snapshots),
            "employees_with_recommendations": completion_count,
            "employees_without_recommendations": len(snapshots) - completion_count,
            "target_requirements_met": sum(
                s["readiness"]["all_requirements_met"] for s in snapshots.values()
            ),
            "cross_role_employees": sum(row["cross_role"] for row in summary.values()),
            "main_bridge_employees": sum(row["main_bridge"] for row in summary.values()),
            "lowest_differs_from_main_employees": sum(
                row["lowest_differs_from_main"] for row in summary.values()
            ),
            "all_lowest_differ_from_main_employees": sum(
                row["all_lowest_differ_from_main"] for row in summary.values()
            ),
            "no_step_reason_counts": dict(reason_counts),
            "recommendation_denominator": recommendation_count,
            "recommendations_allowed": sum(
                c["allowed_as_new_or_active_continuation"] for c in recommendation_checks
            ),
            "recommendations_mandatory": sum(c["mandatory"] for c in recommendation_checks),
            "recommendations_with_history_evidence": sum(
                c["has_history_evidence"] for c in recommendation_checks
            ),
            "minimum_evidence_categories": min(
                len(c["evidence_categories"]) for c in recommendation_checks
            ),
            "recommendations_obeying_growth_rule": sum(
                c["changes_obey_growth_rule"] for c in recommendation_checks
            ),
            "main_completion_denominator": completion_count,
            "main_completions_matching_what_if_readiness": sum(
                c["what_if_matches_completion_readiness"] for c in completion_checks
            ),
            "main_completions_matching_what_if_all_skills": sum(
                c["what_if_matches_completion_all_skills"] for c in completion_checks
            ),
            "main_completions_keeping_grade": sum(c["grade_unchanged"] for c in completion_checks),
        },
        "all_employee_summary": list(summary.values()),
        "recommendation_checks": recommendation_checks,
        "completion_checks": completion_checks,
        "selected": selected,
        "skill_names": {sid: skill["name"] for sid, skill in dataset.skills.items()},
        "hr_before": dashboard,
        "hr_after_demo_completion": {"employee_id": multi_id, "dashboard": hr_after_completion},
        "ui_labels_ru": ui_labels,
        "local_timing_ms": {
            "scope_ru": "Первый последовательный обход build_snapshot в этом процессе; не UI/production.",
            "count": len(snapshot_times_ms),
            "total": sum(snapshot_times_ms),
            "minimum": min(snapshot_times_ms),
            "maximum": max(snapshot_times_ms),
            "all_snapshot_calls": snapshot_times_ms,
            "whole_script_before_serialization": (time.perf_counter() - started) * 1000,
        },
    }


if __name__ == "__main__":
    result = run()
    output = ROOT / "docs" / "evidence" / "local_measurements.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", "utf-8")
    print(
        json.dumps(
            {
                "файл": str(output),
                "профили": result["selection"]["selected_ids"],
                "проверки": result["coverage"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
