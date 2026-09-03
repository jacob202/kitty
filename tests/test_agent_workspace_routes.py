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


def test_global_room_routes_ensure_and_share_one_stable_room(client):
    first = client.post("/agent-room/global/ensure")
    second = client.get("/agent-room/global")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"] == "workspace_global"
    assert [agent["id"] for agent in first.json()["agents"]] == [
        "chatgpt", "claude", "codex", "kitty", "dsh", "commandcode"
    ]


def test_global_room_post_recent_and_inbox_are_one_durable_truth(client):
    posted = client.post(
        "/agent-room/global/messages",
        json={
            "sender_id": "chatgpt",
            "recipient_id": "codex",
            "message_kind": "handoff",
            "content": "Review the room protocol.",
        },
    )
    assert posted.status_code == 201
    message_id = posted.json()["id"]

    recent = client.get("/agent-room/global/messages?limit=10")
    inbox = client.get("/agent-room/global/inbox/codex?unread_only=true&limit=10")
    inbox_again = client.get("/agent-room/global/inbox/codex?unread_only=true&limit=10")

    assert [item["id"] for item in recent.json()["messages"]] == [message_id]
    assert [item["id"] for item in inbox.json()["messages"]] == [message_id]
    assert inbox_again.json() == inbox.json()

def test_global_room_receipt_route_changes_unread_state_explicitly(client):
    posted = client.post(
        "/agent-room/global/messages",
        json={"sender_id": "chatgpt", "recipient_id": "codex",
              "message_kind": "status", "content": "Please acknowledge."},
    )
    message_id = posted.json()["id"]

    seen = client.post(
        f"/agent-room/global/messages/{message_id}/receipts",
        json={"participant_id": "codex", "state": "seen"},
    )
    assert seen.status_code == 200
    assert seen.json()["seen_at"] is not None
    assert seen.json()["acknowledged_at"] is None
    assert client.get("/agent-room/global/inbox/codex?unread_only=true").json() == {
        "messages": []
    }

    acknowledged = client.post(
        f"/agent-room/global/messages/{message_id}/receipts",
        json={"participant_id": "codex", "state": "acknowledged"},
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["seen_at"] == seen.json()["seen_at"]
    assert acknowledged.json()["acknowledged_at"] is not None


def test_global_room_thread_and_invalid_recipient_routes(client):
    root = client.post(
        "/agent-room/global/messages",
        json={"sender_id": "chatgpt", "message_kind": "prompt", "content": "Root"},
    ).json()
    reply = client.post(
        "/agent-room/global/messages",
        json={
            "sender_id": "codex", "recipient_id": "chatgpt",
            "message_kind": "review", "content": "Reply",
            "parent_message_id": root["id"],
        },
    ).json()

    thread = client.get(f"/agent-room/global/threads/{reply['id']}")
    assert thread.status_code == 200
    assert [item["id"] for item in thread.json()["messages"]] == [root["id"], reply["id"]]

    invalid = client.post(
        "/agent-room/global/messages",
        json={
            "sender_id": "chatgpt", "recipient_id": "imaginary",
            "message_kind": "status", "content": "Nope",
        },
    )
    assert invalid.status_code == 400
    assert "participant" in invalid.json()["detail"]
