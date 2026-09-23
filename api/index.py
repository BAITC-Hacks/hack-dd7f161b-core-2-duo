import json
import sys
from pathlib import Path
from typing import Any

# vercel runs this file as the function entry; make the shared package importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, File, Header, HTTPException, UploadFile  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from career_quest.ai import active_model, select_actions  # noqa: E402
from career_quest.dataset import (  # noqa: E402
    Dataset,
    ValidationError,
    build_scenario,
    load_base_dataset,
    read_csv_text,
    validate_scenario,
)
from career_quest.engine import build_snapshot, simulate  # noqa: E402
from career_quest.hr import hr_dashboard  # noqa: E402

app = FastAPI(title="Career Quest API", docs_url="/api/py/docs", openapi_url="/api/py/openapi.json")

_ai_cache: dict[str, dict] = {}


class Overlay(BaseModel):
    # client-held state: localStorage is the store for the demo deployment
    scenario: dict[str, Any] | None = None
    completions: list[dict] = Field(default_factory=list)
    goals: dict[str, dict] = Field(default_factory=dict)
    snoozes: dict[str, list[str]] = Field(default_factory=dict)
    gaming: dict[str, bool] = Field(default_factory=dict)
    history_off: dict[str, bool] = Field(default_factory=dict)


class StateRequest(BaseModel):
    overlay: Overlay = Field(default_factory=Overlay)
    locale: str = "ru"


class SimulateRequest(StateRequest):
    steps: list[str]


def _dataset(overlay: Overlay) -> Dataset:
    base = load_base_dataset()
    if not overlay.scenario:
        return base
    try:
        return build_scenario(base, overlay.scenario)
    except ValidationError as e:
        raise HTTPException(422, {"code": "SCENARIO_INVALID", "errors": e.errors[:50]}) from e


def _authorize(ds: Dataset, employee_id: str, role: str | None, actor: str | None) -> None:
    if employee_id not in ds.employees:
        raise HTTPException(404, {"code": "EMPLOYEE_NOT_FOUND"})
    if role == "hr":
        return
    if role == "employee" and actor == employee_id:
        return
    raise HTTPException(403, {"code": "FORBIDDEN"})


def _skill_names(ds: Dataset) -> dict[str, str]:
    return {k: v["name"] for k, v in ds.skills.items()}


def _public(snap: dict) -> dict:
    out = dict(snap)
    out["shortlist"] = [
        {k: v for k, v in c.items() if k != "path"}
        | {"path_steps": (c.get("path") or {}).get("steps", [])}
        for c in snap["shortlist"]
    ]
    out["recommendations"] = out["shortlist"][: len(snap["recommendations"])]
    return out


@app.get("/api/py/health")
def health() -> dict:
    ds = load_base_dataset()
    return {"status": "ok", "employees": len(ds.employees), "as_of": ds.as_of.isoformat()}


@app.post("/api/py/meta")
def meta(req: StateRequest) -> dict:
    ds = _dataset(req.overlay)
    return {
        "dataset": ds.name,
        "as_of": ds.as_of.isoformat(),
        "employees": [
            {
                k: e.get(k)
                for k in (
                    "employee_id",
                    "full_name",
                    "department",
                    "role",
                    "grade",
                    "preferred_language",
                )
            }
            for e in ds.employees.values()
        ],
        "skills": ds.skills,
        "proficiency_scale": ds.proficiency_scale,
        "events": {
            k: {
                "event_id": v.event_id,
                "title": v.title,
                "description": v.description,
                "type": v.type,
                "format": v.format,
                "duration_hours": v.duration_hours,
                "mandatory": v.mandatory,
                "target_roles": v.target_roles,
                "target_grades": v.target_grades,
                "develops_skills": v.develops_skills,
                "prerequisites": v.prerequisites,
                "upcoming_sessions": [s.isoformat() for s in v.upcoming_sessions],
            }
            for k, v in ds.events.items()
        },
        "targets": sorted({f"{r}|{g}" for r, g in ds.role_profiles}),
    }


@app.post("/api/py/employees/{employee_id}")
def employee_snapshot(
    employee_id: str,
    req: StateRequest,
    x_role: str | None = Header(None),
    x_actor: str | None = Header(None),
) -> dict:
    ds = _dataset(req.overlay)
    _authorize(ds, employee_id, x_role, x_actor)
    return _public(build_snapshot(ds, employee_id, req.overlay.model_dump()))


@app.post("/api/py/employees/{employee_id}/ai")
async def employee_ai(
    employee_id: str,
    req: StateRequest,
    x_role: str | None = Header(None),
    x_actor: str | None = Header(None),
) -> dict:
    ds = _dataset(req.overlay)
    _authorize(ds, employee_id, x_role, x_actor)
    snap = build_snapshot(ds, employee_id, req.overlay.model_dump())
    model = active_model()
    cache_key = f"{snap['fingerprint']}:{req.locale}:{model}"
    if cache_key in _ai_cache:
        return {**_ai_cache[cache_key], "cached": True}
    result = await select_actions(snap, _skill_names(ds), req.locale)
    result["fingerprint"] = snap["fingerprint"]
    if result["ai_status"] == "live_validated":
        _ai_cache[cache_key] = result
    return result


@app.post("/api/py/employees/{employee_id}/simulate")
def employee_simulate(
    employee_id: str,
    req: SimulateRequest,
    x_role: str | None = Header(None),
    x_actor: str | None = Header(None),
) -> dict:
    ds = _dataset(req.overlay)
    _authorize(ds, employee_id, x_role, x_actor)
    return simulate(ds, employee_id, req.overlay.model_dump(), req.steps)


@app.post("/api/py/hr/dashboard")
def dashboard(req: StateRequest, x_role: str | None = Header(None)) -> dict:
    if x_role != "hr":
        raise HTTPException(403, {"code": "HR_ONLY"})
    return hr_dashboard(_dataset(req.overlay), req.overlay.model_dump())


@app.post("/api/py/hr/import/validate")
async def import_validate(
    files: list[UploadFile] = File(...),
    x_role: str | None = Header(None),
) -> dict:
    """Detect employees JSON / history CSV by content, validate, return a normalized scenario."""
    if x_role != "hr":
        raise HTTPException(403, {"code": "HR_ONLY"})
    base = load_base_dataset()
    employees: list[dict] = []
    history: list[dict] = []
    warnings: list[dict] = []
    errors: list[dict] = []
    for f in files:
        raw = await f.read()
        if len(raw) > 10 * 1024 * 1024:
            errors.append({"path": f.filename, "code": "FILE_TOO_LARGE", "detail": ""})
            continue
        text = raw.decode("utf-8-sig", errors="replace")
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                errors.append({"path": f.filename, "code": "INVALID_JSON", "detail": str(e)})
                continue
            if isinstance(data, list):
                employees.extend(data)
                warnings.append({"path": f.filename, "code": "WRAPPER_NORMALIZED", "detail": ""})
            elif "employees" in data:
                employees.extend(data["employees"])
                as_of = (data.get("meta") or {}).get("as_of_date")
                if as_of and as_of != base.as_of.isoformat():
                    errors.append({"path": f.filename, "code": "AS_OF_MISMATCH", "detail": as_of})
            else:
                errors.append(
                    {"path": f.filename, "code": "UNSUPPORTED_JSON", "detail": "expected employees"}
                )
        elif stripped.startswith("record_id"):
            history.extend(read_csv_text(text))
        else:
            errors.append({"path": f.filename, "code": "UNKNOWN_FILE", "detail": ""})
    if not errors:
        v_err, v_warn = validate_scenario(base, employees, history)
        errors += v_err
        warnings += v_warn
    return {
        "ok": not errors,
        "counts": {"employees": len(employees), "history": len(history)},
        "errors": errors[:100],
        "warnings": warnings[:100],
        "employee_ids": [e.get("employee_id") for e in employees],
        "scenario": {"employees": employees, "history": history} if not errors else None,
    }
