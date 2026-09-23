import json
import os

import pytest
from fastapi.testclient import TestClient

import api.index as api


@pytest.fixture
def client():
    api._ai_cache.clear()
    with TestClient(api.app, raise_server_exceptions=False) as test_client:
        yield test_client
    api._ai_cache.clear()


@pytest.mark.parametrize(
    "headers",
    [
        {"x-role": "employee", "x-actor": "E0001"},
        {"x-role": "employee"},
    ],
)
def test_employee_cannot_read_profile_without_matching_actor(client, headers):
    response = client.post("/api/py/employees/E0028", headers=headers, json={})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize("headers", [{}, {"x-role": "employee", "x-actor": "E0028"}])
def test_hr_dashboard_requires_hr_role(client, headers):
    response = client.post("/api/py/hr/dashboard", headers=headers, json={})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "HR_ONLY"


@pytest.mark.parametrize("headers", [{}, {"x-role": "employee", "x-actor": "E0028"}])
def test_import_validation_requires_hr_role(client, headers):
    response = client.post(
        "/api/py/hr/import/validate",
        headers=headers,
        files={"files": ("employees.json", '{"employees": []}', "application/json")},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "HR_ONLY"


def test_import_rejects_null_review_date_with_validation_report(client):
    employee = {**api.load_base_dataset().employees["E0028"], "last_review_date": None}
    response = client.post(
        "/api/py/hr/import/validate",
        headers={"x-role": "hr"},
        files={
            "files": (
                "employees.json",
                json.dumps({"employees": [employee]}),
                "application/json",
            )
        },
    )

    assert response.status_code == 200
    report = response.json()
    assert report["ok"] is False
    assert any(error["code"] == "BAD_DATE" for error in report["errors"])
    assert report["scenario"] is None


def _fake_selection(calls):
    async def select_actions(snapshot, skill_names, locale):
        model = os.getenv("OPENAI_MODEL", "gpt-4.1")
        calls.append(model)
        return {"ai_status": "live_validated", "model": model, "choices": [], "elapsed_ms": 0}

    return select_actions


def test_ai_cache_is_invalidated_when_model_changes(client, monkeypatch):
    calls = []
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(api, "select_actions", _fake_selection(calls))
    request = {"headers": {"x-role": "employee", "x-actor": "E0028"}, "json": {}}

    first = client.post("/api/py/employees/E0028/ai", **request)
    monkeypatch.setenv("OPENAI_MODEL", "test-selected-model")
    second = client.post("/api/py/employees/E0028/ai", **request)

    assert first.status_code == second.status_code == 200
    assert first.json()["model"] == "gpt-4.1"
    assert second.json()["model"] == "test-selected-model"
    assert calls == ["gpt-4.1", "test-selected-model"]
    assert not second.json().get("cached", False)


@pytest.mark.parametrize("configured_model", [None, "test-selected-model"])
def test_ai_cache_reuses_result_for_same_model(client, monkeypatch, configured_model):
    calls = []
    if configured_model is None:
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
    else:
        monkeypatch.setenv("OPENAI_MODEL", configured_model)
    monkeypatch.setattr(api, "select_actions", _fake_selection(calls))
    request = {"headers": {"x-role": "employee", "x-actor": "E0028"}, "json": {}}

    first = client.post("/api/py/employees/E0028/ai", **request)
    second = client.post("/api/py/employees/E0028/ai", **request)

    assert first.status_code == second.status_code == 200
    assert calls == [configured_model or "gpt-4.1"]
    assert second.json() == {**first.json(), "cached": True}
