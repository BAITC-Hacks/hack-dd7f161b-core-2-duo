from career_quest.dataset import GRADES, Dataset


def resolve_target(ds: Dataset, employee: dict, goal_override: dict | None) -> dict:
    role, grade = employee["role"], employee["grade"]
    mode = (goal_override or {}).get("mode", "inherit")
    if mode == "set":
        return {
            "role": goal_override["target_role"],
            "grade": goal_override["target_grade"],
            "source": "user",
        }
    goal = employee.get("career_goal")
    if mode == "inherit" and goal:
        return {"role": goal["target_role"], "grade": goal["target_grade"], "source": "profile"}
    idx = GRADES.index(grade)
    if idx < len(GRADES) - 1:
        return {"role": role, "grade": GRADES[idx + 1], "source": "provisional_next_grade"}
    return {"role": role, "grade": grade, "source": "current_role_maintenance"}


def calculate_gaps(
    skills: dict[str, int], required: dict[str, int], critical: list[str]
) -> list[dict]:
    gaps = []
    for sid, req in required.items():
        cur = skills.get(sid, 0)
        is_crit = sid in critical
        gaps.append(
            {
                "skill_id": sid,
                "current": cur,
                "required": req,
                "gap": max(0, req - cur),
                "critical": is_crit,
                "weight": 2 if is_crit else 1,
            }
        )
    return gaps


def readiness(gaps: list[dict]) -> dict:
    den = sum(g["weight"] * g["required"] for g in gaps if g["required"] > 0)
    num = sum(g["weight"] * min(g["current"], g["required"]) for g in gaps if g["required"] > 0)
    crit = [g for g in gaps if g["critical"] and g["required"] > 0]
    crit_den = sum(g["required"] for g in crit)
    return {
        "readiness_pct": 100.0 if den == 0 else 100 * num / den,
        "no_requirements": den == 0,
        "critical_readiness_pct": None
        if not crit_den
        else 100 * sum(min(g["current"], g["required"]) for g in crit) / crit_den,
        "critical_gate_met": all(g["gap"] == 0 for g in crit),
        "all_requirements_met": all(g["gap"] == 0 for g in gaps),
        "weighted_gap": sum(g["weight"] * g["gap"] for g in gaps),
        "critical_gap": sum(g["gap"] for g in crit),
    }


def target_requirements(ds: Dataset, target: dict) -> tuple[dict[str, int], list[str]]:
    return ds.role_profiles[(target["role"], target["grade"])]
