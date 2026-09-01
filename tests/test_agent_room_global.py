"""Protocol tests for Kitty's canonical global agent room."""

from __future__ import annotations

import pytest

from gateway import agent_room_cli
from gateway import agent_workspace
from gateway import db as kitty_db


@pytest.fixture
def room_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", db_file)
    agent_workspace.init_db()
    return db_file


def test_global_room_is_stable_idempotent_and_has_real_agent_roster(room_db):
    first = agent_workspace.ensure_global_workspace()
    second = agent_workspace.ensure_global_workspace()

    assert first["id"] == second["id"] == "workspace_global"
    assert [agent["id"] for agent in first["agents"]] == [
        "chatgpt", "claude", "codex", "kitty"
    ]
    assert {agent["status"] for agent in first["agents"]} == {"registered"}
    assert all(agent["model"] is None for agent in first["agents"])
    assert len(agent_workspace.list_events("workspace_global")) == 1


def test_global_post_validates_participants_and_preserves_sender_kind(room_db):
    agent_workspace.ensure_global_workspace()

    message = agent_workspace.post_global_message(
        sender_id="jacob",
        recipient_id="claude",
        content="Please inspect the room contract.",
        message_kind="prompt",
    )

    assert message["sender_kind"] == "user"
    assert message["sender_id"] == "jacob"
    assert message["recipient_id"] == "claude"

    with pytest.raises(agent_workspace.AgentWorkspaceError, match="participant"):
        agent_workspace.post_global_message(
            sender_id="chatgpt",
            recipient_id="made-up-agent",
            content="This must fail closed.",
            message_kind="status",
        )

    with pytest.raises(agent_workspace.AgentWorkspaceError, match="participant"):
        agent_workspace.post_global_message(
            sender_id="made-up-agent",
            content="This sender must also fail closed.",
            message_kind="status",
        )


def test_inbox_contains_addressed_messages_but_not_other_or_self_messages(room_db):
    agent_workspace.ensure_global_workspace()
    broadcast = agent_workspace.post_global_message(
        sender_id="chatgpt", content="Room update", message_kind="status"
    )
    direct = agent_workspace.post_global_message(
        sender_id="chatgpt", recipient_id="claude",
        content="Claude-only handoff", message_kind="handoff",
    )
    agent_workspace.post_global_message(
        sender_id="chatgpt", recipient_id="codex",
        content="Codex-only handoff", message_kind="handoff",
    )
    agent_workspace.post_global_message(
        sender_id="claude", content="Claude broadcast", message_kind="status"
    )

    inbox = agent_workspace.list_inbox("claude")

    assert [item["id"] for item in inbox] == [broadcast["id"], direct["id"]]
    assert all(item["seen_at"] is None for item in inbox)
    assert all(item["acknowledged_at"] is None for item in inbox)
    assert agent_workspace.list_inbox("claude", unread_only=True) == inbox


def test_inbox_respects_participant_join_time(room_db):
    agent_workspace.ensure_global_workspace()
    first = agent_workspace.post_global_message(
        sender_id="chatgpt", content="Before join", message_kind="status"
    )
    second = agent_workspace.post_global_message(
        sender_id="chatgpt", content="After join", message_kind="status"
    )
    joined_at = (first["created_at"] + second["created_at"]) / 2
    with kitty_db.connect(room_db) as conn:
        conn.execute(
            "UPDATE agent_workspace_agents SET created_at = ? "
            "WHERE workspace_id = 'workspace_global' AND agent_id = 'claude'",
            (joined_at,),
        )
        conn.commit()

    inbox = agent_workspace.list_inbox("claude")

    assert [item["id"] for item in inbox] == [second["id"]]


def test_receipts_are_explicit_monotonic_and_durable(room_db):
    agent_workspace.ensure_global_workspace()
    message = agent_workspace.post_global_message(
        sender_id="chatgpt", recipient_id="claude",
        content="Please acknowledge.", message_kind="handoff",
    )

    assert agent_workspace.list_inbox("claude", unread_only=True)[0]["id"] == message["id"]
    seen = agent_workspace.record_receipt(message["id"], "claude", "seen")
    assert seen["seen_at"] is not None
    assert seen["acknowledged_at"] is None
    assert agent_workspace.list_inbox("claude", unread_only=True) == []

    acknowledged = agent_workspace.record_receipt(
        message["id"], "claude", "acknowledged"
    )
    assert acknowledged["seen_at"] == seen["seen_at"]
    assert acknowledged["acknowledged_at"] is not None

    after_seen_again = agent_workspace.record_receipt(message["id"], "claude", "seen")
    assert after_seen_again == acknowledged

    agent_workspace.init_db()
    persisted = agent_workspace.list_inbox("claude")[0]
    assert persisted["seen_at"] == acknowledged["seen_at"]
    assert persisted["acknowledged_at"] == acknowledged["acknowledged_at"]

    with pytest.raises(agent_workspace.AgentWorkspaceError, match="participant"):
        agent_workspace.record_receipt(message["id"], "unknown", "seen")
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="message"):
        agent_workspace.record_receipt("message_missing", "claude", "seen")
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="state"):
        agent_workspace.record_receipt(message["id"], "claude", "delivered")


def test_thread_resolves_root_and_descendants_from_any_message(room_db):
    agent_workspace.ensure_global_workspace()
    root = agent_workspace.post_global_message(
        sender_id="chatgpt", content="Root", message_kind="prompt"
    )
    reply = agent_workspace.post_global_message(
        sender_id="claude", recipient_id="chatgpt", content="Reply",
        message_kind="review", parent_message_id=root["id"],
    )
    nested = agent_workspace.post_global_message(
        sender_id="codex", recipient_id="claude", content="Nested",
        message_kind="result", parent_message_id=reply["id"],
    )

    thread = agent_workspace.list_thread(nested["id"])

    assert [item["id"] for item in thread] == [root["id"], reply["id"], nested["id"]]


def test_global_reply_rejects_parent_from_another_workspace(room_db):
    agent_workspace.ensure_global_workspace()
    other = agent_workspace.create_workspace(name="Other", objective=None)
    other_message = agent_workspace.append_message(
        other["id"], sender_kind="user", sender_id="jacob",
        content="Different room", message_kind="prompt",
    )

    with pytest.raises(agent_workspace.AgentWorkspaceError, match="parent message"):
        agent_workspace.post_global_message(
            sender_id="chatgpt", content="Must stay in global room",
            message_kind="status", parent_message_id=other_message["id"],
        )

    with pytest.raises(agent_workspace.AgentWorkspaceError, match="message"):
        agent_workspace.list_thread(other_message["id"])


def test_direct_only_inbox_filters_before_limit(room_db):
    agent_workspace.ensure_global_workspace()
    direct = agent_workspace.post_global_message(
        sender_id="jacob",
        recipient_id="claude",
        content="Older direct request",
        message_kind="prompt",
    )
    agent_workspace.post_global_message(
        sender_id="chatgpt",
        content="Newer broadcast",
        message_kind="status",
    )

    inbox = agent_workspace.list_inbox(
        "claude", unread_only=True, direct_only=True, limit=1
    )

    assert [item["id"] for item in inbox] == [direct["id"]]


def test_room_cli_direct_only_flag_reaches_domain(monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def fake_list_inbox(participant_id, *, unread_only=False, direct_only=False, limit=100):
        seen.update(
            participant_id=participant_id,
            unread_only=unread_only,
            direct_only=direct_only,
            limit=limit,
        )
        return []

    monkeypatch.setattr(agent_room_cli.agent_workspace, "list_inbox", fake_list_inbox)
    args = agent_room_cli._parser().parse_args(
        ["inbox", "--as", "claude", "--unread", "--direct-only", "--limit", "1"]
    )

    assert agent_room_cli._dispatch(args) == []
    assert seen == {
        "participant_id": "claude",
        "unread_only": True,
        "direct_only": True,
        "limit": 1,
    }
