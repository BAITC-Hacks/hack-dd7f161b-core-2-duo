import hashlib
import json
import math
import time
from dataclasses import asdict
from datetime import date, timedelta

from career_quest.dataset import REPEATABLE_EVENTS, Dataset, Event, Record
from career_quest.goals import calculate_gaps, readiness, resolve_target, target_requirements
from career_quest.history import candidate_history, development_health
from career_quest.progression import actual_gain, apply_activity, replay

POLICY_VERSION = "cq-policy-v1"
PLANNER = {"max_depth": 4, "beam_width": 40, "max_expanded_states": 5000, "horizon_days": 120}
XP_PER_COMPLETION = 20


# ---------- state assembly ----------


def effective_completions(ds: Dataset, employee_id: str, overlay: dict) -> list[dict]:
    # first completion wins, including completions already present in source history
    if employee_id not in ds.employees:
        return []
    seen = {
        (
            r.event_id,
            (r.session_date or r.date).isoformat() if r.event_id in REPEATABLE_EVENTS else None,
        )
        for r in ds.history_of(employee_id)
        if r.status == "completed"
    }
    completions = overlay.get("completions") or []
    if not isinstance(completions, list):
        return []
    accepted = []
    for c in completions:
        if not isinstance(c, dict) or c.get("employee_id") != employee_id:
            continue
        event_id = c.get("event_id")
        if not isinstance(event_id, str) or event_id not in ds.events:
            continue
        session = c.get("session_date")
        if session not in (None, ""):
            try:
                session = date.fromisoformat(session).isoformat()
            except (TypeError, ValueError):
                continue
        else:
            session = None
        if event_id in REPEATABLE_EVENTS and session is None:
            continue
        key = (event_id, session if event_id in REPEATABLE_EVENTS else None)
        if key in seen:
            continue
        seen.add(key)
        accepted.append(
            {
                "employee_id": employee_id,
                "event_id": event_id,
                "session_date": session,
                "gaming": c.get("gaming") is True,
            }
        )
    return accepted


def employee_records(ds: Dataset, employee_id: str, overlay: dict) -> list[Record]:
    records = ds.history_of(employee_id)
    for i, c in enumerate(effective_completions(ds, employee_id, overlay)):
        records.append(
            Record(
                record_id=f"APP-{i + 1:04d}",
                employee_id=employee_id,
                event_id=c["event_id"],
                date=ds.as_of,
                due_date=None,
                status="completed",
                completion_pct=100,
                score=None,
                feedback_rating=None,
                assigned_by="self",
                origin="app",
                session_date=date.fromisoformat(c["session_date"]) if c["session_date"] else None,
            )
        )
    return records


def fingerprint(ds: Dataset, employee_id: str, overlay: dict, target: dict) -> str:
    mine = {
        "c": effective_completions(ds, employee_id, overlay),
        "g": (overlay.get("goals") or {}).get(employee_id),
        "s": (overlay.get("snoozes") or {}).get(employee_id),
        "h": (overlay.get("history_off") or {}).get(employee_id),
    }
    raw = json.dumps(
        [
            ds.name,
            ds.employees[employee_id],
            [asdict(r) for r in ds.history_of(employee_id)],
            ds.as_of.isoformat(),
            POLICY_VERSION,
            target,
            mine,
        ],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------- eligibility ----------


def audience_ok(event: Event, employee: dict) -> bool:
    return employee["role"] in event.target_roles and employee["grade"] in event.target_grades


def completed_sessions(records: list[Record]) -> set[tuple[str, date]]:
    return {
        (r.event_id, r.session_date or r.date)
        for r in records
        if r.status == "completed" and r.event_id in REPEATABLE_EVENTS
    }


def next_session(
    event: Event,
    available_from: date,
    horizon_end: date | None,
    used_sessions: set[tuple[str, date]] | None = None,
) -> date | None:
    for s in event.upcoming_sessions:
        if (
            s >= available_from
            and (horizon_end is None or s <= horizon_end)
            and (event.event_id, s) not in (used_sessions or set())
        ):
            return s
    return None


def check_eligibility(
    ds: Dataset,
    event: Event,
    employee: dict,
    skills: dict[str, int],
    completed: set[str],
    active: set[str],
    snoozed: set[str],
    available_from: date | None = None,
    used_sessions: set[tuple[str, date]] | None = None,
) -> dict:
    reasons = []
    if event.mandatory:
        reasons.append({"code": "MANDATORY"})
    if not audience_ok(event, employee):
        reasons.append(
            {
                "code": "AUDIENCE_MISMATCH",
                "roles": event.target_roles,
                "grades": event.target_grades,
            }
        )
    unmet = {s: lvl for s, lvl in event.prerequisites.items() if skills.get(s, 0) < lvl}
    if unmet:
        reasons.append(
            {
                "code": "PREREQUISITES_UNMET",
                "unmet": [
                    {"skill_id": s, "required": lvl, "current": skills.get(s, 0)}
                    for s, lvl in unmet.items()
                ],
            }
        )
    if event.event_id in completed and event.event_id not in REPEATABLE_EVENTS:
        reasons.append({"code": "ALREADY_COMPLETED"})
    if event.event_id in active:
        reasons.append({"code": "ACTIVE_ACTIVITY_ALREADY_SELECTED"})
    session = None
    if event.scheduled:
        session = next_session(event, available_from or ds.as_of, None, used_sessions)
        if session is None:
            reasons.append({"code": "NO_UPCOMING_SESSION"})
    if event.event_id in snoozed:
        reasons.append({"code": "SNOOZED"})
    return {"eligible": not reasons, "reasons": reasons, "session": session}


# ---------- planner (bounded beam search, spec 11) ----------


def useful_skill_set(
    ds: Dataset, gaps: list[dict], skills: dict[str, int], employee: dict
) -> set[str]:
    useful = {g["skill_id"] for g in gaps if g["gap"] > 0}
    changed = True
    while changed:
        changed = False
        for ev in ds.events.values():
            if ev.mandatory or not audience_ok(ev, employee):
                continue
            if any(e["skill_id"] in useful and e["gain"] > 0 for e in ev.develops_skills):
                for s, lvl in ev.prerequisites.items():
                    if skills.get(s, 0) < lvl and s not in useful:
                        useful.add(s)
                        changed = True
    return useful


def _finish(event: Event, start: date, remaining_hours: float | None = None) -> date:
    hours = event.duration_hours if remaining_hours is None else remaining_hours
    if event.scheduled and remaining_hours is None:
        return start + timedelta(days=max(1, math.ceil(hours / 8)))
    return start + timedelta(days=max(1, math.ceil(hours / 4)))


def plan_paths(
    ds: Dataset,
    employee: dict,
    skills: dict[str, int],
    required: dict[str, int],
    critical: list[str],
    completed: set[str],
    active: dict[str, Record],
    snoozed: set[str],
    used_sessions: set[tuple[str, date]] | None = None,
) -> dict:
    t0 = time.perf_counter()
    gaps0 = calculate_gaps(skills, required, critical)
    useful = useful_skill_set(ds, gaps0, skills, employee)
    horizon_end = ds.as_of + timedelta(days=PLANNER["horizon_days"])
    pool = [
        ev
        for ev in ds.events.values()
        if not ev.mandatory
        and audience_ok(ev, employee)
        and ev.event_id not in snoozed
        and (ev.event_id not in completed or ev.event_id in REPEATABLE_EVENTS)
    ]

    def metrics(sk: dict[str, int]) -> tuple[int, int]:
        r = readiness(calculate_gaps(sk, required, critical))
        return r["critical_gap"], r["weighted_gap"]

    def expand(state: dict) -> list[dict]:
        out = []
        options = []
        if not state["steps"]:
            for eid, rec in active.items():
                ev = ds.events[eid]
                remaining = ev.duration_hours * (1 - rec.completion_pct / 100)
                options.append((ev, "continue", None, ds.as_of, _finish(ev, ds.as_of, remaining)))
        for ev in pool:
            if ev.event_id in state["used"] or ev.event_id in active:
                continue
            if any(state["skills"].get(s, 0) < lvl for s, lvl in ev.prerequisites.items()):
                continue
            if ev.scheduled:
                sess = next_session(ev, state["avail"], horizon_end, used_sessions)
                if sess is None:
                    continue
                options.append((ev, "start", sess, sess, _finish(ev, sess)))
            else:
                if state["avail"] > horizon_end:
                    continue
                options.append((ev, "start", None, state["avail"], _finish(ev, state["avail"])))
        for ev, kind, sess, start, finish in options:
            gains = {
                e["skill_id"]: actual_gain(
                    state["skills"].get(e["skill_id"], 0), e["gain"], e["max_level"]
                )
                for e in ev.develops_skills
            }
            if not any(v > 0 and s in useful for s, v in gains.items()):
                continue
            new_skills, changes = apply_activity(state["skills"], ev)
            cg, wg = metrics(new_skills)
            out.append(
                {
                    "skills": new_skills,
                    "used": state["used"] | {ev.event_id},
                    "avail": finish,
                    "effort": state["effort"] + ev.duration_hours,
                    "cg": cg,
                    "wg": wg,
                    "steps": state["steps"]
                    + [
                        {
                            "event_id": ev.event_id,
                            "action_kind": kind,
                            "session": sess.isoformat() if sess else None,
                            "estimated_start": start.isoformat(),
                            "estimated_finish": finish.isoformat(),
                            "changes": [c for c in changes if c["actual"] > 0],
                        }
                    ],
                }
            )
        return out

    def key(s: dict):
        return (s["cg"], s["wg"], s["effort"], s["avail"], tuple(x["event_id"] for x in s["steps"]))

    cg0, wg0 = metrics(skills)
    root = {
        "skills": skills,
        "used": frozenset(),
        "avail": ds.as_of,
        "effort": 0.0,
        "cg": cg0,
        "wg": wg0,
        "steps": [],
    }
    beam = [root]
    best = None
    by_first: dict[str, dict] = {}
    expanded = 0
    limited = False
    seen: set = set()
    for _depth in range(PLANNER["max_depth"]):
        children = []
        for st in beam:
            if st["wg"] == 0:
                continue
            for ch in expand(st):
                sig = (tuple(sorted(ch["skills"].items())), ch["used"], ch["avail"])
                if sig in seen:
                    continue
                seen.add(sig)
                children.append(ch)
                expanded += 1
                first = ch["steps"][0]["event_id"]
                if first not in by_first or key(ch) < key(by_first[first]):
                    by_first[first] = ch
                if best is None or key(ch) < key(best):
                    best = ch
            if expanded >= PLANNER["max_expanded_states"]:
                limited = True
                break
        if not children or limited:
            break
        children.sort(key=key)
        beam = children[: PLANNER["beam_width"]]

    def render(st: dict | None) -> dict | None:
        if not st:
            return None
        return {
            "steps": st["steps"],
            "critical_gap_after": st["cg"],
            "weighted_gap_after": st["wg"],
            "effort_hours": st["effort"],
            "skills_after": st["skills"],
        }

    status = "no_path_found"
    if best:
        status = "target_reached_in_plan" if best["wg"] == 0 else "partial_progress"
    if limited:
        status = "search_limited"
    return {
        "status": status,
        "best": render(best),
        "by_first": {k: render(v) for k, v in by_first.items()},
        "explored_states": expanded,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "assumptions": {
            **PLANNER,
            "self_paced_hours_per_day": 4,
            "scheduled_days": "max(1, ceil(duration_hours/8))",
        },
    }


# ---------- ranking + evidence ----------


def _event_brief(ev: Event) -> dict:
    return {
        "event_id": ev.event_id,
        "title": ev.title,
        "type": ev.type,
        "format": ev.format,
        "duration_hours": ev.duration_hours,
    }


def _unlocked(
    ds: Dataset, employee: dict, before: dict[str, int], after: dict[str, int], completed: set[str]
) -> list[str]:
    out = []
    for ev in ds.events.values():
        if ev.mandatory or not audience_ok(ev, employee) or ev.event_id in completed:
            continue
        was = all(before.get(s, 0) >= lvl for s, lvl in ev.prerequisites.items())
        now = all(after.get(s, 0) >= lvl for s, lvl in ev.prerequisites.items())
        if now and not was:
            out.append(ev.event_id)
    return out


def score_candidate(
    ds: Dataset,
    ev: Event,
    kind: str,
    session: date | None,
    ctx: dict,
    remaining_hours: float,
) -> dict | None:
    gaps = ctx["gaps"]
    gap_by = {g["skill_id"]: g for g in gaps}
    skills = ctx["skills"]
    D = sum(g["weight"] * g["gap"] for g in gaps)
    crit_gap = sum(g["gap"] for g in gaps if g["critical"])
    new_skills, changes = apply_activity(skills, ev)
    useful = {}
    for c in changes:
        g = gap_by.get(c["skill_id"])
        if g and g["gap"] > 0 and c["actual"] > 0:
            useful[c["skill_id"]] = min(g["gap"], c["actual"])
    G = sum(gap_by[s]["weight"] * v for s, v in useful.items()) / max(1, D)
    crit_useful = sum(v for s, v in useful.items() if gap_by[s]["critical"])
    C = crit_useful / max(1, crit_gap)
    unlocks = _unlocked(ds, ctx["employee"], skills, new_skills, ctx["completed"])
    path = ctx["plan"]["by_first"].get(ev.event_id)
    U = 0.0
    path_crit_reduction = 0
    bridge = False
    if path and len(path["steps"]) > 1:
        later = {s["event_id"] for s in path["steps"][1:]}
        bridge = bool(later & set(unlocks))
        if bridge:
            direct_w = sum(gap_by[s]["weight"] * v for s, v in useful.items())
            extra = (D - path["weighted_gap_after"]) - direct_w
            U = max(0.0, extra) / max(1, D) * 0.75 ** (len(path["steps"]) - 1)
            path_crit_reduction = crit_gap - path["critical_gap_after"] - crit_useful
    if crit_gap > 0 and (crit_useful > 0 or (bridge and path_crit_reduction > 0)):
        tier = 0
    elif G > 0:
        tier = 1
    elif U > 0:
        tier = 2
    else:
        return None
    hist = candidate_history(ds, ctx["records"], ev, ctx["history_enabled"])
    days_wait = (session - ds.as_of).days if session else 0
    breakdown = {
        "gap_closure": 60 * G,
        "critical_closure": 25 * C,
        "path_value": 20 * U,
        "history_fit": 10 * (2 * hist["affinity"] - 1),
        "feedback": 3 * hist["feedback_factor"],
        "work_format": 2.0
        if ctx["employee"].get("work_format") == "remote" and ev.format in ("online", "self_paced")
        else 0.0,
        "continuation": 3.0 if kind == "continue" else 0.0,
        "effort_penalty": -min(5.0, remaining_hours / 8),
        "wait_penalty": -min(5.0, days_wait / 30),
    }
    return {
        **_event_brief(ev),
        "action_kind": kind,
        "session": session.isoformat() if session else None,
        "tier": tier,
        "score": round(sum(breakdown.values()), 2),
        "breakdown": {k: round(v, 2) for k, v in breakdown.items()},
        "changes": changes,
        "useful": useful,
        "unlocks": unlocks,
        "bridge": bridge,
        "path": path,
        "history": hist,
        "remaining_hours": remaining_hours,
        "prerequisites": ev.prerequisites,
    }


def build_facts(cand: dict, ctx: dict) -> list[dict]:
    emp = ctx["employee"]
    gap_by = {g["skill_id"]: g for g in ctx["gaps"]}
    facts: list[dict] = []

    def add(category: str, code: str, **values):
        facts.append(
            {"id": f"f{len(facts) + 1:02d}", "category": category, "code": code, "values": values}
        )

    add(
        "profile",
        "PROFILE_CONTEXT",
        role=emp["role"],
        grade=emp["grade"],
        tenure_months=emp.get("tenure_months"),
    )
    t = ctx["target"]
    add(
        "target_requirement",
        "TARGET_CONTEXT",
        target_role=t["role"],
        target_grade=t["grade"],
        source=t["source"],
    )
    for c in cand["changes"]:
        g = gap_by.get(c["skill_id"])
        if g and g["gap"] > 0:
            add(
                "target_requirement",
                "REQUIREMENT",
                skill_id=c["skill_id"],
                required=g["required"],
                critical=g["critical"],
            )
            add(
                "skill_gap",
                "SKILL_GAP",
                skill_id=c["skill_id"],
                current=g["current"],
                required=g["required"],
                gap=g["gap"],
            )
    for c in cand["changes"]:
        if c["actual"] > 0:
            g = gap_by.get(c["skill_id"])
            gap_after = max(0, g["required"] - c["after"]) if g else None
            add(
                "event_effect",
                "EVENT_EFFECT",
                skill_id=c["skill_id"],
                before=c["before"],
                after=c["after"],
                gain=c["gain"],
                cap=c["cap"],
                gap_after=gap_after,
            )
    h = cand["history"]
    if h["insufficient"]:
        add(
            "history",
            "HISTORY_INSUFFICIENT",
            total_nonmandatory_terminal_observations=h["total_observations"],
        )
    else:
        for name, grp in h["groups"].items():
            if not grp["insufficient"]:
                scope = {name: cand[name]} if name in {"format", "type"} else {}
                add(
                    "history",
                    "HISTORY_GROUP",
                    group=name,
                    **scope,
                    n=grp["n"],
                    completed=grp["completed"],
                    no_show=grp["no_show"],
                    dropped=grp["dropped"],
                    declined=grp["declined"],
                    affinity=round(grp["affinity"], 2),
                )
    add(
        "eligibility",
        "ELIGIBLE",
        action_kind=cand["action_kind"],
        session=cand["session"],
        format=cand["format"],
        prerequisites=cand["prerequisites"],
    )
    if cand["bridge"] and cand["unlocks"]:
        add("prerequisite_path", "UNLOCKS", event_ids=cand["unlocks"])
    remaining = []
    for g in ctx["gaps"]:
        if g["critical"] and g["gap"] > 0:
            after = next(
                (c["after"] for c in cand["changes"] if c["skill_id"] == g["skill_id"]),
                g["current"],
            )
            if after < g["required"]:
                remaining.append(
                    {
                        "skill_id": g["skill_id"],
                        "after": after,
                        "required": g["required"],
                        "critical": True,
                        "skill": ctx["skill_names"].get(g["skill_id"], g["skill_id"]),
                    }
                )
    if remaining:
        add("limitation", "CRITICAL_REMAINING", skills=remaining)
    return facts


# ---------- diagnostics ----------

HR_CODE = {
    "NO_RELEVANT_CATALOG_EVENT": "NO_SKILL_PROVIDER",
    "SKILL_CAP_CEILING": "CAP_INSUFFICIENT",
    "AUDIENCE_MISMATCH": "AUDIENCE_RESTRICTED",
    "NO_UPCOMING_SESSION": "SCHEDULE_UNAVAILABLE",
    "PREREQUISITES_UNMET": "PREREQUISITE_BLOCKED",
    "ONLY_ALREADY_COMPLETED_EVENTS": "CATALOG_EXHAUSTED",
    "ALL_RELEVANT_ACTIONS_SNOOZED": "USER_DEFERRED",
}
PROOF = {
    "NO_RELEVANT_CATALOG_EVENT": "catalog_fact",
    "SKILL_CAP_CEILING": "catalog_fact",
    "AUDIENCE_MISMATCH": "eligibility_fact",
    "NO_UPCOMING_SESSION": "eligibility_fact",
    "PREREQUISITES_UNMET": "eligibility_fact",
    "ONLY_ALREADY_COMPLETED_EVENTS": "eligibility_fact",
    "ALL_RELEVANT_ACTIONS_SNOOZED": "user_choice",
    "ACTIVE_ACTIVITY_ALREADY_SELECTED": "user_choice",
    "NO_PATH_WITHIN_HORIZON": "search_limit",
}


def skill_blockers(ds: Dataset, g: dict, catalog: list[dict]) -> list[dict]:
    """Why a gap skill has no direct executable step; one entry per distinct reason."""
    sid = g["skill_id"]
    providers = [
        (ev, st)
        for ev, st in ((ds.events[c["event_id"]], c) for c in catalog)
        if not ev.mandatory
        and any(e["skill_id"] == sid and e["gain"] > 0 for e in ev.develops_skills)
    ]
    if not providers:
        return [{"code": "NO_RELEVANT_CATALOG_EVENT", "skill_id": sid, "event_ids": []}]
    capped = [
        ev.event_id
        for ev, _ in providers
        if all(e["max_level"] <= g["current"] for e in ev.develops_skills if e["skill_id"] == sid)
    ]
    if len(capped) == len(providers):
        return [{"code": "SKILL_CAP_CEILING", "skill_id": sid, "event_ids": capped}]
    found: dict[str, list[str]] = {}
    mapping = {
        "AUDIENCE_MISMATCH": "AUDIENCE_MISMATCH",
        "PREREQUISITES_UNMET": "PREREQUISITES_UNMET",
        "NO_UPCOMING_SESSION": "NO_UPCOMING_SESSION",
        "ALREADY_COMPLETED": "ONLY_ALREADY_COMPLETED_EVENTS",
        "SNOOZED": "ALL_RELEVANT_ACTIONS_SNOOZED",
        "ACTIVE_ACTIVITY_ALREADY_SELECTED": "ACTIVE_ACTIVITY_ALREADY_SELECTED",
    }
    for ev, st in providers:
        if ev.event_id in capped:
            continue
        for r in st["reasons"]:
            code = mapping.get(r["code"])
            if code:
                found.setdefault(code, []).append(ev.event_id)
    return [{"code": c, "skill_id": sid, "event_ids": ids} for c, ids in found.items()]


# ---------- snapshot ----------


def build_snapshot(ds: Dataset, employee_id: str, overlay: dict, with_plan: bool = True) -> dict:
    employee = ds.employees[employee_id]
    records = employee_records(ds, employee_id, overlay)
    used_sessions = completed_sessions(records)
    rp = replay(ds, employee, records)
    skills = rp["current"]
    goal_override = (overlay.get("goals") or {}).get(employee_id)
    target = resolve_target(ds, employee, goal_override)
    required, critical = target_requirements(ds, target)
    gaps = calculate_gaps(skills, required, critical)
    rd = readiness(gaps)
    completed = {r.event_id for r in records if r.status == "completed"}
    latest: dict[str, Record] = {}
    for r in sorted(records, key=lambda r: (r.date, r.record_id)):
        latest[r.event_id] = r
    active = {
        eid: r
        for eid, r in latest.items()
        if r.status == "in_progress" and not ds.events[eid].mandatory and eid not in completed
    }
    snoozed = set((overlay.get("snoozes") or {}).get(employee_id) or [])
    history_enabled = not (overlay.get("history_off") or {}).get(employee_id)

    catalog = []
    for ev in ds.events.values():
        st = check_eligibility(
            ds, ev, employee, skills, completed, set(active), snoozed, used_sessions=used_sessions
        )
        catalog.append(
            {
                **_event_brief(ev),
                **st,
                "session": st["session"].isoformat() if st["session"] else None,
            }
        )

    plan = (
        plan_paths(
            ds, employee, skills, required, critical, completed, active, snoozed, used_sessions
        )
        if with_plan and not rd["all_requirements_met"]
        else {
            "status": "not_run",
            "best": None,
            "by_first": {},
            "explored_states": 0,
            "elapsed_ms": 0,
            "assumptions": {},
        }
    )
    ctx = {
        "skill_names": {sid: skill["name"] for sid, skill in ds.skills.items()},
        "employee": employee,
        "skills": skills,
        "gaps": gaps,
        "target": target,
        "completed": completed,
        "records": records,
        "plan": plan,
        "history_enabled": history_enabled,
    }
    candidates = []
    if not rd["all_requirements_met"]:
        for eid, rec in active.items():
            if eid in snoozed:
                continue
            ev = ds.events[eid]
            rem = ev.duration_hours * (1 - rec.completion_pct / 100)
            c = score_candidate(ds, ev, "continue", None, ctx, rem)
            if c:
                candidates.append(c)
        for st in catalog:
            if st["eligible"]:
                ev = ds.events[st["event_id"]]
                sess = date.fromisoformat(st["session"]) if st["session"] else None
                c = score_candidate(ds, ev, "start", sess, ctx, ev.duration_hours)
                if c:
                    candidates.append(c)
    candidates.sort(
        key=lambda c: (
            c["tier"],
            -c["score"],
            c["remaining_hours"],
            c["session"] or "",
            c["event_id"],
        )
    )
    for c in candidates:
        c["facts"] = build_facts(c, ctx)
    top = candidates[:3]

    no_step: list[dict] = []
    gap_open = [g for g in gaps if g["gap"] > 0]
    coverage = []
    for g in gap_open:
        direct = [c["event_id"] for c in candidates if g["skill_id"] in c["useful"]]
        bridge = [
            c["event_id"]
            for c in candidates
            if c["bridge"]
            and (c["path"] or {}).get("skills_after", {}).get(g["skill_id"], 0) > g["current"]
        ]
        blockers = [] if direct else skill_blockers(ds, g, catalog)
        status = "actionable" if direct else ("bridge" if bridge else "uncovered")
        coverage.append({**g, "status": status, "direct_event_ids": direct, "blockers": blockers})
    if rd["all_requirements_met"]:
        no_step = [{"code": "TARGET_REQUIREMENTS_MET", "proof_level": "catalog_fact"}]
    elif not top:
        seen_codes: dict[str, dict] = {}
        for cov in coverage:
            for b in cov["blockers"]:
                entry = seen_codes.setdefault(
                    b["code"], {"code": b["code"], "skills": [], "event_ids": set()}
                )
                entry["skills"].append(b["skill_id"])
                entry["event_ids"].update(b["event_ids"])
        no_step = [
            {
                **v,
                "event_ids": sorted(v["event_ids"]),
                "proof_level": PROOF.get(k, "eligibility_fact"),
            }
            for k, v in seen_codes.items()
        ] or [
            {
                "code": "NO_PATH_WITHIN_HORIZON",
                "skills": [g["skill_id"] for g in gap_open],
                "event_ids": [],
                "proof_level": "search_limit",
            }
        ]

    skill_rows = []
    for sid in sorted(set(required) | {s for s, v in rp["assessed"].items() if v > 0}):
        g = next((x for x in gaps if x["skill_id"] == sid), None)
        skill_rows.append(
            {
                "skill_id": sid,
                "assessed": rp["assessed"].get(sid, 0),
                "current": skills.get(sid, 0),
                "required": g["required"] if g else None,
                "critical": bool(g and g["critical"]),
                "gap": g["gap"] if g else 0,
                "in_target": g is not None,
                "applications": rp["applications"].get(sid, []),
            }
        )

    gamification = gamification_state(ds, employee_id, overlay, records, target)
    return {
        "employee": {
            k: employee.get(k)
            for k in (
                "employee_id",
                "full_name",
                "department",
                "role",
                "grade",
                "tenure_months",
                "work_format",
                "preferred_language",
                "last_review_date",
                "hire_date",
                "career_goal",
            )
        },
        "as_of": ds.as_of.isoformat(),
        "dataset": ds.name,
        "fingerprint": fingerprint(ds, employee_id, overlay, target),
        "policy_version": POLICY_VERSION,
        "target": target,
        "readiness": rd,
        "gaps": gaps,
        "skills": skill_rows,
        "coverage": coverage,
        "recommendations": top,
        "shortlist": candidates[:8],
        "alternatives_considered": [
            {
                k: c[k]
                for k in (
                    "event_id",
                    "title",
                    "tier",
                    "score",
                    "breakdown",
                    "format",
                    "type",
                    "useful",
                )
            }
            for c in candidates[3:8]
        ],
        "no_step_reasons": no_step,
        "plan": {k: v for k, v in plan.items() if k != "by_first"},
        "catalog": catalog,
        "history": [
            {
                "record_id": r.record_id,
                "event_id": r.event_id,
                "title": ds.events[r.event_id].title if r.event_id in ds.events else r.event_id,
                "date": r.date.isoformat(),
                "status": r.status,
                "completion_pct": r.completion_pct,
                "score": r.score,
                "feedback_rating": r.feedback_rating,
                "assigned_by": r.assigned_by,
                "mandatory": ds.events[r.event_id].mandatory if r.event_id in ds.events else False,
                "origin": r.origin,
            }
            for r in sorted(records, key=lambda r: (r.date, r.record_id), reverse=True)
        ],
        "active": list(active),
        "snoozed": sorted(snoozed),
        "health": development_health(ds, records),
        "gamification": gamification,
    }


def gamification_state(
    ds: Dataset, employee_id: str, overlay: dict, records: list[Record], target: dict
) -> dict:
    """XP only for app completions made with opt-in, voluntary, positive real gain."""
    opt_in = bool((overlay.get("gaming") or {}).get(employee_id))
    employee = ds.employees[employee_id]
    review = date.fromisoformat(employee["last_review_date"])
    skills = {sid: 0 for sid in ds.skills} | (employee.get("skills") or {})
    required, critical = target_requirements(ds, target)
    xp = 0
    claims = 0
    critical_closed = []
    app_flags = {
        f"APP-{i + 1:04d}": c["gaming"]
        for i, c in enumerate(effective_completions(ds, employee_id, overlay))
    }
    for r in sorted(
        (r for r in records if r.status == "completed" and review < r.date <= ds.as_of),
        key=lambda r: (r.date, r.origin != "source", r.record_id),
    ):
        ev = ds.events[r.event_id]
        before = dict(skills)
        skills, changes = apply_activity(skills, ev)
        if r.origin != "app":
            continue
        if (
            not app_flags.get(r.record_id)
            or ev.mandatory
            or not any(c["actual"] > 0 for c in changes)
        ):
            continue
        xp += XP_PER_COMPLETION
        claims += 1
        for sid in critical:
            if before.get(sid, 0) < required[sid] <= skills.get(sid, 0):
                critical_closed.append(
                    {
                        "skill_id": sid,
                        "event_id": ev.event_id,
                        "target": f"{target['role']} {target['grade']}",
                    }
                )
    return {
        "opt_in": opt_in,
        "xp": xp,
        "level": 1 + xp // 100,
        "progress": xp % 100,
        "badges": [
            {"code": "FIRST_STEP", "progress": min(claims, 1), "of": 1},
            {"code": "FIVE_STEPS", "progress": min(claims, 5), "of": 5},
            {
                "code": "CRITICAL_GAP_CLOSED",
                "progress": min(len(critical_closed), 1),
                "of": 1,
                "refs": critical_closed,
            },
        ],
    }


# ---------- what-if ----------


def simulate(ds: Dataset, employee_id: str, overlay: dict, steps: list[str]) -> dict:
    employee = ds.employees[employee_id]
    records = employee_records(ds, employee_id, overlay)
    used_sessions = completed_sessions(records)
    skills = replay(ds, employee, records)["current"]
    target = resolve_target(ds, employee, (overlay.get("goals") or {}).get(employee_id))
    required, critical = target_requirements(ds, target)
    completed = {r.event_id for r in records if r.status == "completed"}
    active = {r.event_id for r in records if r.status == "in_progress"} - completed
    before = readiness(calculate_gaps(skills, required, critical))
    out_steps = []
    avail = ds.as_of
    effort = 0.0
    cur = dict(skills)
    used = set(completed)

    def eligible_set(sk: dict[str, int], used_ids: set[str]) -> set[str]:
        return {
            ev.event_id
            for ev in ds.events.values()
            if check_eligibility(
                ds, ev, employee, sk, used_ids, set(), set(), used_sessions=used_sessions
            )["eligible"]
        }

    for eid in steps[:4]:
        ev = ds.events.get(eid)
        if not ev:
            return {"error": {"code": "UNKNOWN_EVENT", "event_id": eid}}
        is_continue = eid in active and not out_steps
        if not is_continue:
            st = check_eligibility(ds, ev, employee, cur, used, set(), set(), avail, used_sessions)
            if not st["eligible"]:
                return {
                    "error": {"code": "STEP_BLOCKED", "event_id": eid, "reasons": st["reasons"]}
                }
            start = st["session"] or avail
        else:
            start = ds.as_of
        elig_before = eligible_set(cur, used)
        rd_before = readiness(calculate_gaps(cur, required, critical))
        cur, changes = apply_activity(cur, ev)
        used = used | {eid}
        if eid in REPEATABLE_EVENTS and not is_continue:
            used_sessions.add((eid, start))
        rd_after = readiness(calculate_gaps(cur, required, critical))
        finish = _finish(ev, start)
        avail = finish
        effort += ev.duration_hours
        out_steps.append(
            {
                "event_id": eid,
                "title": ev.title,
                "changes": changes,
                "readiness_before": rd_before["readiness_pct"],
                "readiness_after": rd_after["readiness_pct"],
                "readiness_delta_pp": rd_after["readiness_pct"] - rd_before["readiness_pct"],
                "new_unlocks": sorted(eligible_set(cur, used) - elig_before),
                "estimated_start": start.isoformat(),
                "estimated_finish": finish.isoformat(),
            }
        )
    after_gaps = calculate_gaps(cur, required, critical)
    after = readiness(after_gaps)
    return {
        "is_projection": True,
        "target": target,
        "before": {**before, "skills": skills},
        "steps": out_steps,
        "after": {
            **after,
            "skills": cur,
            "remaining_gaps": [g for g in after_gaps if g["gap"] > 0],
        },
        "total_effort_hours": effort,
    }
