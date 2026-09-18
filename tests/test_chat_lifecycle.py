"""Focused contracts for durable chat-conversation metadata."""

import types

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


def test_list_conversation_does_not_use_per_turn_getter(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file)

    first = chat_lifecycle.start_turn(
        conversation_id="chat-1",
        project_id=None,
        title="Recovery chat",
        user_message_id="message-1",
        user_text="First turn",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )
    chat_lifecycle.finish_turn(
        first,
        status="succeeded",
        assistant_text="First answer",
        resolved_model="kitty-default",
    )

    second = chat_lifecycle.start_turn(
        conversation_id="chat-1",
        project_id=None,
        title="Recovery chat",
        user_message_id="message-2",
        user_text="Second turn",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )
    chat_lifecycle.finish_turn(
        second,
        status="succeeded",
        assistant_text="Second answer",
        resolved_model="kitty-default",
    )

    def fail_if_called(_turn_id):
        raise AssertionError("list_conversation must not call get_turn once per turn")

    monkeypatch.setattr(chat_lifecycle, "get_turn", fail_if_called)

    result = chat_lifecycle.list_conversation("chat-1")

    assert [turn["sequence"] for turn in result["turns"]] == [1, 2]
    assert [turn["messages"][0]["content"] for turn in result["turns"]] == [
        "First turn",
        "Second turn",
    ]
    assert result["turns"][0]["attempts"][0]["status"] == "succeeded"
    assert result["turns"][1]["attempts"][0]["status"] == "succeeded"


def test_list_project_conversations_is_scoped_recent_and_bounded(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file)
    # Patch this module's clock, not the process-wide `time.time`. Installed
    # globally, a one-shot iterator of timestamps is consumed by any unrelated
    # caller in the same process — a telemetry or log-flusher thread, pytest
    # machinery — and the next call inside the test raises StopIteration.
    # Scoped to the module under test, only the code under test can consume it.
    ticks = iter([100.0, 200.0, 300.0])
    monkeypatch.setattr(
        chat_lifecycle, "time", types.SimpleNamespace(time=lambda: next(ticks))
    )

    for conversation_id, project_id, title in [
        ("chat-old", 7, "Older project chat"),
        ("chat-other", 8, "Other project chat"),
        ("chat-new", 7, "Newest project chat"),
    ]:
        chat_lifecycle.start_turn(
            conversation_id=conversation_id,
            project_id=project_id,
            title=title,
            user_message_id=f"message-{conversation_id}",
            user_text="hello",
            manifest_revision="test-revision",
            requested_model="kitty-default",
        )

    rows = chat_lifecycle.list_project_conversations(7, limit=1)

    assert [row["id"] for row in rows] == ["chat-new"]
    assert rows[0]["title"] == "Newest project chat"
    assert rows[0]["project_id"] == 7
    assert "turns" not in rows[0]


def test_reconcile_running_turns_marks_restart_interrupted_and_is_idempotent(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file)

    handle = chat_lifecycle.start_turn(
        conversation_id="chat-restart",
        project_id=None,
        title="Restart recovery",
        user_message_id="message-restart",
        user_text="Are you still there?",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )

    assert chat_lifecycle.reconcile_interrupted_turns() == 1
    assert chat_lifecycle.reconcile_interrupted_turns() == 0

    state = chat_lifecycle.list_conversation("chat-restart")
    turn = state["turns"][0]
    assert turn["id"] == handle.turn_id
    assert turn["status"] == "interrupted"
    assert turn["error"] == "Gateway restarted before the chat turn finished"
    assert turn["attempts"][0]["status"] == "interrupted"
    assert turn["attempts"][0]["error"] == "Gateway restarted before the chat turn finished"

    assistant_messages = [message for message in turn["messages"] if message["role"] == "assistant"]
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["status"] == "interrupted"
    assert assistant_messages[0]["content"] == (
        "Kitty restarted before this reply finished. Tap retry to try again."
    )


def test_reconcile_running_turns_does_not_touch_terminal_turns(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file)

    handle = chat_lifecycle.start_turn(
        conversation_id="chat-complete",
        project_id=None,
        title="Completed chat",
        user_message_id="message-complete",
        user_text="What is done?",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )
    chat_lifecycle.finish_turn(
        handle,
        status="succeeded",
        assistant_text="This turn is complete.",
        resolved_model="kitty-default",
    )

    assert chat_lifecycle.reconcile_interrupted_turns() == 0
    turn = chat_lifecycle.list_conversation("chat-complete")["turns"][0]
    assert turn["status"] == "succeeded"
    assert turn["attempts"][0]["status"] == "succeeded"
    assert [m["content"] for m in turn["messages"] if m["role"] == "assistant"] == [
        "This turn is complete."
    ]


def test_reconcile_only_latest_orphan_in_conversation_promises_retry(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file)

    chat_lifecycle.start_turn(
        conversation_id="multi-orphan",
        project_id=None,
        title="Two tabs",
        user_message_id="user-one",
        user_text="First tab",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )
    chat_lifecycle.start_turn(
        conversation_id="multi-orphan",
        project_id=None,
        title="Two tabs",
        user_message_id="user-two",
        user_text="Second tab",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )

    assert chat_lifecycle.reconcile_interrupted_turns() == 2
    turns = chat_lifecycle.list_conversation("multi-orphan")["turns"]
    assistant_texts = [
        next(message["content"] for message in turn["messages"] if message["role"] == "assistant")
        for turn in turns
    ]
    assert assistant_texts[0] == "Kitty restarted before this reply finished."
    assert assistant_texts[1] == "Kitty restarted before this reply finished. Tap retry to try again."


def test_reconcile_withholds_retry_when_a_later_turn_already_finished(monkeypatch, tmp_path):
    """A finished later turn, not an earlier still-running one, is the real latest."""
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file)

    earlier = chat_lifecycle.start_turn(
        conversation_id="race",
        project_id=None,
        title="Race",
        user_message_id="user-earlier",
        user_text="First tab, slow to finish",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )
    later = chat_lifecycle.start_turn(
        conversation_id="race",
        project_id=None,
        title="Race",
        user_message_id="user-later",
        user_text="Second tab, fast to finish",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )
    chat_lifecycle.finish_turn(
        later,
        status="succeeded",
        assistant_text="Done before the crash.",
        resolved_model="kitty-default",
    )

    assert chat_lifecycle.reconcile_interrupted_turns() == 1

    turns = chat_lifecycle.list_conversation("race")["turns"]
    earlier_turn = next(turn for turn in turns if turn["id"] == earlier.turn_id)
    assistant_message = next(
        message for message in earlier_turn["messages"] if message["role"] == "assistant"
    )
    assert assistant_message["content"] == "Kitty restarted before this reply finished."


def test_list_running_conversations_reports_the_requested_model(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file)

    chat_lifecycle.start_turn(
        conversation_id="model-chat",
        project_id=None,
        title="Non-default model",
        user_message_id="user-1",
        user_text="Use the good model",
        manifest_revision="test-revision",
        requested_model="gpt-5-pro",
    )

    running = chat_lifecycle.list_running_conversations()
    assert len(running) == 1
    assert running[0]["requested_model"] == "gpt-5-pro"

def test_finish_turn_persists_source_evidence_separately_from_memory(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file)
    handle = chat_lifecycle.start_turn(
        conversation_id="chat-evidence",
        project_id=None,
        title="Evidence chat",
        user_message_id="user-evidence",
        user_text="What does the source say?",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )
    receipt = {
        "evidence_id": "E1",
        "text": "Exact excerpt",
        "title": "Service Manual",
        "locator_start": "12",
    }
    chat_lifecycle.finish_turn(
        handle,
        status="succeeded",
        assistant_text="See [E1].",
        resolved_model="kitty-default",
        memory_items=[{"text": "remembered preference"}],
        evidence_items=[receipt],
    )
    assistant = next(
        message for message in chat_lifecycle.get_turn(handle.turn_id)["messages"]
        if message["role"] == "assistant"
    )
    assert 'remembered preference' in assistant["memory_items"]
    assert '"evidence_id": "E1"' in assistant["evidence_items"]
    assert 'Service Manual' in assistant["evidence_items"]


def test_finish_turn_persists_evidence_with_empty_assistant_text(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(chat_lifecycle, "LIFECYCLE_DB_FILE", db_file)
    handle = chat_lifecycle.start_turn(
        conversation_id="chat-empty-evidence",
        project_id=None,
        title="Empty evidence chat",
        user_message_id="user-empty-evidence",
        user_text="Return the source receipt",
        manifest_revision="test-revision",
        requested_model="kitty-default",
    )
    chat_lifecycle.finish_turn(
        handle,
        status="succeeded",
        assistant_text="",
        resolved_model="kitty-default",
        evidence_items=[{
            "evidence_id": "E1",
            "text": "Exact excerpt",
        }],
    )

    assistant = next(
        message for message in chat_lifecycle.get_turn(handle.turn_id)["messages"]
        if message["role"] == "assistant"
    )
    assert assistant["content"] == ""
    assert '"evidence_id": "E1"' in assistant["evidence_items"]
