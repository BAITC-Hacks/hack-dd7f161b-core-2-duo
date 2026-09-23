from datetime import date

from career_quest.dataset import Dataset, Event, Record

TERMINAL = {"completed", "no_show", "dropped", "declined"}
NEGATIVE_WEIGHT = {"no_show": 0.75, "dropped": 1.0, "declined": 0.25}


def _skills_of(event: Event) -> set[str]:
    return {e["skill_id"] for e in event.develops_skills if e["gain"] > 0}


def voluntary_terminal(ds: Dataset, records: list[Record]) -> list[Record]:
    return [
        r
        for r in records
        if r.status in TERMINAL and r.event_id in ds.events and not ds.events[r.event_id].mandatory
    ]


def _group_affinity(ds: Dataset, rows: list[Record]) -> dict:
    pos = neg = 0.0
    counts = {"completed": 0, "no_show": 0, "dropped": 0, "declined": 0}
    for r in rows:
        w = 0.5 ** (max(0, (ds.as_of - r.date).days) / 180)
        counts[r.status] += 1
        if r.status == "completed":
            pos += w
        else:
            neg += NEGATIVE_WEIGHT[r.status] * w
    n = len(rows)
    insufficient = n < 3 or pos + neg < 1.5
    value = 0.5 if insufficient else (2 + pos) / (4 + pos + neg)
    return {"n": n, **counts, "affinity": value, "insufficient": insufficient}


def candidate_history(
    ds: Dataset, records: list[Record], event: Event, enabled: bool = True
) -> dict:
    """History affinity for one candidate event (spec 9.4): format 0.5, type 0.2, skills 0.3."""
    rows = voluntary_terminal(ds, records)
    skills = _skills_of(event)
    groups = {
        "format": _group_affinity(
            ds, [r for r in rows if ds.events[r.event_id].format == event.format]
        ),
        "type": _group_affinity(ds, [r for r in rows if ds.events[r.event_id].type == event.type]),
        "skills": _group_affinity(
            ds, [r for r in rows if _skills_of(ds.events[r.event_id]) & skills]
        ),
    }
    if not enabled:
        for g in groups.values():
            g["affinity"], g["insufficient"] = 0.5, True
    affinity = (
        0.5 * groups["format"]["affinity"]
        + 0.2 * groups["type"]["affinity"]
        + 0.3 * groups["skills"]["affinity"]
    )
    rated = [
        r
        for r in rows
        if r.feedback_rating is not None
        and (
            ds.events[r.event_id].format == event.format or ds.events[r.event_id].type == event.type
        )
    ]
    feedback = 0.0
    if enabled and len(rated) >= 3:
        ws = [0.5 ** (max(0, (ds.as_of - r.date).days) / 180) for r in rated]
        mean = sum(w * r.feedback_rating for w, r in zip(ws, rated, strict=True)) / sum(ws)
        feedback = max(-1.0, min(1.0, (mean - 3) / 2))
    return {
        "affinity": affinity,
        "groups": groups,
        "feedback_factor": feedback,
        "feedback_n": len(rated),
        "insufficient": all(g["insufficient"] for g in groups.values()),
        "total_observations": len(rows),
    }


def development_health(ds: Dataset, records: list[Record]) -> dict:
    vol = [r for r in records if r.event_id in ds.events and not ds.events[r.event_id].mandatory]
    observed = [r for r in vol if r.status in TERMINAL or r.status == "in_progress"]

    def days(r: Record) -> int:
        return (ds.as_of - r.date).days

    first: date | None = min((r.date for r in observed), default=None)
    base = {
        "observations_count": len(observed),
        "history_observed_from": first.isoformat() if first else None,
    }
    if len(observed) < 3:
        return {**base, "code": "INSUFFICIENT_HISTORY"}
    active = [r for r in vol if r.status == "in_progress"]
    if active:
        return {**base, "code": "IN_PROGRESS", "event_ids": [r.event_id for r in active]}
    if any(r.status == "completed" and days(r) <= 90 for r in vol):
        return {**base, "code": "RECENT_ACTIVITY"}
    misses = [r for r in vol if r.status in ("dropped", "no_show") and days(r) <= 180]
    if len(misses) >= 3:
        return {**base, "code": "FORMAT_REVIEW_SUGGESTED", "misses": len(misses)}
    if not any(r.status == "completed" and days(r) <= 180 for r in vol):
        return {**base, "code": "NO_RECENT_COMPLETION_OBSERVED"}
    return {**base, "code": "OBSERVED_HISTORY_AVAILABLE"}
