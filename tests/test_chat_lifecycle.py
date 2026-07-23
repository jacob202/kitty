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
