import base64
import json
import time
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from api import index as api
from career_quest.auth import SignedTokenStore
from career_quest.dataset import load_base_dataset

SECRET = "test-only-session-signing-secret"
EMPLOYEE = "E0028"
OTHER_EMPLOYEE = "E0001"
EMPLOYEE_ROUTES = [
    f"/api/py/employees/{EMPLOYEE}",
    f"/api/py/employees/{EMPLOYEE}/ai",
    f"/api/py/employees/{EMPLOYEE}/simulate",
]
HR_ROUTES = ["/api/py/hr/dashboard", "/api/py/hr/import/validate"]
PROTECTED_ROUTES = EMPLOYEE_ROUTES + HR_ROUTES + ["/api/py/auth/logout"]


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("DEMO_EMPLOYEE_PASSWORD", "demo")
    monkeypatch.setenv("DEMO_HR_PASSWORD", "hr-demo")
    store = SignedTokenStore(secret=SECRET)
    monkeypatch.setattr(api, "session_store", store)
    return store


@pytest.fixture
def client(store, monkeypatch):
    async def fake_select_actions(*args, **kwargs):
        return {"ai_status": "unavailable", "choices": []}

    # Successful AI authorization must never issue an external model request.
    monkeypatch.setattr(api, "select_actions", fake_select_actions)
    monkeypatch.setattr(api, "_ai_cache", {})
    with TestClient(api.app) as client:
        yield client


def login(client, login=EMPLOYEE, password="demo", overlay=None):
    body = {"login": login, "password": password}
    if overlay is not None:
        body["overlay"] = overlay
    response = client.post("/api/py/auth/login", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def post_protected(client, path, headers=None):
    if path.endswith("/import/validate"):
        employee = deepcopy(load_base_dataset().employees[EMPLOYEE])
        contents = json.dumps({"employees": [employee]}).encode()
        return client.post(
            path,
            headers=headers,
            files=[("files", ("employees.json", contents, "application/json"))],
        )
    body = {"steps": []} if path.endswith("/simulate") else {}
    return client.post(path, json=body, headers=headers)


def test_meta_and_health_remain_public(client):
    assert client.get("/api/py/health").status_code == 200
    response = client.post("/api/py/meta", json={})
    assert response.status_code == 200
    assert EMPLOYEE in {employee["employee_id"] for employee in response.json()["employees"]}


@pytest.mark.parametrize("path", PROTECTED_ROUTES)
def test_missing_session_is_unauthorized(client, path):
    assert post_protected(client, path).status_code == 401


@pytest.mark.parametrize("path", PROTECTED_ROUTES)
def test_forged_role_and_actor_headers_are_unauthorized(client, path):
    response = post_protected(client, path, {"x-role": "hr", "x-actor": EMPLOYEE})
    assert response.status_code == 401


@pytest.mark.parametrize("authorization", ["Bearer", "Bearer invalid", "Basic fake", ""])
def test_invalid_authorization_is_unauthorized(client, authorization):
    response = client.post(EMPLOYEE_ROUTES[0], json={}, headers={"Authorization": authorization})
    assert response.status_code == 401


def test_login_returns_verified_identity_and_expiry(client, store):
    session = login(client)
    assert session["role"] == "employee"
    assert session["employee_id"] == EMPLOYEE
    assert time.time() < session["expires_at"] <= time.time() + 8 * 60 * 60
    principal = store.resolve(session["token"])
    assert principal is not None
    assert principal.role == session["role"]
    assert principal.employee_id == session["employee_id"]
    assert principal.expires_at == session["expires_at"]
    assert principal.jti


@pytest.mark.parametrize("path", EMPLOYEE_ROUTES)
def test_employee_can_access_own_routes(client, path):
    session = login(client)
    response = post_protected(client, path, bearer(session["token"]))
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("path", EMPLOYEE_ROUTES)
def test_employee_cannot_read_other_employee_even_with_forged_headers(client, path):
    session = login(client)
    headers = bearer(session["token"]) | {"x-role": "hr", "x-actor": OTHER_EMPLOYEE}
    response = post_protected(client, path.replace(EMPLOYEE, OTHER_EMPLOYEE), headers)
    assert response.status_code == 403


@pytest.mark.parametrize("path", HR_ROUTES)
def test_employee_cannot_access_hr_even_with_forged_role(client, path):
    session = login(client)
    headers = bearer(session["token"]) | {"x-role": "hr"}
    response = post_protected(client, path, headers)
    assert response.status_code == 403


@pytest.mark.parametrize("path", HR_ROUTES + EMPLOYEE_ROUTES)
def test_hr_can_access_hr_and_employee_routes(client, path):
    session = login(client, "hr", "hr-demo")
    assert session["role"] == "hr"
    assert session["employee_id"] is None
    response = post_protected(client, path, bearer(session["token"]))
    assert response.status_code == 200, response.text
    if path.endswith("/import/validate"):
        assert response.json()["ok"] is True


@pytest.mark.parametrize(
    ("username", "password"),
    [
        (EMPLOYEE, "wrong"),
        (EMPLOYEE, "демо"),
        (EMPLOYEE, "\ud800"),
        (EMPLOYEE, " demo "),
        (EMPLOYEE, ""),
        ("hr", "demo"),
        ("UNKNOWN_EMPLOYEE", "demo"),
    ],
)
def test_wrong_credentials_return_401(client, username, password):
    response = client.post(
        "/api/py/auth/login",
        content=json.dumps({"login": username, "password": password}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.parametrize(
    ("field", "value"), [("role", "hr"), ("employee_id", OTHER_EMPLOYEE), ("exp", 9999999999)]
)
def test_tampered_payload_is_unauthorized(client, field, value):
    token = login(client)["token"]
    encoded, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    payload[field] = value
    forged_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    response = client.post(
        EMPLOYEE_ROUTES[0], json={}, headers=bearer(f"{forged_payload}.{signature}")
    )
    assert response.status_code == 401


def test_tampered_signature_is_unauthorized(client):
    encoded, signature = login(client)["token"].split(".")
    replacement = "A" if signature[0] != "A" else "B"
    forged = f"{encoded}.{replacement}{signature[1:]}"
    response = client.post(EMPLOYEE_ROUTES[0], json={}, headers=bearer(forged))
    assert response.status_code == 401


def test_expired_token_is_unauthorized(client, monkeypatch):
    expired_store = SignedTokenStore(secret=SECRET, ttl_seconds=-1)
    token = expired_store.create(EMPLOYEE, "demo", load_base_dataset())
    assert token is not None
    monkeypatch.setattr(api, "session_store", expired_store)
    response = client.post(EMPLOYEE_ROUTES[0], json={}, headers=bearer(token))
    assert response.status_code == 401


def test_token_works_on_another_stateless_instance(client, monkeypatch):
    session = login(client)
    other_instance = SignedTokenStore(secret=SECRET)
    principal = other_instance.resolve(session["token"])
    assert principal is not None
    assert principal.employee_id == EMPLOYEE
    monkeypatch.setattr(api, "session_store", other_instance)
    response = client.post(EMPLOYEE_ROUTES[0], json={}, headers=bearer(session["token"]))
    assert response.status_code == 200


def test_token_signed_with_another_secret_is_unauthorized(client, monkeypatch):
    session = login(client)
    monkeypatch.setattr(api, "session_store", SignedTokenStore(secret="different-test-secret"))
    response = client.post(EMPLOYEE_ROUTES[0], json={}, headers=bearer(session["token"]))
    assert response.status_code == 401


def test_uploaded_scenario_employee_can_log_in_and_read_own_profile(client):
    employee = deepcopy(load_base_dataset().employees[EMPLOYEE])
    employee["employee_id"] = "JURY_AUTH_001"
    employee["manager_id"] = None
    overlay = {"scenario": {"employees": [employee], "history": []}}
    without_overlay = client.post(
        "/api/py/auth/login", json={"login": employee["employee_id"], "password": "demo"}
    )
    assert without_overlay.status_code == 401
    session = login(client, employee["employee_id"], overlay=overlay)
    assert session["employee_id"] == employee["employee_id"]
    response = client.post(
        f"/api/py/employees/{employee['employee_id']}",
        json={"overlay": overlay},
        headers=bearer(session["token"]),
    )
    assert response.status_code == 200, response.text
    # Uploaded scenarios replace the employee list; a base-only account cannot log in there.
    base_employee = client.post(
        "/api/py/auth/login", json={"login": EMPLOYEE, "password": "demo", "overlay": overlay}
    )
    assert base_employee.status_code == 401


def test_logout_revokes_only_the_selected_session(client, store):
    session = login(client)
    other_session = login(client)
    assert session["token"] != other_session["token"]
    headers = bearer(session["token"])
    response = client.post("/api/py/auth/logout", headers=headers)
    assert response.status_code in (200, 204)
    assert store.resolve(session["token"]) is None
    assert client.post(EMPLOYEE_ROUTES[0], json={}, headers=headers).status_code == 401
    assert store.resolve(other_session["token"]) is not None
    assert (
        client.post(EMPLOYEE_ROUTES[0], json={}, headers=bearer(other_session["token"])).status_code
        == 200
    )


def test_password_environment_overrides_defaults(client, monkeypatch):
    monkeypatch.setenv("DEMO_EMPLOYEE_PASSWORD", "employee-test-password")
    monkeypatch.setenv("DEMO_HR_PASSWORD", "hr-test-password")
    monkeypatch.setattr(api, "session_store", SignedTokenStore(secret=SECRET))
    for username, default_password, configured_password in [
        (EMPLOYEE, "demo", "employee-test-password"),
        ("hr", "hr-demo", "hr-test-password"),
    ]:
        response = client.post(
            "/api/py/auth/login", json={"login": username, "password": default_password}
        )
        assert response.status_code == 401
        assert login(client, username, configured_password)["token"]
