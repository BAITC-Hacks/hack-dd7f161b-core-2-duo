from datetime import date

from career_quest.dataset import Dataset, Event, Record


def actual_gain(current: int, gain: int, cap: int) -> int:
    """Dataset growth rule: raise by gain, not above max_level, never lower."""
    return max(0, min(gain, cap - current, 5 - current))


def apply_activity(skills: dict[str, int], event: Event) -> tuple[dict[str, int], list[dict]]:
    new = dict(skills)
    changes = []
    for eff in event.develops_skills:
        sid = eff["skill_id"]
        before = new.get(sid, 0)
        delta = actual_gain(before, eff["gain"], eff["max_level"])
        new[sid] = before + delta
        changes.append(
            {
                "skill_id": sid,
                "before": before,
                "after": before + delta,
                "gain": eff["gain"],
                "cap": eff["max_level"],
                "actual": delta,
            }
        )
    return new, changes


def replay(ds: Dataset, employee: dict, records: list[Record]) -> dict:
    """Assessment + completed records after review date (history_date_proxy_v1)."""
    review = date.fromisoformat(employee["last_review_date"])
    assessed = {sid: 0 for sid in ds.skills}
    assessed.update(employee.get("skills") or {})
    current = dict(assessed)
    applications: dict[str, list[dict]] = {}
    applied = sorted(
        (r for r in records if r.status == "completed" and review < r.date <= ds.as_of),
        key=lambda r: (r.date, r.origin != "source", r.record_id),
    )
    for r in applied:
        event = ds.events.get(r.event_id)
        if not event:
            continue
        current, changes = apply_activity(current, event)
        for c in changes:
            applications.setdefault(c["skill_id"], []).append(
                {
                    **c,
                    "record_id": r.record_id,
                    "event_id": r.event_id,
                    "date": r.date.isoformat(),
                    "date_confidence": "explicit" if r.origin == "app" else "proxy",
                    "origin": r.origin,
                }
            )
    return {
        "assessed": assessed,
        "current": current,
        "applications": applications,
        "review_date": review,
    }
