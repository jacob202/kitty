"""Tests for the durable shared agent workspace vertical slice."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

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
    assert (
        next(agent for agent in room["agents"] if agent["id"] == "builder")["model"]
        == "kitty-default"
    )
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


class FailingWorkspaceBackend(FakeWorkspaceBackend):
    def complete(self, agent_id: str, prompt: str, context: list[dict]) -> str:
        if agent_id == "researcher":
            raise RuntimeError("configured provider rejected the researcher request")
        return super().complete(agent_id, prompt, context)


class TimeoutWorkspaceBackend(FakeWorkspaceBackend):
    def complete(self, agent_id: str, prompt: str, context: list[dict]) -> str:
        raise TimeoutError("the configured provider exceeded the 60 second room timeout")


def test_run_turn_persists_a_four_agent_lifecycle_and_builder_proposal(workspace_db):
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
        "builder",
        "reviewer",
    ]
    assert [message["message_kind"] for message in messages] == [
        "prompt",
        "plan",
        "handoff",
        "handoff",
        "review",
    ]
    assert messages[1]["recipient_id"] == "researcher"
    assert messages[2]["recipient_id"] == "builder"
    assert messages[3]["recipient_id"] == "reviewer"
    assert messages[4]["recipient_id"] == "jacob"
    assert result["status"] == "completed"
    assert result["turn"]["status"] == "completed"
    assert [call[0] for call in backend.calls] == ["planner", "researcher", "builder", "reviewer"]
    assert "planner response" in backend.calls[1][2][-1]["content"]
    assert "researcher response" in backend.calls[2][2][-1]["content"]
    assert "builder response" in backend.calls[3][2][-1]["content"]
    assert "cannot submit a Mission" in backend.calls[2][1]
    assert "create a queue task" in backend.calls[2][1]
    assert [event["type"] for event in result["events"]] == [
        "workspace_created",
        "message_created",
        "turn_started",
        "agent_started",
        "message_created",
        "agent_completed",
        "agent_started",
        "message_created",
        "agent_completed",
        "agent_started",
        "message_created",
        "agent_completed",
        "agent_started",
        "message_created",
        "agent_completed",
        "turn_completed",
    ]


def test_failed_agent_turn_keeps_partial_messages_and_a_durable_failure_record(workspace_db):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")

    result = agent_workspace.run_turn(
        room["id"],
        "Make a verified plan for the shared workspace.",
        backend=FailingWorkspaceBackend(),
    )

    assert result["status"] == "failed"
    assert result["turn"]["status"] == "failed"
    assert result["turn"]["active_agent_id"] is None
    assert result["turn"]["error_type"] == "RuntimeError"
    assert "provider rejected" in result["turn"]["error_message"]
    assert [message["sender_id"] for message in result["messages"]] == [
        "jacob",
        "planner",
        "gateway",
    ]
    assert result["messages"][-1]["message_kind"] == "status"
    assert result["messages"][-1]["parent_message_id"] == result["messages"][1]["id"]
    assert result["messages"][-1]["content"].startswith("Incomplete: researcher")
    assert [event["type"] for event in result["events"]][-3:] == [
        "agent_failed",
        "message_created",
        "turn_failed",
    ]
    assert "turn_completed" not in [event["type"] for event in result["events"]]

    reopened = agent_workspace.get_workspace(room["id"])
    assert reopened["turns"][0]["id"] == result["turn"]["id"]
    assert reopened["turns"][0]["status"] == "failed"


def test_timed_out_agent_turn_records_an_incomplete_durable_failure(workspace_db):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")

    result = agent_workspace.run_turn(
        room["id"],
        "Make a verified plan for the shared workspace.",
        backend=TimeoutWorkspaceBackend(),
    )

    assert result["status"] == "failed"
    assert result["turn"]["error_type"] == "TimeoutError"
    assert "60 second room timeout" in result["turn"]["error_message"]
    assert result["messages"][-1]["message_kind"] == "status"
    assert result["messages"][-1]["content"].startswith("Incomplete: planner")
    assert result["events"][-1]["type"] == "turn_failed"


def test_recovery_interrupts_an_orphaned_turn_and_allows_the_room_to_continue(workspace_db):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")
    running_turn = agent_workspace.start_turn(room["id"], "Plan the first step.")

    recovered = agent_workspace.interrupt_running_turns(
        reason="Gateway restarted before the room executor could finish."
    )

    assert recovered == 1
    reopened = agent_workspace.get_workspace(room["id"])
    interrupted = reopened["turns"][0]
    assert interrupted["id"] == running_turn["id"]
    assert interrupted["status"] == "interrupted"
    assert interrupted["error_type"] == "InterruptedError"
    assert "Gateway restarted" in interrupted["error_message"]
    assert reopened["messages"][-1]["message_kind"] == "status"
    assert reopened["messages"][-1]["content"].startswith("Incomplete: the room was interrupted")
    assert [event["type"] for event in reopened["events"]][-2:] == [
        "message_created",
        "turn_interrupted",
    ]

    resumed_turn = agent_workspace.start_turn(room["id"], "Continue after restart.")
    assert resumed_turn["status"] == "running"


def test_recovery_does_not_overwrite_a_turn_that_completed_after_its_snapshot(
    workspace_db, monkeypatch
):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")
    running_turn = agent_workspace.start_turn(room["id"], "Plan the first step.")
    original_messages = agent_workspace.list_messages(room["id"])
    original_events = agent_workspace.list_events(room["id"])
    real_connect = agent_workspace.kitty_db.connect

    class CompletionRaceConnection:
        def __init__(self, db_file):
            self._connection = real_connect(db_file)
            self._completed_competing_turn = False

        def __enter__(self):
            self._connection.__enter__()
            return self

        def __exit__(self, *args):
            return self._connection.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self._connection, name)

        def execute(self, sql, parameters=()):
            if not self._completed_competing_turn and "status = 'interrupted'" in sql:
                self._completed_competing_turn = True
                with real_connect(workspace_db) as competing_connection:
                    competing_connection.execute(
                        """
                        UPDATE agent_workspace_turns
                        SET status = 'completed', active_agent_id = NULL, finished_at = ?
                        WHERE id = ?
                        """,
                        (1.0, running_turn["id"]),
                    )
                    competing_connection.commit()
            return self._connection.execute(sql, parameters)

    monkeypatch.setattr(agent_workspace, "init_db", lambda: None)
    monkeypatch.setattr(agent_workspace.kitty_db, "connect", CompletionRaceConnection)

    assert agent_workspace.interrupt_running_turns() == 0

    reopened = agent_workspace.get_workspace(room["id"])
    assert reopened["turns"][0]["status"] == "completed"
    assert reopened["messages"] == original_messages
    assert reopened["events"] == original_events


def test_concurrent_submitters_admit_exactly_one_running_turn(workspace_db, monkeypatch):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")
    monkeypatch.setattr(agent_workspace, "init_db", lambda: None)
    barrier = Barrier(2)

    def submit() -> dict | Exception:
        barrier.wait()
        try:
            return agent_workspace.start_turn(room["id"], "Submit one durable room turn.")
        except Exception as exc:  # Return both thread outcomes for an exact assertion below.
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: submit(), range(2)))

    admitted = [outcome for outcome in outcomes if isinstance(outcome, dict)]
    rejected = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
    assert len(admitted) == 1
    assert len(rejected) == 1
    assert isinstance(rejected[0], agent_workspace.AgentWorkspaceError)
    assert "already has running" in str(rejected[0])
    assert [turn["status"] for turn in agent_workspace.list_turns(room["id"])] == ["running"]


def test_second_turn_reuses_the_first_turns_durable_room_context(workspace_db):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")
    backend = FakeWorkspaceBackend()

    first = agent_workspace.run_turn(room["id"], "Plan the first step.", backend=backend)
    second = agent_workspace.run_turn(room["id"], "Now refine the plan.", backend=backend)

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert [turn["status"] for turn in agent_workspace.list_turns(room["id"])] == [
        "completed",
        "completed",
    ]
    second_planner_context = backend.calls[4][2]
    assert any(message["sender_id"] == "reviewer" for message in second_planner_context)
    assert any("reviewer response" in message["content"] for message in second_planner_context)
