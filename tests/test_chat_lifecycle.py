"""Focused contracts for durable chat-conversation metadata."""

from gateway import chat_lifecycle


def test_start_turn_carries_objective_into_conversation(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file)

    chat_lifecycle.start_turn(
        conversation_id="chat-1",
        project_id=None,
        title="Goal chat",
        user_message_id="message-1",
        user_text="What should I do next?",
        manifest_revision="test-revision",
        requested_model="kitty-default",
        objective="Submit one application",
    )

    conversation = chat_lifecycle.list_conversation("chat-1")["conversation"]
    assert conversation["objective"] == "Submit one application"


def _start(db_file, monkeypatch, conversation_id="chat-mem"):
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file)
    return chat_lifecycle.start_turn(
        conversation_id=conversation_id,
        project_id=None,
        title="Memory chat",
        user_message_id="message-1",
        user_text="what informed this?",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )


def test_finish_turn_stores_memory_evidence_on_assistant_message(monkeypatch, tmp_path):
    handle = _start(tmp_path / "kitty" / "kitty.db", monkeypatch)

    chat_lifecycle.finish_turn(
        handle,
        status="succeeded",
        assistant_text="here is the answer",
        resolved_model="kitty-default",
        memory_items=[
            {"text": "decided on FastAPI", "memory_id": "mem-fastapi"},
            {"text": "prefers dark mode"},
        ],
    )

    turn = chat_lifecycle.get_turn(handle.turn_id)
    assistant = [m for m in turn["messages"] if m["role"] == "assistant"][0]
    import json as _json

    assert _json.loads(assistant["memory_items"]) == [
        {"text": "decided on FastAPI", "memory_id": "mem-fastapi"},
        {"text": "prefers dark mode"},
    ]


def test_finish_turn_without_memory_evidence_stores_null(monkeypatch, tmp_path):
    handle = _start(tmp_path / "kitty" / "kitty.db", monkeypatch)

    chat_lifecycle.finish_turn(
        handle, status="succeeded", assistant_text="plain answer"
    )

    turn = chat_lifecycle.get_turn(handle.turn_id)
    assistant = [m for m in turn["messages"] if m["role"] == "assistant"][0]
    assert assistant["memory_items"] is None


def test_finish_turn_rejects_invalid_memory_evidence(monkeypatch, tmp_path):
    handle = _start(tmp_path / "kitty" / "kitty.db", monkeypatch)

    import pytest

    with pytest.raises(chat_lifecycle.ChatLifecycleError, match="memory_items"):
        chat_lifecycle.finish_turn(
            handle,
            status="succeeded",
            assistant_text="answer",
            memory_items=[{"text": "ok"}, {"memory_id": "missing-text"}],
        )
