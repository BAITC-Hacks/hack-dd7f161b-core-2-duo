"""Сводка сохранённых запусков: PYTHONDONTWRITEBYTECODE=1 python3 docs/measure_summary.py."""

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence"


def read(name):
    return json.loads((EVIDENCE / name).read_text())


def span(values):
    return {"min": min(values), "max": max(values)} if values else None


def main():
    names = ["production_measurements.json", "production_demo_measurements.json"]
    runs = [read(name) for name in names]
    rows = [row for run in runs for row in run["ai"]]
    fresh = [
        row
        for row in rows
        if not row["response"].get("cached") and row["response"]["ai_status"] != "not_needed"
    ]
    profiles = [row for run in runs for row in run["profiles"]]
    local = read("local_measurements.json")
    evaluation = read("evaluation_branch.json")
    source_matches = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
        for name, digest in evaluation["conditions"]["source_hashes"].items()
        if name.startswith("career_quest/")
    }
    summary = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 docs/measure_summary.py",
        "input_sha256": {
            name: hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest()
            for name in names + ["local_measurements.json", "evaluation_branch.json"]
        },
        "scope_ru": "Производные значения из сохранённых реальных запусков. repeat_ai исключён. Кэш и not_needed исключены из свежих AI-вызовов. HTTP включает сеть, внутренний elapsed_ms — отдельный показатель.",
        "started_utc": min(run["started_utc"] for run in runs),
        "finished_utc": max(run["finished_utc"] for run in runs),
        "profiles": len(profiles),
        "snapshot_http_ms": span([row["snapshot"]["http_ms"] for row in profiles]),
        "ai": {
            "total": len(rows),
            "fresh": len(fresh),
            "fresh_statuses": dict(Counter(row["response"]["ai_status"] for row in fresh)),
            "fresh_employee_ids": [row["employee_id"] for row in fresh],
            "cached": sum(bool(row["response"].get("cached")) for row in rows),
            "not_needed": sum(row["response"]["ai_status"] == "not_needed" for row in rows),
            "models": sorted({row["response"]["model"] for row in rows}),
            "prompt_versions": sorted({row["response"]["prompt_version"] for row in rows}),
            "fresh_http_ms": span([row["http_ms"] for row in fresh]),
            "fresh_elapsed_ms": span([row["response"]["elapsed_ms"] for row in fresh]),
            "fresh_validations": [row["response"].get("validation", []) for row in fresh],
        },
        "production_checks": {
            key: {
                "passed": sum(row["checks"][key] for row in profiles if "checks" in row),
                "total": sum("checks" in row for row in profiles),
            }
            for key in profiles[0]["checks"]
        },
        "auth": {
            name: [run[name]["http_status"] for run in runs]
            for name in [
                "wrong_actor",
                "employee_hr_access",
                "no_headers_profile",
                "forged_hr_header",
                "forged_employee_headers",
                "employee_forged_hr",
                "wrong_password",
            ]
        },
        "core": local["coverage"],
        "evaluation_branch": {
            "generated_at_utc": evaluation["conditions"]["generated_at_utc"],
            "measured_git_commit": evaluation["conditions"]["git_commit"],
            "engine_hashes_match_worktree": source_matches,
            "failed_cases": len(evaluation["results"]["failed_cases"]),
            "additional_failures": len(
                evaluation["results"]["additional_diagnostics"]["failed_cases"]
            ),
            "scope_ru": "Сохранённый запуск из origin/feature/evaluation; в этой работе заново не запускался. Исходники ядра сопоставлены по SHA-256.",
        },
    }
    e2e = EVIDENCE / "e2e-results.json"
    if e2e.exists():
        summary["e2e"] = read(e2e.name)["stats"]
    (EVIDENCE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in [
                    "profiles",
                    "snapshot_http_ms",
                    "ai",
                    "production_checks",
                    "evaluation_branch",
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
