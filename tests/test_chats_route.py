"""Tests for the /chats route after migration to chats_store (Phase C C3)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import app as app_module
from gateway import artifact_store, chat_lifecycle, chats_store
from gateway.routes import chats as chats_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Build a minimal FastAPI app around the chats router and isolate its DB."""
    db_file = tmp_path / "kitty" / "kitty.db"
    legacy_json = tmp_path / "kitty" / "chats.json"
    monkeypatch.setattr(chats_store, "CHATS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(artifact_store, "ARTIFACTS_DB_FILE", db_file, raising=False)
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


def test_restart_materializes_ledger_only_chat_for_reload_discovery(client):
    chat_lifecycle.start_turn(
        conversation_id="ledger-only",
        project_id=None,
        title="Interrupted first turn",
        user_message_id="user-first",
        user_text="Will this survive?",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )

    assert client.get("/chats").json() == {"chats": []}

    app_module._reconcile_chat_turns_on_startup()

    listed = client.get("/chats").json()["chats"]
    assert len(listed) == 1
    assert listed[0]["id"] == "ledger-only"
    assert listed[0]["title"] == "Interrupted first turn"
    assert listed[0]["messages"] == []
    assert listed[0]["model"] == "kitty-default"
    assert listed[0]["color"] == "purple"
    recovered = client.get("/chats/ledger-only/messages").json()["messages"]
    assert [message["role"] for message in recovered] == ["user", "assistant"]
    assert recovered[-1]["status"] == "interrupted"


def test_retry_recovery_suppresses_superseded_interruption_bubble(client):
    first = chat_lifecycle.start_turn(
        conversation_id="retry-chat",
        project_id=None,
        title="Retry chat",
        user_message_id="same-user-message",
        user_text="Try this",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )
    assert first.sequence == 1
    chat_lifecycle.reconcile_interrupted_turns()

    retry = chat_lifecycle.start_turn(
        conversation_id="retry-chat",
        project_id=None,
        title="Retry chat",
        user_message_id="same-user-message",
        user_text="Try this",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )
    chat_lifecycle.finish_turn(
        retry,
        status="succeeded",
        assistant_text="Recovered answer",
        resolved_model="kitty-default",
    )

    recovered = client.get("/chats/retry-chat/messages").json()["messages"]
    assert [(message["role"], message["content"]) for message in recovered] == [
        ("user", "Try this"),
        ("assistant", "Recovered answer"),
    ]
    assert all("restarted before this reply" not in message["content"] for message in recovered)


def test_restart_shell_records_the_actual_requested_model(client):
    chat_lifecycle.start_turn(
        conversation_id="model-shell",
        project_id=None,
        title="Non-default model turn",
        user_message_id="user-first",
        user_text="Use the good model",
        manifest_revision="test-revision",
        requested_model="gpt-5-pro",
    )

    app_module._reconcile_chat_turns_on_startup()

    listed = client.get("/chats").json()["chats"]
    assert len(listed) == 1
    assert listed[0]["model"] == "gpt-5-pro"


def test_restart_shell_is_materialized_before_turns_are_terminalized(client, monkeypatch):
    """A crash between shell creation and reconciliation must stay recoverable.

    If ``reconcile_interrupted_turns`` blows up after the shell for a
    still-running conversation was already written, the shell must not be
    lost: the next startup pass has to find the conversation again via
    ``list_running_conversations`` (the turn is still ``running``) and
    re-materialize it, which only works if the shell write happens first.
    """
    chat_lifecycle.start_turn(
        conversation_id="crash-window",
        project_id=None,
        title="Crash window",
        user_message_id="user-first",
        user_text="Will this survive a mid-pass crash?",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )

    def _boom():
        raise RuntimeError("simulated crash between shell write and reconciliation")

    monkeypatch.setattr(chat_lifecycle, "reconcile_interrupted_turns", _boom)

    with pytest.raises(RuntimeError):
        app_module._reconcile_chat_turns_on_startup()

    listed = client.get("/chats").json()["chats"]
    assert len(listed) == 1
    assert listed[0]["id"] == "crash-window"


def test_retry_recovery_preserves_original_attachments(client, tmp_path):
    attachment_path = tmp_path / "photo.png"
    attachment_path.write_bytes(b"fake-image-bytes")
    artifact = artifact_store.register_file(
        attachment_path,
        kind="image",
        media_type="image/png",
        project_id=None,
        created_by="user",
    )

    chat_lifecycle.start_turn(
        conversation_id="retry-with-attachment",
        project_id=None,
        title="Retry with attachment",
        user_message_id="same-user-message",
        user_text="Look at this",
        manifest_revision="test-revision",
        requested_model="kitty-default",
        attachment_ids=[artifact["id"]],
    )
    chat_lifecycle.reconcile_interrupted_turns()

    retry = chat_lifecycle.start_turn(
        conversation_id="retry-with-attachment",
        project_id=None,
        title="Retry with attachment",
        user_message_id="same-user-message",
        user_text="Look at this",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )
    chat_lifecycle.finish_turn(
        retry,
        status="succeeded",
        assistant_text="I see it.",
        resolved_model="kitty-default",
    )

    recovered = client.get("/chats/retry-with-attachment/messages").json()["messages"]
    user_message = next(message for message in recovered if message["role"] == "user")
    assert [a["id"] for a in user_message["attachments"]] == [artifact["id"]]
