"""HTTP tests for the shared agent workspace routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import agent_workspace
from gateway.routes import agent_workspace as agent_workspace_route


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(
        agent_workspace,
        "WORKSPACE_DB_FILE",
        tmp_path / "kitty" / "kitty.db",
    )
    agent_workspace.init_db()
    app = FastAPI()
    app.include_router(agent_workspace_route.router)
    return TestClient(app)


class FakeBackend:
    def complete(self, agent_id: str, prompt: str, context: list[dict]) -> str:
        return f"{agent_id} completed the step"


def test_workspace_routes_create_read_and_run_turn(client, monkeypatch):
    monkeypatch.setattr(agent_workspace, "_default_backend", lambda: FakeBackend())

    created = client.post(
        "/agent-workspaces",
        json={"name": "Kitty room", "objective": "Ship a proof"},
    )
    assert created.status_code == 201
    workspace_id = created.json()["id"]

    turn = client.post(
        f"/agent-workspaces/{workspace_id}/turns",
        json={"message": "Create a verified plan."},
    )
    assert turn.status_code == 202
    body = turn.json()
    assert body["status"] == "running"
    assert body["turn"]["status"] == "running"

    read = client.get(f"/agent-workspaces/{workspace_id}")
    assert read.status_code == 200
    assert read.json()["agents"][0]["id"] == "planner"
    assert read.json()["turns"][0]["status"] == "completed"
    assert [message["sender_id"] for message in read.json()["messages"]] == [
        "jacob",
        "planner",
        "researcher",
        "builder",
        "reviewer",
    ]


def test_workspace_routes_reject_missing_room(client):
    response = client.get("/agent-workspaces/workspace_missing")

    assert response.status_code == 404
