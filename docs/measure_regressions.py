"""Локальные воспроизводимые наблюдения исправлений, без сетевого вызова LLM.

Запуск Python с установленными зависимостями проекта:
PYTHONDONTWRITEBYTECODE=1 python docs/measure_regressions.py
"""

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from career_quest.ai import active_model, model_params, select_actions  # noqa: E402
from career_quest.auth import SESSION_TTL_SECONDS  # noqa: E402
from career_quest.dataset import build_scenario, load_base_dataset, validate_scenario  # noqa: E402
from career_quest.engine import build_snapshot, simulate  # noqa: E402


def main():
    ds = load_base_dataset()
    source = {"name": "same-name", "employees": [deepcopy(ds.employees["E0028"])], "history": []}
    changed = deepcopy(source)
    changed["employees"][0]["skills"]["SK_SYSTEM_DESIGN"] = 0
    a = build_snapshot(build_scenario(ds, source), "E0028", {})
    b = build_snapshot(build_scenario(ds, changed), "E0028", {})
    changed_history = deepcopy(source)
    changed_history["history"] = [
        {
            "record_id": "DOCS_PROBE",
            "employee_id": "E0028",
            "event_id": "EV_005",
            "date": ds.as_of.isoformat(),
            "status": "declined",
            "assigned_by": "self",
        }
    ]
    c = build_snapshot(build_scenario(ds, changed_history), "E0028", {})
    fixture = json.loads((ROOT / "tests/fixtures_continue_repro.json").read_text())
    started = build_scenario(ds, {"name": "continue", **fixture})
    snap = build_snapshot(started, "E9007", {})
    sim = simulate(started, "E9007", {}, ["EV_018"])
    emp = deepcopy(ds.employees["E0028"])
    emp["last_review_date"] = None
    date_errors, _ = validate_scenario(ds, [emp], [])
    row = {
        "record_id": "X1",
        "employee_id": "E0028",
        "event_id": "EV_005",
        "date": "2026-05-01",
        "due_date": "not-a-date",
        "status": "completed",
        "completion_pct": "100",
        "score": "abc",
        "feedback_rating": "9",
        "assigned_by": "self",
    }
    history_errors, _ = validate_scenario(ds, [ds.employees["E0028"]], [row])
    base = build_snapshot(ds, "E0143", {})
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
        no_key = asyncio.run(
            select_actions(base, {k: v["name"] for k, v in ds.skills.items()}, "ru")
        )
    report = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "python_executable": sys.executable,
        "command": "PYTHONDONTWRITEBYTECODE=1 python docs/measure_regressions.py",
        "scope_ru": "Локальные вызовы текущего кода; без production и без запроса OpenAI. Ключ временно отсутствует только в этом процессе.",
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "career_quest").glob("*.py"))
        },
        "runtime": {
            "default_model": active_model(),
            "model_params": model_params(active_model()),
            "session_ttl_seconds": SESSION_TTL_SECONDS,
        },
        "no_key": no_key,
        "fingerprint": {
            "source": a["fingerprint"],
            "profile_changed": b["fingerprint"],
            "history_changed": c["fingerprint"],
            "changes_with_profile": a["fingerprint"] != b["fingerprint"],
            "changes_with_history": a["fingerprint"] != c["fingerprint"],
        },
        "continue": {
            "fixture": "tests/fixtures_continue_repro.json",
            "employee_id": "E9007",
            "event_id": "EV_018",
            "duration_hours": started.events["EV_018"].duration_hours,
            "history": fixture["history"],
            "plan": snap["plan"]["best"],
            "simulation": sim,
        },
        "import_errors": {"last_review_date": date_errors, "history": history_errors},
    }
    output = ROOT / "docs/evidence/regressions.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(output.relative_to(ROOT)),
                "no_key": no_key["ai_status"],
                "profile_fingerprint_changed": report["fingerprint"]["changes_with_profile"],
                "history_fingerprint_changed": report["fingerprint"]["changes_with_history"],
                "remaining_hours": sim["total_effort_hours"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
