"""Tests for the durable shared agent workspace vertical slice."""

from __future__ import annotations

import pytest

from gateway import agent_workspace


@pytest.fixture
def workspace_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", db_file)
    agent_workspace.init_db()
    return db_file


def test_create_workspace_seeds_named_agent_roster(workspace_db):
    room = agent_workspace.create_workspace(
        name="Kitty room",
        objective="Plan and verify a small feature",
    )

    assert room["id"].startswith("workspace_")
    assert room["name"] == "Kitty room"
    assert room["objective"] == "Plan and verify a small feature"
    assert [agent["id"] for agent in room["agents"]] == [
        "planner",
        "researcher",
        "builder",
        "reviewer",
    ]
    assert room["messages"] == []


def test_messages_are_durable_and_targetable_between_agents(workspace_db):
    room = agent_workspace.create_workspace(name="Kitty room", objective=None)

    user_message = agent_workspace.append_message(
        room["id"],
        sender_kind="user",
        sender_id="jacob",
        content="Investigate the current work surface.",
        message_kind="prompt",
    )
    handoff = agent_workspace.append_message(
        room["id"],
        sender_kind="agent",
        sender_id="planner",
        recipient_id="researcher",
        content="Research the existing Gateway work projection.",
        message_kind="handoff",
        parent_message_id=user_message["id"],
    )

    messages = agent_workspace.list_messages(room["id"])

    assert [message["id"] for message in messages] == [
        user_message["id"],
        handoff["id"],
    ]
    assert messages[1]["recipient_id"] == "researcher"
    assert messages[1]["parent_message_id"] == user_message["id"]
    assert [event["type"] for event in agent_workspace.list_events(room["id"])] == [
        "workspace_created",
        "message_created",
        "message_created",
    ]


class FakeWorkspaceBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list[dict]]] = []

    def complete(self, agent_id: str, prompt: str, context: list[dict]) -> str:
        self.calls.append((agent_id, prompt, context))
        return f"{agent_id} response"


def test_run_turn_persists_planner_specialist_and_reviewer_handoffs(workspace_db):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")
    backend = FakeWorkspaceBackend()

    result = agent_workspace.run_turn(
        room["id"],
        "Make a verified plan for the shared workspace.",
        backend=backend,
    )

    messages = agent_workspace.list_messages(room["id"])
    assert [message["sender_id"] for message in messages] == [
        "jacob",
        "planner",
        "researcher",
        "reviewer",
    ]
    assert [message["message_kind"] for message in messages] == [
        "prompt",
        "plan",
        "handoff",
        "review",
    ]
    assert messages[1]["recipient_id"] == "researcher"
    assert messages[2]["recipient_id"] == "reviewer"
    assert messages[3]["recipient_id"] == "jacob"
    assert result["status"] == "completed"
    assert [call[0] for call in backend.calls] == ["planner", "researcher", "reviewer"]
    assert "planner response" in backend.calls[1][2][-1]["content"]
    assert "researcher response" in backend.calls[2][2][-1]["content"]
