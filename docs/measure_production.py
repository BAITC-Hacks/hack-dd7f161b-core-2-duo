"""Замер production с подписанными сессиями; запись только в docs/.

Запуск: PYTHONDONTWRITEBYTECODE=1 python3 docs/measure_production.py
Отметки передаются временным overlay, бизнес-состояние сервера не сохраняется.
Токены остаются в памяти процесса и stdin curl, в файлы и логи не попадают.
"""

import argparse
import csv
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from career_quest.dataset import load_base_dataset  # noqa: E402

BASE = "https://career-quest-bay.vercel.app"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("employee_ids", nargs="*")
parser.add_argument("--output", default="docs/evidence/production_measurements.json")
parser.add_argument("--skip-import", action="store_true")
args = parser.parse_args()
OUT = (ROOT / args.output).resolve()
if not OUT.is_relative_to(ROOT / "docs"):
    parser.error("Результат можно записывать только в docs/")
FIXTURES = ROOT / "docs/fixtures"
IDS = args.employee_ids or ["E0028", "E0001", "E0050", "E0100", "E0150"]
TOKENS = {}


def config_quote(value):
    return (
        '"'
        + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
        + '"'
    )


def call(path, body=None, account=None, files=None, headers=None, expected=200):
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--max-time",
        "45",
        "--config",
        "-",
        "--write-out",
        "\n%{http_code} %{time_total}",
    ]
    config = []
    if account:
        config.append("header = " + config_quote("Authorization: Bearer " + TOKENS[account]))
    for key, value in (headers or {}).items():
        config.append("header = " + config_quote(f"{key}: {value}"))
    if files:
        for file in files:
            command += ["-F", f"files=@{file}"]
    elif body is not None:
        config.append('header = "content-type: application/json"')
        config.append("data-binary = " + config_quote(json.dumps(body, ensure_ascii=False)))
    command.append(BASE + path)
    proc = subprocess.run(
        command, input="\n".join(config) + "\n", text=True, capture_output=True, check=True
    )
    raw, timing = proc.stdout.rsplit("\n", 1)
    status, elapsed = timing.split()
    # Даже ошибочный ответ login не должен сохранить возвращённый token.
    response = json.loads(raw)
    result = {
        "path": path,
        "http_status": int(status),
        "http_ms": round(float(elapsed) * 1000, 3),
        "response": response,
    }
    if path == "/api/py/auth/login" and "token" in response:
        TOKENS[body["login"]] = response.pop("token")
        response["token_omitted"] = True
    if expected is not None and int(status) != expected:
        raise RuntimeError(f"{path}: HTTP {status}, ожидался {expected}")
    return result


def login(account, data, overlay=None):
    request = {"login": account, "password": "hr-demo" if account == "hr" else "demo"}
    if overlay:
        request["overlay"] = overlay
    result = call("/api/py/auth/login", request)
    data["logins"].append({"account": account, **result})


def save(data):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")


def main():
    data = {
        "started_utc": datetime.now(UTC).isoformat(),
        "base_url": BASE,
        "local_git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 docs/measure_production.py "
        + " ".join(sys.argv[1:]),
        "method": "Последовательные HTTP-запросы curl с проверкой TLS, locale=ru, пустой overlay, POST auth/login и Bearer. HTTP-время включает сеть; elapsed_ms возвращает сервер. cached=true не является новым вызовом LLM. Браузер и нагрузка не измеряются. Локальный HEAD не доказывает revision deployment.",
        "profiles": [],
        "ai": [],
        "logins": [],
    }
    data["health"] = call("/api/py/health")
    meta = call("/api/py/meta", {})
    m = meta.pop("response")
    meta["summary"] = {
        "employees": len(m["employees"]),
        "events": len(m["events"]),
        "skills": len(m["skills"]),
        "as_of": m["as_of"],
    }
    data["meta"] = meta
    save(data)
    for eid in IDS:
        login(eid, data)
        snap_req = call(f"/api/py/employees/{eid}", {}, eid)
        snap = snap_req["response"]
        record = {"employee_id": eid, "snapshot": snap_req}
        if snap["recommendations"]:
            step = snap["recommendations"][0]
            event = step["event_id"]
            record["simulate_main"] = call(
                f"/api/py/employees/{eid}/simulate", {"steps": [event]}, eid
            )
            plan_ids = [s["event_id"] for s in (snap["plan"]["best"] or {}).get("steps", [])]
            if plan_ids:
                record["simulate_route"] = call(
                    f"/api/py/employees/{eid}/simulate", {"steps": plan_ids}, eid
                )
            claim = {
                "employee_id": eid,
                "event_id": event,
                "session_date": step["session"],
                "gaming": False,
            }
            record["completion"] = call(
                f"/api/py/employees/{eid}", {"overlay": {"completions": [claim]}}, eid
            )
            record["duplicate_completion"] = call(
                f"/api/py/employees/{eid}", {"overlay": {"completions": [claim, claim]}}, eid
            )
            after = record["completion"]["response"]
            duplicate = record["duplicate_completion"]["response"]
            predicted = record["simulate_main"]["response"]["after"]
            skills = {s["skill_id"]: s["current"] for s in after["skills"]}
            record["checks"] = {
                "duplicate_skills_equal": duplicate["skills"] == after["skills"],
                "duplicate_readiness_equal": duplicate["readiness"] == after["readiness"],
                "what_if_visible_skills_equal": all(
                    predicted["skills"][sid] == level for sid, level in skills.items()
                ),
                "what_if_readiness_equal": predicted["readiness_pct"]
                == after["readiness"]["readiness_pct"],
                "grade_unchanged": snap["employee"]["grade"] == after["employee"]["grade"],
            }
        data["profiles"].append(record)
        ai = call(f"/api/py/employees/{eid}/ai", {"locale": "ru"}, eid)
        ai["employee_id"] = eid
        data["ai"].append(ai)
        save(data)
        print(
            json.dumps(
                {
                    "employee_id": eid,
                    "readiness": snap["readiness"]["readiness_pct"],
                    "baseline_main": (snap["recommendations"] or [{}])[0].get("event_id"),
                    "model": ai["response"].get("model"),
                    "ai_status": ai["response"].get("ai_status"),
                    "cached": ai["response"].get("cached", False),
                    "http_ms": ai["http_ms"],
                    "checks": record.get("checks"),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    login("hr", data)
    data["hr"] = call("/api/py/hr/dashboard", {}, "hr")
    actor = IDS[0]
    other = next(eid for eid in m["employees"] if eid["employee_id"] != actor)["employee_id"]
    data["wrong_actor"] = call(f"/api/py/employees/{other}", {}, actor, expected=403)
    data["employee_hr_access"] = call("/api/py/hr/dashboard", {}, actor, expected=403)
    data["no_headers_profile"] = call(f"/api/py/employees/{actor}", {}, expected=401)
    data["forged_hr_header"] = call(
        "/api/py/hr/dashboard", {}, headers={"x-role": "hr"}, expected=401
    )
    data["forged_employee_headers"] = call(
        f"/api/py/employees/{actor}",
        {},
        headers={"x-role": "employee", "x-actor": actor},
        expected=401,
    )
    data["employee_forged_hr"] = call(
        "/api/py/hr/dashboard", {}, actor, headers={"x-role": "hr"}, expected=403
    )
    data["wrong_password"] = call(
        "/api/py/auth/login", {"login": "hr", "password": "invalid-demo-password"}, expected=401
    )
    data["repeat_ai"] = call(f"/api/py/employees/{actor}/ai", {"locale": "ru"}, actor)
    if not args.skip_import:
        ds = load_base_dataset()
        selected = IDS[:3]
        FIXTURES.mkdir(parents=True, exist_ok=True)
        employees_path = FIXTURES / "employees.json"
        history_path = FIXTURES / "activity_history.csv"
        employees_path.write_text(
            json.dumps(
                {
                    "meta": {"as_of_date": ds.as_of.isoformat()},
                    "employees": [ds.employees[x] for x in selected],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            "utf-8",
        )
        with (ROOT / "data/dataset/activity_history.csv").open(newline="") as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames
            rows = [row for row in reader if row["employee_id"] in selected]
        with history_path.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        imp = call("/api/py/hr/import/validate", account="hr", files=[employees_path, history_path])
        data["import"] = imp
        scenario = imp["response"].get("scenario")
        if scenario:
            data["scenario_hr"] = call(
                "/api/py/hr/dashboard", {"overlay": {"scenario": scenario}}, "hr"
            )
            data["scenario_snapshots"] = [
                call(f"/api/py/employees/{eid}", {"overlay": {"scenario": scenario}}, "hr")
                for eid in selected
            ]
        data["duplicate_import"] = call(
            "/api/py/hr/import/validate",
            account="hr",
            files=[employees_path, employees_path, history_path],
        )
        data["jury_import"] = call(
            "/api/py/hr/import/validate",
            account="hr",
            files=[
                ROOT / "samples/jury/employees.json",
                ROOT / "samples/jury/activity_history.csv",
            ],
        )
        jury = data["jury_import"]["response"].get("scenario")
        if jury:
            jury_id = jury["employees"][0]["employee_id"]
            login(jury_id, data, {"scenario": jury})
            data["jury_snapshot"] = call(
                f"/api/py/employees/{jury_id}", {"overlay": {"scenario": jury}}, jury_id
            )
    data["finished_utc"] = datetime.now(UTC).isoformat()
    save(data)
    print(
        json.dumps(
            {"output": str(OUT.relative_to(ROOT)), "hr": data["hr"]["response"]["cards"]},
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
