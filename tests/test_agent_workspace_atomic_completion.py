"""Regression tests for atomic durable agent-step completion."""

from __future__ import annotations

import pytest

from gateway import agent_workspace


@pytest.fixture
def workspace_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", db_file)
    agent_workspace.init_db()
    return db_file


def test_nonfinal_agent_completion_clears_active_agent_in_same_commit(workspace_db):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")
    turn = agent_workspace.start_turn(room["id"], "Plan the first step.")
    agent_workspace._set_turn_active_agent(room["id"], turn["id"], "planner")

    message = agent_workspace._persist_agent_output(
        room["id"],
        turn["id"],
        agent_id="planner",
        recipient_id="researcher",
        content="planner response",
        message_kind="plan",
        parent_message_id=turn["user_message_id"],
        final_step=False,
    )

    persisted = agent_workspace.get_turn(room["id"], turn["id"])
    assert persisted["status"] == "running"
    assert persisted["active_agent_id"] is None
    assert message["sender_id"] == "planner"
    assert [event["type"] for event in agent_workspace.list_events(room["id"])[-2:]] == [
        "message_created",
        "agent_completed",
    ]


def test_final_agent_output_completes_turn_in_same_commit(workspace_db):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")
    turn = agent_workspace.start_turn(room["id"], "Plan the first step.")
    agent_workspace._set_turn_active_agent(room["id"], turn["id"], "reviewer")

    message = agent_workspace._persist_agent_output(
        room["id"],
        turn["id"],
        agent_id="reviewer",
        recipient_id="jacob",
        content="reviewer response",
        message_kind="review",
        parent_message_id=turn["user_message_id"],
        final_step=True,
    )

    persisted = agent_workspace.get_turn(room["id"], turn["id"])
    assert persisted["status"] == "completed"
    assert persisted["active_agent_id"] is None
    assert persisted["finished_at"] is not None
    assert message["sender_id"] == "reviewer"
    assert [event["type"] for event in agent_workspace.list_events(room["id"])[-3:]] == [
        "message_created",
        "agent_completed",
        "turn_completed",
    ]
