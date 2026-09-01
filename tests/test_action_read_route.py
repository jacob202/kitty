"""Regression coverage for reading one ActionQueue item by durable id."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import action_grants, action_queue
from gateway.routes import actions as actions_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(action_queue, "ACTIONS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_file, raising=False)
    action_queue.reload_registry()
    app = FastAPI()
    app.include_router(actions_route.router)
    yield TestClient(app)
    action_queue.reload_registry()


def test_reads_one_action_with_exact_payload(client):
    proposed = client.post(
        "/actions/propose",
        json={
            "source_kind": "chat",
            "kind": "todo.create",
            "title": "Add follow-up",
            "preview": "Create the follow-up todo",
            "payload": {"content": "Call Alex tomorrow"},
        },
    ).json()

    response = client.get(f"/actions/{proposed['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == proposed["id"]
    assert response.json()["payload"] == {"content": "Call Alex tomorrow"}
    assert response.json()["status"] == "proposed"


def test_missing_action_read_is_404(client):
    response = client.get("/actions/999999")

    assert response.status_code == 404
    assert "no action" in response.json()["detail"].lower()


def test_read_action_reports_current_effective_tier(client, monkeypatch):
    proposed = client.post(
        "/actions/propose",
        json={
            "source_kind": "chat",
            "kind": "todo.create",
            "title": "Add follow-up",
            "preview": "Create the follow-up todo",
            "payload": {"content": "Call Alex tomorrow"},
        },
    ).json()
    assert proposed["risk_tier"] == "T0"

    registry = dict(action_queue._registry())
    _, executor = registry["todo.create"]
    registry["todo.create"] = ("T2", executor)
    monkeypatch.setattr(action_queue, "_REGISTRY", registry)

    response = client.get(f"/actions/{proposed['id']}")

    assert response.status_code == 200
    assert response.json()["risk_tier"] == "T0"
    assert response.json()["effective_risk_tier"] == "T2"


def test_read_action_reports_current_grant_decision(client):
    proposed = client.post(
        "/actions/propose",
        json={
            "source_kind": "chat",
            "kind": "todo.create",
            "title": "Add follow-up",
            "preview": "Create the follow-up todo",
            "payload": {"content": "Call Alex tomorrow"},
        },
    ).json()

    baseline = client.get(f"/actions/{proposed['id']}").json()
    assert baseline["execution_decision"]["outcome"] == "allow"

    action_grants.create_grant(
        capability="todo.create",
        decision="ask",
        granted_tier="T0",
        reason="ask every time",
        created_by="user",
    )
    asking = client.get(f"/actions/{proposed['id']}").json()
    assert asking["execution_decision"] == {"outcome": "ask", "basis": "scoped_ask"}

    approved = client.post(f"/actions/{proposed['id']}/approve").json()
    assert approved["status"] == "approved"
    after_approval = client.get(f"/actions/{proposed['id']}").json()
    assert after_approval["execution_decision"]["outcome"] == "allow"
    assert after_approval["execution_decision"]["basis"] == "one_shot_approval"


def test_read_action_reports_scoped_deny(client):
    proposed = client.post(
        "/actions/propose",
        json={
            "source_kind": "chat",
            "kind": "todo.create",
            "title": "Add follow-up",
            "preview": "Create the follow-up todo",
            "payload": {"content": "Call Alex tomorrow"},
        },
    ).json()
    action_grants.create_grant(
        capability="todo.create",
        decision="deny",
        granted_tier="T0",
        reason="never here",
        created_by="user",
    )

    response = client.get(f"/actions/{proposed['id']}")

    assert response.status_code == 200
    assert response.json()["execution_decision"] == {"outcome": "deny", "basis": "scoped_deny"}
