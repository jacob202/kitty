"""Tests for the /actions routes (P3) — lifecycle + tier enforcement over HTTP."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import action_queue, calendar_integration, todo_store
from gateway.routes import actions as actions_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(action_queue, "ACTIONS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(action_queue, "DRAFTS_DIR", tmp_path / "drafts", raising=False)
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(calendar_integration, "create", lambda *a, **k: True)
    action_queue.reload_registry()
    app = FastAPI()
    app.include_router(actions_route.router)
    yield TestClient(app)
    action_queue.reload_registry()


def _propose(client, kind, payload):
    return client.post(
        "/actions/propose",
        json={
            "source_kind": "manual",
            "kind": kind,
            "title": f"{kind} action",
            "preview": f"will run {kind}",
            "payload": payload,
        },
    )


def test_propose_returns_proposed_action(client):
    r = _propose(client, "todo.create", {"content": "ship it"})

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "proposed"
    assert body["risk_tier"] == "T0"


def test_t0_execute_from_proposed_over_http(client):
    action_id = _propose(client, "todo.create", {"content": "ship it"}).json()["id"]

    r = client.post(f"/actions/{action_id}/execute")

    assert r.status_code == 200
    assert r.json()["status"] == "executed"


def test_t2_execute_without_approval_returns_403(client):
    action_id = _propose(client, "calendar.event.create", {"title": "Dentist"}).json()["id"]

    r = client.post(f"/actions/{action_id}/execute")

    assert r.status_code == 403


def test_t2_approve_then_execute_over_http(client):
    action_id = _propose(client, "calendar.event.create", {"title": "Dentist"}).json()["id"]

    assert client.post(f"/actions/{action_id}/approve").status_code == 200
    r = client.post(f"/actions/{action_id}/execute")

    assert r.status_code == 200
    assert r.json()["status"] == "executed"


def test_disabled_kind_returns_400(client):
    r = _propose(client, "email.send", {"content": "hi"})

    assert r.status_code == 400


def test_missing_payload_field_returns_400(client):
    r = _propose(client, "todo.create", {})

    assert r.status_code == 400


def test_execute_missing_action_returns_404(client):
    r = client.post("/actions/999999/execute")

    assert r.status_code == 404


def test_list_actions_filters_by_status(client):
    _propose(client, "todo.create", {"content": "one"})

    r = client.get("/actions", params={"status": "proposed"})

    assert r.status_code == 200
    actions = r.json()["actions"]
    assert len(actions) == 1
    assert actions[0]["kind"] == "todo.create"
