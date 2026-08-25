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
