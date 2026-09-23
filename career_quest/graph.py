"""A read-only graph projection of the same state used by the planner.

Current availability and planned progress remain separate. Catalog edges describe
real skill effects/requirements, never an invented event-to-event prerequisite.
"""

from career_quest.dataset import Dataset
from career_quest.progression import apply_activity


def build_career_graph(
    ds: Dataset,
    target: dict,
    skills: dict[str, int],
    required: dict[str, int],
    critical: list[str],
    catalog: list[dict],
    plan: dict,
    active: dict,
) -> dict:
    best = plan.get("best") or {}
    steps = {s["event_id"]: (i + 1, s) for i, s in enumerate(best.get("steps", []))}
    needed = set(required)
    selected = set(steps)
    # Include providers of preparatory skills too; the fixed point handles cycles.
    while True:
        previous = (len(needed), len(selected))
        for ev in ds.events.values():
            if ev.mandatory:
                continue
            if ev.event_id in selected or any(
                e["skill_id"] in needed and e["gain"] > 0 for e in ev.develops_skills
            ):
                selected.add(ev.event_id)
                needed.update(ev.prerequisites)
        if previous == (len(needed), len(selected)):
            break

    nodes = [
        {
            "id": "goal",
            "kind": "goal",
            "label": f"{target['role']} · {target['grade']}",
            "status": "met" if all(skills.get(s, 0) >= r for s, r in required.items()) else "gap",
            "source": target["source"],
        }
    ]
    edges = []

    def edge(source, dest, kind, **values):
        edges.append(
            {
                "id": f"{kind}:{source}:{dest}",
                "source": source,
                "target": dest,
                "kind": kind,
                **values,
            }
        )

    states = {c["event_id"]: c for c in catalog}
    thresholds = dict(required)
    for eid in sorted(selected, key=lambda e: (steps.get(e, (999,))[0], e)):
        ev = ds.events[eid]
        state = states[eid]
        codes = {r["code"] for r in state["reasons"]}
        order, step = steps.get(eid, (None, None))
        if "ALREADY_COMPLETED" in codes:
            status = "completed"
        elif eid in active and "SNOOZED" not in codes:
            status = "in_progress"
        elif state["eligible"]:
            status = "available"
        elif step and codes == {"PREREQUISITES_UNMET"}:
            status = "after_previous"
        else:
            status = "blocked"
        _, effects = apply_activity(skills, ev)
        prerequisites = []
        for sid, level in sorted(ev.prerequisites.items()):
            thresholds[sid] = max(thresholds.get(sid, 0), level)
            prerequisites.append(
                {
                    "skill_id": sid,
                    "current": skills.get(sid, 0),
                    "required": level,
                    "met": skills.get(sid, 0) >= level,
                }
            )
            edge(f"skill:{sid}", f"activity:{eid}", "prerequisite", level=level)
        for effect in effects:
            sid = effect["skill_id"]
            needed.add(sid)
            edge(
                f"activity:{eid}",
                f"skill:{sid}",
                "develops",
                gain=effect["gain"],
                cap=effect["cap"],
            )
        nodes.append(
            {
                "id": f"activity:{eid}",
                "kind": "activity",
                "event_id": eid,
                "label": ev.title,
                "status": status,
                "reasons": state["reasons"],
                "prerequisites": prerequisites,
                "effects": effects,
                "step": order,
                "plan_step": step,
                "session": state["session"],
                "duration_hours": ev.duration_hours,
                "format": ev.format,
            }
        )
    for sid in sorted(needed, key=lambda s: (s not in critical, s not in required, s)):
        current = skills.get(sid, 0)
        threshold = required.get(sid, thresholds.get(sid))
        nodes.append(
            {
                "id": f"skill:{sid}",
                "kind": "skill",
                "skill_id": sid,
                "label": ds.skills[sid]["name"],
                "current": current,
                "required": required.get(sid),
                "critical": sid in critical,
                "planned": best.get("skills_after", skills).get(sid, current),
                "status": "support"
                if threshold is None
                else "met"
                if current >= threshold
                else "gap",
            }
        )
        if sid in required:
            edge("goal", f"skill:{sid}", "requires", level=required[sid])
    return {"nodes": nodes, "edges": edges}
