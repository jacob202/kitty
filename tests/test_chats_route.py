"""Tests for the /chats route after migration to chats_store (Phase C C3)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import chats_store
from gateway.routes import chats as chats_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Build a minimal FastAPI app around the chats router and isolate its DB."""
    db_file = tmp_path / "kitty" / "kitty.db"
    legacy_json = tmp_path / "kitty" / "chats.json"
    monkeypatch.setattr(chats_store, "CHATS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(chats_store, "LEGACY_CHATS_FILE", legacy_json, raising=False)
    app = FastAPI()
    app.include_router(chats_route.router)
    return TestClient(app)


def test_post_then_get_round_trip(client):
    payload = {"id": "abc", "title": "Hello"}

    post = client.post("/chats", json=payload)
    get = client.get("/chats")

    assert post.status_code == 200
    assert post.json() == {"ok": True}
    assert get.json() == {"chats": [payload]}


def test_post_rejects_missing_id(client):
    r = client.post("/chats", json={"title": "no id"})

    assert r.status_code == 400
    assert "id" in r.json()["detail"].lower()


def test_post_upsert_replaces(client):
    client.post("/chats", json={"id": "abc", "title": "v1"})
    post = client.post("/chats", json={"id": "abc", "title": "v2"})
    listed = client.get("/chats").json()["chats"]

    assert post.status_code == 200
    assert len(listed) == 1
    assert listed[0]["title"] == "v2"


def test_delete_removes(client):
    client.post("/chats", json={"id": "abc", "title": "x"})

    delete = client.delete("/chats/abc")
    listed = client.get("/chats")

    assert delete.status_code == 200
    assert listed.json() == {"chats": []}


def test_delete_missing_is_ok(client):
    r = client.delete("/chats/never-existed")

    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_patch_objective_sets_and_returns(client):
    client.post("/chats", json={"id": "abc", "title": "test"})

    patch = client.patch("/chats/abc/objective", json={"objective": "Find the answer"})
    assert patch.status_code == 200
    assert patch.json()["objective"] == "Find the answer"

    get = client.get("/chats")
    assert get.json()["chats"][0]["objective"] == "Find the answer"


def test_patch_objective_clears(client):
    client.post("/chats", json={"id": "abc", "title": "test"})
    client.patch("/chats/abc/objective", json={"objective": "thing"})
    patch = client.patch("/chats/abc/objective", json={"objective": None})

    assert patch.status_code == 200
    assert patch.json().get("objective") is None


def test_patch_objective_rejects_long_string(client):
    client.post("/chats", json={"id": "abc", "title": "test"})
    r = client.patch("/chats/abc/objective", json={"objective": "x" * 501})

    assert r.status_code == 400
    assert "500" in r.json()["detail"]


def test_patch_objective_rejects_non_string(client):
    client.post("/chats", json={"id": "abc", "title": "test"})
    r = client.patch("/chats/abc/objective", json={"objective": 42})

    assert r.status_code == 400


def test_patch_objective_requires_field(client):
    client.post("/chats", json={"id": "abc", "title": "test"})

    r = client.patch("/chats/abc/objective", json={})

    assert r.status_code == 400
    assert "objective" in r.json()["detail"]


def test_patch_objective_rejects_non_object_payload(client):
    client.post("/chats", json={"id": "abc", "title": "test"})

    r = client.patch("/chats/abc/objective", json=[])

    assert r.status_code == 400
    assert "object" in r.json()["detail"]


def test_patch_objective_missing_chat_returns_404(client):
    r = client.patch("/chats/no-such/objective", json={"objective": "goal"})

    assert r.status_code == 404


def test_ledger_recovery_carries_memory_evidence(client, monkeypatch, tmp_path):
    """CR-05b: /chats/{id}/messages restores the memory items recorded on the
    assistant message so the 'kitty remembered' block survives recovery."""
    from gateway import chat_lifecycle

    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file, raising=False)

    handle = chat_lifecycle.start_turn(
        conversation_id="chat-mem",
        project_id=None,
        title="Memory chat",
        user_message_id="message-1",
        user_text="what informed this?",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )
    chat_lifecycle.finish_turn(
        handle,
        status="succeeded",
        assistant_text="here is the answer",
        resolved_model="kitty-default",
        memory_items=["decided on FastAPI", "prefers dark mode"],
    )

    payload = client.get("/chats/chat-mem/messages").json()
    roles = {m["role"]: m for m in payload["messages"]}
    assert roles["assistant"]["memory_items"] == [
        "decided on FastAPI",
        "prefers dark mode",
    ]
    assert roles["user"]["memory_items"] == []
