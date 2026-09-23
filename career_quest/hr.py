from collections import Counter, defaultdict

from career_quest.dataset import Dataset
from career_quest.engine import HR_CODE, PROOF, build_snapshot, employee_records

INTERVENTION = {
    "NO_SKILL_PROVIDER": "create_learning_activity",
    "CAP_INSUFFICIENT": "add_advanced_level",
    "AUDIENCE_RESTRICTED": "agree_access_or_widen_audience",
    "SCHEDULE_UNAVAILABLE": "schedule_session",
    "PREREQUISITE_BLOCKED": "add_preparatory_module",
    "CATALOG_EXHAUSTED": "add_next_level_activity",
    "USER_DEFERRED": "none_user_choice",
}


def hr_dashboard(ds: Dataset, overlay: dict) -> dict:
    """Aggregates over the same snapshots employees see; no LLM calls, no people ranking."""
    snaps = [build_snapshot(ds, eid, overlay) for eid in ds.employees]
    skill_stats: dict[str, dict] = defaultdict(
        lambda: {
            "required_count": 0,
            "below_target_count": 0,
            "critical_gap_count": 0,
            "gap_sum": 0,
            "actionable": 0,
            "bridge": 0,
            "uncovered": 0,
            "blockers": Counter(),
            "blocker_events": defaultdict(set),
            "role_grades": Counter(),
        }
    )
    no_step = []
    target_met = []
    cards = Counter()
    for s in snaps:
        emp = s["employee"]
        cards["employees"] += 1
        if any(g["critical"] and g["gap"] > 0 for g in s["gaps"]):
            cards["open_critical"] += 1
        for g in s["gaps"]:
            st = skill_stats[g["skill_id"]]
            if g["required"] > 0:
                st["required_count"] += 1
            if g["gap"] > 0:
                st["below_target_count"] += 1
                st["gap_sum"] += g["gap"]
                st["role_grades"][f"{s['target']['role']} / {s['target']['grade']}"] += 1
                if g["critical"]:
                    st["critical_gap_count"] += 1
        for cov in s["coverage"]:
            st = skill_stats[cov["skill_id"]]
            st[cov["status"]] += 1
            for b in cov["blockers"]:
                code = HR_CODE.get(b["code"], b["code"])
                st["blockers"][code] += 1
                st["blocker_events"][code].update(b["event_ids"])
        codes = [r["code"] for r in s["no_step_reasons"]]
        row = {
            "employee_id": emp["employee_id"],
            "full_name": emp["full_name"],
            "role": emp["role"],
            "grade": emp["grade"],
            "target": s["target"],
            "critical_gaps": [g for g in s["gaps"] if g["critical"] and g["gap"] > 0],
            "reasons": s["no_step_reasons"],
            "health": s["health"]["code"],
        }
        if "TARGET_REQUIREMENTS_MET" in codes:
            cards["target_met"] += 1
            target_met.append(row)
        elif not s["recommendations"]:
            cards["no_step"] += 1
            no_step.append(row)
        if s["plan"].get("status") == "search_limited":
            cards["limited"] += 1
    skills_out = []
    for sid, st in skill_stats.items():
        if not st["below_target_count"]:
            continue
        providers = [
            ev.event_id
            for ev in ds.events.values()
            if not ev.mandatory
            and any(e["skill_id"] == sid and e["gain"] > 0 for e in ev.develops_skills)
        ]
        top_blocker = st["blockers"].most_common(1)[0][0] if st["blockers"] else None
        skills_out.append(
            {
                "skill_id": sid,
                "name": ds.skills[sid]["name"],
                "type": ds.skills[sid]["type"],
                "required_count": st["required_count"],
                "below_target_count": st["below_target_count"],
                "critical_gap_count": st["critical_gap_count"],
                "gap_rate": st["below_target_count"] / st["required_count"]
                if st["required_count"]
                else None,
                "avg_gap": st["gap_sum"] / st["below_target_count"],
                "catalog_event_count": len(providers),
                "actionable_employee_count": st["actionable"],
                "bridge_employee_count": st["bridge"],
                "uncovered_employee_count": st["uncovered"],
                "blockers": [
                    {
                        "code": c,
                        "count": n,
                        "event_ids": sorted(st["blocker_events"][c]),
                        "proof_level": next(
                            (PROOF[k] for k, v in HR_CODE.items() if v == c), "eligibility_fact"
                        ),
                    }
                    for c, n in st["blockers"].most_common()
                ],
                "intervention": INTERVENTION.get(top_blocker) if top_blocker else None,
                "top_groups": st["role_grades"].most_common(3),
            }
        )
    skills_out.sort(
        key=lambda x: (-x["critical_gap_count"], -x["below_target_count"], x["skill_id"])
    )
    no_step.sort(key=lambda r: r["employee_id"])
    return {
        "dataset": ds.name,
        "as_of": ds.as_of.isoformat(),
        "population": len(snaps),
        "cards": dict(cards),
        "skills": skills_out,
        "no_step": no_step,
        "target_met": target_met,
        "participation": participation(ds, overlay),
    }


def participation(ds: Dataset, overlay: dict) -> list[dict]:
    rows: dict[str, dict] = {}
    records = (
        record
        for employee_id in ds.employees
        for record in employee_records(ds, employee_id, overlay)
    )
    for r in records:
        ev = ds.events.get(r.event_id)
        if not ev:
            continue
        row = rows.setdefault(
            r.event_id,
            {
                "event_id": ev.event_id,
                "title": ev.title,
                "type": ev.type,
                "format": ev.format,
                "mandatory": ev.mandatory,
                "counts": Counter(),
                "employees": set(),
                "feedback": [],
            },
        )
        row["counts"][r.status] += 1
        if r.origin == "app" and r.status == "completed":
            row["counts"]["app_completed"] += 1
        row["employees"].add(r.employee_id)
        if r.feedback_rating is not None:
            row["feedback"].append(r.feedback_rating)
    out = []
    for row in rows.values():
        c = row["counts"]
        terminal = c["completed"] + c["dropped"] + c["no_show"] + c["declined"]
        out.append(
            {
                **{k: row[k] for k in ("event_id", "title", "type", "format", "mandatory")},
                "counts": dict(c),
                "unique_employees": len(row["employees"]),
                # app_completed is a subset of completed, not another observation
                "observations": sum(n for status, n in c.items() if status != "app_completed"),
                "completion_share": c["completed"] / terminal
                if terminal and not row["mandatory"]
                else None,
                "attendance_proxy": c["completed"] / (c["completed"] + c["no_show"])
                if row["format"] != "self_paced" and (c["completed"] + c["no_show"])
                else None,
                "avg_feedback": sum(row["feedback"]) / len(row["feedback"])
                if row["feedback"]
                else None,
                "feedback_n": len(row["feedback"]),
            }
        )
    out.sort(key=lambda x: (x["mandatory"], x["event_id"]))
    return out
