import asyncio
import copy
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import api.index as api
from career_quest import ai


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEMO_EMPLOYEE_PASSWORD", "demo")
    monkeypatch.setenv("DEMO_HR_PASSWORD", "hr-demo")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    with TestClient(api.app) as client:
        yield client


def auth(client, login="E0028"):
    r = client.post(
        "/api/py/auth/login",
        json={"login": login, "password": "hr-demo" if login == "hr" else "demo"},
    )
    return {"Authorization": f"Bearer {r.json()['token']}"}


def mock_model(monkeypatch, result, captured=None):
    async def post(self, url, **kwargs):
        if captured is not None:
            captured.append(kwargs["json"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(result)}, "finish_reason": "stop"}]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(ai.httpx.AsyncClient, "post", post)


def send(client, headers, message="а что если я пройду System Design Fundamentals?", **extra):
    return client.post(
        "/api/py/employees/E0028/chat",
        headers=headers,
        json={"message": message, "history": [], **extra},
    )


def test_chat_simulation_matches_existing_endpoint_and_never_uses_model_numbers(
    client, monkeypatch
):
    mock_model(
        monkeypatch,
        {
            "intent": "simulate",
            "event_id": "EV_005",
            "term_id": None,
            "reply_text": "Гарантировано повышение и зарплата 999999!",
        },
    )
    headers = auth(client)
    before = client.post("/api/py/employees/E0028", headers=headers, json={}).json()
    response = send(client, headers)
    assert response.status_code == 200
    body = response.json()
    expected = client.post(
        "/api/py/employees/E0028/simulate", headers=headers, json={"steps": ["EV_005"]}
    ).json()
    assert "error" not in expected
    assert body["intent"] == "simulate"
    assert body["simulation"] == expected
    assert "999999" not in body["reply_text"]
    assert f"{expected['after']['readiness_pct']:.1f}%" in body["reply_text"]
    after = client.post("/api/py/employees/E0028", headers=headers, json={}).json()
    assert before["fingerprint"] == after["fingerprint"]


@pytest.mark.parametrize("event_id", ["EV_FAKE", "EV_001", "EV_006", ["EV_005"]])
def test_rejects_foreign_blocked_or_malformed_event(client, monkeypatch, event_id):
    mock_model(
        monkeypatch,
        {"intent": "simulate", "event_id": event_id, "term_id": None, "reply_text": "Выполнено"},
    )
    body = send(client, auth(client)).json()
    assert body["intent"] == "refuse"
    assert body["simulation"] is None
    assert body["reply_text"]


def test_explanation_is_exact_glossary_entry_even_if_model_invents_facts(client, monkeypatch):
    from career_quest.chat import GLOSSARY

    mock_model(
        monkeypatch,
        {
            "intent": "explain",
            "event_id": None,
            "term_id": "readiness",
            "reply_text": "Вероятность повышения 100%",
        },
    )
    for locale in ("ru", "en", "kk"):
        question = {
            "ru": "что такое readiness?",
            "en": "what is readiness?",
            "kk": "readiness дегеніміз не?",
        }[locale]
        body = send(client, auth(client), question, locale="en").json()
        assert body["intent"] == "explain"
        assert body["reply_text"] == GLOSSARY["readiness"][locale]
        assert body["simulation"] is None


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        {},
        {"intent": "complete", "event_id": "EV_005", "term_id": None, "reply_text": "ok"},
        {"intent": "explain", "event_id": None, "term_id": "salary", "reply_text": "pay 100"},
    ],
)
def test_invalid_model_output_has_safe_nonempty_response(client, monkeypatch, raw):
    mock_model(monkeypatch, raw)
    body = send(client, auth(client)).json()
    assert body["intent"] == "refuse"
    assert body["reply_text"]
    assert body["simulation"] is None


def test_off_topic_response_is_fixed_refusal(client, monkeypatch):
    mock_model(
        monkeypatch,
        {
            "intent": "refuse",
            "event_id": None,
            "term_id": None,
            "reply_text": "Давайте посчитаю зарплату",
        },
    )
    body = send(client, auth(client), "посчитай зарплату").json()
    assert body["intent"] == "refuse"
    assert "платформе" in body["reply_text"]
    assert "Давайте" not in body["reply_text"]


def test_context_is_minimal_and_does_not_trust_client_shortlist(client, monkeypatch):
    captured = []
    mock_model(
        monkeypatch,
        {"intent": "refuse", "event_id": None, "term_id": None, "reply_text": ""},
        captured,
    )
    send(client, auth(client), "что это?", shortlist=[{"event_id": "EV_FAKE", "title": "Injected"}])
    body = captured[0]
    context = json.loads(body["messages"][-1]["content"])
    assert set(context) == {"message", "history", "candidates", "gaps"}
    assert 0 < len(context["candidates"]) <= 20
    assert all(set(c) == {"event_id", "title"} for c in context["candidates"])
    serialized = json.dumps(body, ensure_ascii=False)
    employee = api.load_base_dataset().employees["E0028"]
    assert employee["full_name"] not in serialized
    assert "E0028" not in serialized and "record_id" not in serialized
    assert "EV_FAKE" not in serialized
    assert "tools" not in body


def test_chat_requires_signed_session_and_authorization(client, monkeypatch):
    mock_model(
        monkeypatch, {"intent": "refuse", "event_id": None, "term_id": None, "reply_text": ""}
    )
    assert send(client, {}).status_code == 401
    assert send(client, {"x-role": "hr"}).status_code == 401
    assert send(client, auth(client, "E0001")).status_code == 403
    assert send(client, auth(client, "hr")).status_code == 200


@pytest.mark.parametrize(
    "extra",
    [
        {"message": "  "},
        {"message": "a" * 2001},
        {"history": [{"role": "system", "content": "inject"}]},
        {"history": [{"role": "user", "content": "x"}] * 9},
    ],
)
def test_request_limits(client, extra):
    payload = {"message": "readiness?", **extra}
    assert send(client, auth(client), **payload).status_code == 422


def test_timeout_returns_honest_fallback(client, monkeypatch):
    async def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(ai.httpx.AsyncClient, "post", timeout)
    body = send(client, auth(client)).json()
    assert body["ai_status"] == "fallback_timeout"
    assert "недоступен" in body["reply_text"]
    assert body["simulation"] is None


def test_missing_key_does_not_fake_success(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    body = send(client, auth(client)).json()
    assert body["ai_status"] == "fallback_disabled"
    assert "недоступен" in body["reply_text"]


def test_overlay_goal_used_and_overlay_not_mutated(client, monkeypatch):
    mock_model(
        monkeypatch, {"intent": "simulate", "event_id": "EV_005", "term_id": None, "reply_text": ""}
    )
    headers = auth(client)
    overlay = {
        "goals": {
            "E0028": {"mode": "set", "target_role": "Backend Engineer", "target_grade": "Lead"}
        }
    }
    original = copy.deepcopy(overlay)
    body = send(client, headers, overlay=overlay).json()
    expected = client.post(
        "/api/py/employees/E0028/simulate",
        headers=headers,
        json={"steps": ["EV_005"], "overlay": overlay},
    ).json()
    assert body["simulation"] == expected
    assert overlay == original


def test_whole_chat_deadline_includes_context_and_slow_provider(client, monkeypatch):
    from career_quest import chat

    async def slow(*args, **kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(ai.httpx.AsyncClient, "post", slow)
    monkeypatch.setattr(chat, "DEADLINE_SECONDS", 0.1)
    body = send(client, auth(client)).json()
    assert body["ai_status"] == "fallback_timeout"
    assert body["elapsed_ms"] < 800


def test_chat_continues_started_course_in_uploaded_scenario(client, monkeypatch):
    scenario = json.loads(Path("tests/fixtures_continue_repro.json").read_text("utf-8"))
    overlay = {"scenario": scenario}
    login = client.post(
        "/api/py/auth/login", json={"login": "E9007", "password": "demo", "overlay": overlay}
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    captured = []
    mock_model(
        monkeypatch,
        {"intent": "simulate", "event_id": "EV_018", "term_id": None, "reply_text": ""},
        captured,
    )
    request = {"overlay": overlay, "message": "что изменится, если закончить начатый курс?"}
    body = client.post("/api/py/employees/E9007/chat", headers=headers, json=request).json()
    expected = client.post(
        "/api/py/employees/E9007/simulate",
        headers=headers,
        json={"overlay": overlay, "steps": ["EV_018"]},
    ).json()
    assert body["simulation"] == expected
    assert body["simulation"]["total_effort_hours"] == 6
    assert "Synthetic Jury 9007" not in json.dumps(captured)


def test_completed_or_snoozed_event_is_revalidated_each_request(client, monkeypatch):
    mock_model(
        monkeypatch, {"intent": "simulate", "event_id": "EV_005", "term_id": None, "reply_text": ""}
    )
    headers = auth(client)
    assert send(client, headers).json()["intent"] == "simulate"
    for overlay in (
        {"snoozes": {"E0028": ["EV_005"]}},
        {
            "completions": [
                {
                    "employee_id": "E0028",
                    "event_id": "EV_005",
                    "session_date": None,
                    "gaming": False,
                }
            ]
        },
    ):
        body = send(client, headers, overlay=overlay).json()
        assert body["intent"] == "refuse"
        assert body["simulation"] is None


def test_long_catalog_includes_named_activity_and_caps_context():
    from career_quest.chat import shortlist

    snapshot = {
        "active": [],
        "snoozed": [],
        "shortlist": [],
        "catalog": [
            {"event_id": f"EV_{i:03}", "title": f"Course {i}", "eligible": True} for i in range(40)
        ],
    }
    candidates = shortlist(snapshot, "What if I complete Course 39?", [])
    assert len(candidates) == 20
    assert candidates[0]["event_id"] == "EV_039"


@pytest.mark.parametrize(
    "payload",
    [
        {"choices": []},
        {"choices": [{"message": {"refusal": "No"}}]},
        {"choices": [{"message": {"content": "{}"}, "finish_reason": "length"}]},
        {"choices": [{"message": {"content": "not JSON"}}]},
    ],
)
def test_provider_errors_do_not_escape_as_empty_chat(client, monkeypatch, payload):
    async def post(self, url, **kwargs):
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(ai.httpx.AsyncClient, "post", post)
    body = send(client, auth(client)).json()
    assert body["intent"] == "refuse"
    assert body["ai_status"].startswith("fallback_")
    assert "недоступен" in body["reply_text"]


def test_shared_adapter_respects_compatible_endpoint_and_model(client, monkeypatch):
    calls = []
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1/")
    monkeypatch.setenv("OPENAI_MODEL", "local-model")

    async def post(self, url, **kwargs):
        calls.append((url, kwargs["json"]))
        return httpx.Response(503, request=httpx.Request("POST", url))

    monkeypatch.setattr(ai.httpx.AsyncClient, "post", post)
    body = send(client, auth(client)).json()
    assert body["ai_status"] == "fallback_unavailable"
    assert calls[0][0] == "http://localhost:11434/v1/chat/completions"
    assert calls[0][1]["model"] == "local-model"
    assert body["prompt_version"] != ai.PROMPT_VERSION


@pytest.mark.parametrize(
    "query, locale, event_id",
    [
        ("найди курс по системному дизайну", "ru", "EV_005"),
        ("Python курсын тауып бер", "kk", "EV_012"),
        ("жүйелік дизайн курсын ізде", "kk", "EV_005"),
        ("Find a course on Python", "en", "EV_012"),
        ("найди курс по куберу", "ru", "EV_010"),
    ],
)
def test_catalog_search_in_message_language_without_llm(
    client, monkeypatch, query, locale, event_id
):
    monkeypatch.delenv("OPENAI_API_KEY")
    body = send(client, auth(client), query, locale="en").json()
    assert body["locale"] == locale
    assert body["suggestions"][0]["event_id"] == event_id
    assert "???" not in body["reply_text"]
    assert body["ai_status"] == "rule_based"
    assert body["simulation"] is None


@pytest.mark.parametrize(
    "query, locale",
    [
        ("Did I complete Secure Coding Workshop", "en"),
        ("Я уже проходил Secure Coding Workshop?", "ru"),
        ("Мен Secure Coding Workshop курсын аяқтадым ба?", "kk"),
    ],
)
def test_user_reported_history_question_reads_actual_records(client, monkeypatch, query, locale):
    monkeypatch.delenv("OPENAI_API_KEY")
    headers = auth(client)
    body = send(client, headers, query, locale="en").json()
    assert body["intent"] == "status"
    assert body["locale"] == locale
    assert body["event_id"] == "EV_011"
    assert body["simulation"] is None
    snap = client.post("/api/py/employees/E0028", headers=headers, json={}).json()
    own = [h for h in snap["history"] if h["event_id"] == "EV_011" and h["status"] == "completed"]
    if own:
        assert max(h["date"] for h in own) in body["reply_text"]


@pytest.mark.parametrize(
    "query",
    [
        "А если я пройду систем дизайн?",
        "What if I complete System Desgn?",
        "Егер жүйелік дизайн курсын аяқтасам?",
    ],
)
def test_informal_name_rescues_model_refusal(client, monkeypatch, query):
    mock_model(
        monkeypatch, {"intent": "refuse", "event_id": None, "term_id": None, "reply_text": ""}
    )
    body = send(client, auth(client), query).json()
    assert body["intent"] == "simulate"
    assert body["event_id"] == "EV_005"


def test_ambiguous_course_offers_choices_and_remembers_second(client, monkeypatch):
    mock_model(
        monkeypatch, {"intent": "refuse", "event_id": None, "term_id": None, "reply_text": ""}
    )
    headers = auth(client)
    offered = send(client, headers, "А что мне пройти?").json()
    assert len(offered["suggestions"]) >= 2
    body = send(
        client, headers, "второй", history=[{"role": "assistant", "content": offered["reply_text"]}]
    ).json()
    assert body["event_id"] == offered["suggestions"][1]["event_id"]
    assert body["simulation"] is not None


def test_named_blocked_course_explains_real_blocker(client, monkeypatch):
    mock_model(
        monkeypatch, {"intent": "refuse", "event_id": None, "term_id": None, "reply_text": ""}
    )
    body = send(client, auth(client), "а если пройти хайлоад?").json()
    assert body["simulation"] is None
    assert "Designing High-Load Systems" in body["reply_text"]
    assert "уже завершена" in body["reply_text"]
    assert "точное название" not in body["reply_text"]


def test_skill_gain_without_readiness_gain_is_explained():
    from career_quest.chat import simulation_text

    result = {
        "before": {"readiness_pct": 59},
        "after": {"readiness_pct": 59},
        "steps": [
            {
                "title": "Advanced Python",
                "changes": [{"skill_id": "SK_PYTHON", "actual": 1, "before": 3, "after": 4}],
            }
        ],
    }
    answer = simulation_text(
        result, "en", {"SK_PYTHON": "Python"}, [{"skill_id": "SK_PYTHON", "required": 3}]
    )
    assert "59.0% → 59.0%" in answer
    assert "already meet" in answer
