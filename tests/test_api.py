import json

import pytest
from fastapi.testclient import TestClient

import api.index as api
from career_quest.ai import DEFAULT_MODEL, active_model


def _token(client, login, password):
    response = client.post("/api/py/auth/login", json={"login": login, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def client():
    api._ai_cache.clear()
    with TestClient(api.app, raise_server_exceptions=False) as test_client:
        yield test_client
    api._ai_cache.clear()


def test_employee_cannot_read_another_profile(client):
    response = client.post(
        "/api/py/employees/E0028", headers=_token(client, "E0001", "demo"), json={}
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


def test_forged_role_headers_are_ignored(client):
    response = client.post(
        "/api/py/employees/E0028", headers={"x-role": "hr", "x-actor": "E0028"}, json={}
    )

    assert response.status_code == 401


def test_hr_dashboard_requires_hr_role(client):
    assert client.post("/api/py/hr/dashboard", json={}).status_code == 401
    response = client.post("/api/py/hr/dashboard", headers=_token(client, "E0028", "demo"), json={})
    assert response.status_code == 403


def test_import_validation_requires_hr_role(client):
    files = {"files": ("employees.json", '{"employees": []}', "application/json")}
    assert client.post("/api/py/hr/import/validate", files=files).status_code == 401
    response = client.post(
        "/api/py/hr/import/validate", headers=_token(client, "E0028", "demo"), files=files
    )
    assert response.status_code == 403


def test_import_rejects_null_review_date_with_validation_report(client):
    employee = {**api.load_base_dataset().employees["E0028"], "last_review_date": None}
    response = client.post(
        "/api/py/hr/import/validate",
        headers=_token(client, "hr", "hr-demo"),
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
        model = active_model()
        calls.append(model)
        return {"ai_status": "live_validated", "model": model, "choices": [], "elapsed_ms": 0}

    return select_actions


def test_ai_cache_is_invalidated_when_model_changes(client, monkeypatch):
    calls = []
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(api, "select_actions", _fake_selection(calls))
    request = {"headers": _token(client, "E0028", "demo"), "json": {}}

    first = client.post("/api/py/employees/E0028/ai", **request)
    monkeypatch.setenv("OPENAI_MODEL", "test-selected-model")
    second = client.post("/api/py/employees/E0028/ai", **request)

    assert first.status_code == second.status_code == 200
    assert first.json()["model"] == DEFAULT_MODEL
    assert second.json()["model"] == "test-selected-model"
    assert calls == [DEFAULT_MODEL, "test-selected-model"]
    assert not second.json().get("cached", False)


@pytest.mark.parametrize("configured_model", [None, "test-selected-model"])
def test_ai_cache_reuses_result_for_same_model(client, monkeypatch, configured_model):
    calls = []
    if configured_model is None:
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
    else:
        monkeypatch.setenv("OPENAI_MODEL", configured_model)
    monkeypatch.setattr(api, "select_actions", _fake_selection(calls))
    request = {"headers": _token(client, "E0028", "demo"), "json": {}}

    first = client.post("/api/py/employees/E0028/ai", **request)
    second = client.post("/api/py/employees/E0028/ai", **request)

    assert first.status_code == second.status_code == 200
    assert calls == [configured_model or DEFAULT_MODEL]
    assert second.json() == {**first.json(), "cached": True}


@pytest.mark.parametrize(
    "payload", ['{"employees": null}', '{"employees": [null]}', '{"employees": "bad"}', "[1, 2]"]
)
def test_malformed_employees_json_returns_report_not_500(client, payload):
    response = client.post(
        "/api/py/hr/import/validate",
        headers=_token(client, "hr", "hr-demo"),
        files={"files": ("employees.json", payload, "application/json")},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
