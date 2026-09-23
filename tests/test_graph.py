from dataclasses import replace

from test_core import _mini_dataset

from career_quest.dataset import load_base_dataset
from career_quest.engine import build_snapshot


def chain_dataset():
    ds = _mini_dataset([])
    ds.employees["T001"]["skills"]["SK_SD"] = 1
    ds.events["EV_SD"] = replace(ds.events["EV_SD"], format="self_paced", upcoming_sessions=[])
    ds.events["EV_ADV"] = replace(
        ds.events["EV_SD"],
        event_id="EV_ADV",
        title="Advanced design",
        prerequisites={"SK_SD": 2, "SK_PY": 4},
        develops_skills=[{"skill_id": "SK_SD", "gain": 2, "max_level": 4}],
    )
    return ds


def test_graph_has_real_typed_dependencies_and_current_blockers():
    snap = build_snapshot(chain_dataset(), "T001", {})
    graph = snap["career_graph"]
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = graph["edges"]
    assert {e["kind"] for e in edges} == {"requires", "develops", "prerequisite"}
    assert all(e["source"] in nodes and e["target"] in nodes for e in edges)
    advanced = nodes["activity:EV_ADV"]
    assert advanced["status"] == "after_previous"
    assert advanced["reasons"][0]["code"] == "PREREQUISITES_UNMET"
    assert advanced["prerequisites"] == [
        {"skill_id": "SK_PY", "current": 4, "required": 4, "met": True},
        {"skill_id": "SK_SD", "current": 1, "required": 2, "met": False},
    ]
    # A planned gain must not replace the current skill level or imply completion.
    assert nodes["skill:SK_SD"]["current"] == 1
    assert nodes["skill:SK_SD"]["planned"] == 4
    assert nodes["goal"]["status"] == "gap"
    assert nodes["activity:EV_SD"]["status"] == "available"


def test_graph_recomputes_after_completion_without_keeping_old_lock():
    ds = chain_dataset()
    snap = build_snapshot(
        ds, "T001", {"completions": [{"employee_id": "T001", "event_id": "EV_SD"}]}
    )
    nodes = {n["id"]: n for n in snap["career_graph"]["nodes"]}
    assert nodes["activity:EV_SD"]["status"] == "completed"
    assert nodes["activity:EV_ADV"]["status"] == "available"
    assert nodes["skill:SK_SD"]["current"] == 2


def test_graph_shows_requirements_when_no_catalog_route_exists():
    ds = chain_dataset()
    ds.events = {}
    snap = build_snapshot(ds, "T001", {})
    graph = snap["career_graph"]
    assert not any(n["kind"] == "activity" for n in graph["nodes"])
    assert len([e for e in graph["edges"] if e["kind"] == "requires"]) == 3
    assert any(n["kind"] == "skill" and n["status"] == "gap" for n in graph["nodes"])


def test_graph_includes_unassessed_prerequisite_and_zero_gain_cap():
    ds = chain_dataset()
    ds.skills["SK_BRIDGE"] = {"skill_id": "SK_BRIDGE", "name": "Bridge"}
    ds.events["EV_ADV"] = replace(ds.events["EV_ADV"], prerequisites={"SK_BRIDGE": 2})
    snap = build_snapshot(ds, "T001", {})
    nodes = {n["id"]: n for n in snap["career_graph"]["nodes"]}
    assert nodes["skill:SK_BRIDGE"]["current"] == 0
    assert nodes["skill:SK_BRIDGE"]["required"] is None
    assert nodes["activity:EV_ADV"]["status"] == "blocked"
    assert nodes["activity:EV_PY"]["effects"][0]["actual"] == 0


def test_graph_excludes_mandatory_events_and_respects_snooze():
    ds = chain_dataset()
    ds.events["EV_PS"] = replace(ds.events["EV_PS"], mandatory=True)
    snap = build_snapshot(ds, "T001", {"snoozes": {"T001": ["EV_SD"]}})
    nodes = {n["id"]: n for n in snap["career_graph"]["nodes"]}
    assert "activity:EV_PS" not in nodes
    assert nodes["activity:EV_SD"]["status"] == "blocked"
    assert {r["code"] for r in nodes["activity:EV_SD"]["reasons"]} == {"SNOOZED"}


def test_graph_valid_for_every_original_profile():
    ds = load_base_dataset()
    for eid in ds.employees:
        graph = build_snapshot(ds, eid, {})["career_graph"]
        node_ids = {n["id"] for n in graph["nodes"]}
        assert len(node_ids) == len(graph["nodes"])
        assert len({e["id"] for e in graph["edges"]}) == len(graph["edges"])
        assert all(e["source"] in node_ids and e["target"] in node_ids for e in graph["edges"])


def test_graph_target_status_does_not_inherit_higher_catalog_prerequisite():
    ds = chain_dataset()
    ds.role_profiles[("Backend Engineer", "Senior")] = ({"SK_SD": 1}, ["SK_SD"])
    graph = build_snapshot(ds, "T001", {})["career_graph"]
    nodes = {n["id"]: n for n in graph["nodes"]}
    assert nodes["goal"]["status"] == "met"
    assert nodes["skill:SK_SD"]["status"] == "met"
    assert nodes["activity:EV_ADV"]["status"] == "blocked"


def test_graph_api_serializes_and_retains_profile_access_checks(monkeypatch):
    from fastapi.testclient import TestClient

    from api.index import app

    monkeypatch.setenv("DEMO_EMPLOYEE_PASSWORD", "demo")
    with TestClient(app) as client:
        login = client.post("/api/py/auth/login", json={"login": "E0028", "password": "demo"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        response = client.post("/api/py/employees/E0028", headers=headers, json={})
        assert response.status_code == 200
        assert response.json()["career_graph"]["nodes"]
        assert client.post("/api/py/employees/E0029", headers=headers, json={}).status_code == 403
