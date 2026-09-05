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


def test_list_messages_returns_newest_window_in_chronological_order(workspace_db):
    room = agent_workspace.create_workspace(name="Kitty room", objective=None)
    for index in range(10):
        agent_workspace.append_message(
            room["id"],
            sender_kind="user",
            sender_id="jacob",
            content=f"turn {index}",
            message_kind="prompt",
        )

    windowed = agent_workspace.list_messages(room["id"], limit=3)

    # Bounded callers must see the *newest* messages, not the oldest, and in
    # chronological (not reverse-chronological) order.
    assert [message["content"] for message in windowed] == ["turn 7", "turn 8", "turn 9"]


def test_get_workspace_reads_messages_events_and_turns_from_one_snapshot(
    workspace_db, monkeypatch
):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")
    running_turn = agent_workspace.start_turn(room["id"], "Plan the first step.")
    real_connect = agent_workspace.kitty_db.connect

    class InterleavedWriteConnection:
        """Commits a competing write between get_workspace's reads."""

        def __init__(self, db_file):
            self._connection = real_connect(db_file)
            self._interleaved = False

        def __enter__(self):
            self._connection.__enter__()
            return self

        def __exit__(self, *args):
            return self._connection.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self._connection, name)

        def execute(self, sql, parameters=()):
            result = self._connection.execute(sql, parameters)
            if not self._interleaved and "FROM agent_workspace_agents" in sql:
                self._interleaved = True
                with real_connect(workspace_db) as writer:
                    writer.execute(
                        """
                        INSERT INTO agent_workspace_messages
                            (id, workspace_id, parent_message_id, sender_kind, sender_id,
                             recipient_id, message_kind, content, created_at)
                        VALUES ('message_interleaved', ?, NULL, 'agent', 'planner',
                                NULL, 'plan', 'late write', 999999)
                        """,
                        (room["id"],),
                    )
                    writer.execute(
                        """
                        UPDATE agent_workspace_turns
                        SET status = 'completed', active_agent_id = NULL, finished_at = 999999
                        WHERE id = ?
                        """,
                        (running_turn["id"],),
                    )
                    writer.commit()
            return result

    monkeypatch.setattr(agent_workspace, "init_db", lambda: None)
    monkeypatch.setattr(agent_workspace.kitty_db, "connect", InterleavedWriteConnection)

    reopened = agent_workspace.get_workspace(room["id"])

    # The snapshot must not mix pre-write turns with post-write messages (or
    # vice versa): either the interleaved write is fully visible or not at all.
    turn_saw_completion = reopened["turns"][0]["status"] == "completed"
    message_saw_write = any(
        message["id"] == "message_interleaved" for message in reopened["messages"]
    )
    assert turn_saw_completion == message_saw_write


def test_run_persisted_turn_does_not_append_after_the_turn_is_interrupted(workspace_db):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")
    turn = agent_workspace.start_turn(room["id"], "Plan the first step.")

    class InterruptingBackend(FakeWorkspaceBackend):
        def complete(self, agent_id: str, prompt: str, context: list[dict]) -> str:
            # Simulate a Gateway restart recovering this turn while the model
            # call for the *first* step is still in flight.
            agent_workspace.interrupt_running_turns(reason="restarted mid-flight")
            return super().complete(agent_id, prompt, context)

    result = agent_workspace.run_persisted_turn(
        room["id"], turn["id"], backend=InterruptingBackend()
    )

    assert result["turn"]["status"] == "interrupted"
    assert result["turn"]["error_type"] == "InterruptedError"
    # No late planner message should have landed on top of the interruption record.
    assert not any(
        message["sender_id"] == "planner" for message in result["messages"]
    )
    assert result["messages"][-1]["content"].startswith("Incomplete: planner was interrupted")


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


class DeadProviderChainBackend(FakeWorkspaceBackend):
    """The #498 shape: the room dies partway with the whole chain down."""

    def complete(self, agent_id: str, prompt: str, context: list[dict]) -> str:
        if agent_id == "builder":
            from gateway.llm_client import ProviderChainExhausted

            raise ProviderChainExhausted(
                [
                    "litellm: HTTPConnectionPool(host='127.0.0.1', port=4000): Max retries",
                    "openrouter: no api key configured",
                    "agentrouter: disabled",
                ]
            )
        return super().complete(agent_id, prompt, context)


def test_dead_provider_chain_reaches_the_room_as_plain_language(workspace_db):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")

    result = agent_workspace.run_turn(
        room["id"],
        "Make a verified plan for the shared workspace.",
        backend=DeadProviderChainBackend(),
    )

    assert result["status"] == "failed"
    status_message = result["messages"][-1]["content"]
    assert status_message.startswith("Incomplete: builder could not finish.")
    assert "no model provider it can use" in status_message
    assert "Setting up a provider is required" in status_message
    # The operator mechanics that used to land in Jacob's conversation stay out.
    for leak in ("HTTPConnectionPool", "ProviderChainExhausted", "api key", "./kitty", ".env"):
        assert leak.lower() not in status_message.lower(), leak


def test_dead_provider_chain_keeps_raw_diagnostics_in_the_event_log(workspace_db):
    room = agent_workspace.create_workspace(name="Kitty room", objective="Ship a proof")

    result = agent_workspace.run_turn(
        room["id"],
        "Make a verified plan for the shared workspace.",
        backend=DeadProviderChainBackend(),
    )

    failed = [event for event in result["events"] if event["type"] == "agent_failed"][-1]
    assert failed["metadata"]["error_type"] == "ProviderChainExhausted"
    assert "openrouter: no api key configured" in failed["metadata"]["error_message"]


def test_direct_assignment_inbox_excludes_routine_broadcasts_without_marking_receipts(workspace_db):
    agent_workspace.ensure_global_workspace()
    direct = agent_workspace.post_global_message(
        sender_id="jacob",
        recipient_id="codex",
        content="Please review this handoff.",
        message_kind="handoff",
    )
    broadcast = agent_workspace.post_global_message(
        sender_id="chatgpt",
        content="Routine shared status.",
        message_kind="status",
    )

    assignments = agent_workspace.list_inbox(
        "codex", unread_only=True, direct_only=True
    )

    assert [message["id"] for message in assignments] == [direct["id"]]
    assert assignments[0]["receipt_state"] == "sent"
    assert assignments[0]["seen_at"] is None
    assert assignments[0]["acknowledged_at"] is None

    shared_inbox = agent_workspace.list_inbox("codex", unread_only=True)
    assert [message["id"] for message in shared_inbox] == [direct["id"], broadcast["id"]]
    assert all(message["receipt_state"] == "sent" for message in shared_inbox)


def test_reply_to_direct_message_records_consumption_without_acknowledging_broadcast(workspace_db):
    agent_workspace.ensure_global_workspace()
    direct = agent_workspace.post_global_message(
        sender_id="jacob", recipient_id="codex", content="Please review.", message_kind="review"
    )
    broadcast = agent_workspace.post_global_message(
        sender_id="chatgpt", content="Shared status.", message_kind="status"
    )

    agent_workspace.post_global_message(
        sender_id="codex", recipient_id="jacob", content="Reviewed.",
        message_kind="review", parent_message_id=direct["id"],
    )
    agent_workspace.post_global_message(
        sender_id="codex", content="Following up in thread.",
        message_kind="status", parent_message_id=broadcast["id"],
    )

    inbox = {item["id"]: item for item in agent_workspace.list_inbox("codex")}
    assert inbox[direct["id"]]["receipt_state"] == "acknowledged"
    assert inbox[broadcast["id"]]["receipt_state"] == "sent"


def test_mission_continuity_modules_are_available():
    import importlib.util

    assert importlib.util.find_spec("gateway.memory_mission") is not None
    assert importlib.util.find_spec("gateway.context_mission") is not None


def test_mission_state_persists_independently_of_worker_sessions(tmp_path):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    created = memory_mission.create_mission(
        mission_id="life-2",
        objective="Build a life worth participating in",
        definition_of_done=["durable coordination exists"],
        supervisor_id="chad",
        db_path=db_path,
    )

    reopened = memory_mission.get_mission("life-2", db_path=db_path)

    assert reopened == created
    assert reopened["mission_id"] == "life-2"
    assert reopened["status"] == "PLANNING"
    assert reopened["supervisor"] == {"id": "chad", "epoch": 1}
    assert reopened["definition_of_done"] == ["durable coordination exists"]


def test_mission_list_returns_durable_rows_most_recent_first(tmp_path, monkeypatch):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    stamps = iter((100.0, 200.0))
    monkeypatch.setattr(memory_mission.time, "time", lambda: next(stamps))

    memory_mission.create_mission(
        mission_id="mission-older",
        objective="Older objective",
        definition_of_done=["older done"],
        supervisor_id="supervisor-a",
        db_path=db_path,
    )
    memory_mission.create_mission(
        mission_id="mission-newer",
        objective="Newer objective",
        definition_of_done=["newer done"],
        supervisor_id="supervisor-b",
        db_path=db_path,
    )

    listed = memory_mission.list_missions(db_path=db_path)

    assert [mission["mission_id"] for mission in listed] == [
        "mission-newer",
        "mission-older",
    ]
    assert listed[0]["objective"] == "Newer objective"
    assert listed[1]["status"] == "PLANNING"


def test_mission_execution_requires_current_independent_plan_review(tmp_path):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    memory_mission.create_mission(
        mission_id="life-2",
        objective="Coordinate Life 2.0",
        definition_of_done=["verified outcome"],
        supervisor_id="chad",
        db_path=db_path,
    )
    digest = "a" * 64
    memory_mission.set_plan(
        "life-2", plan_ref="plan://life-2/v1", plan_digest=digest, db_path=db_path
    )

    with pytest.raises(memory_mission.MissionError, match="independent"):
        memory_mission.record_plan_review(
            "life-2", reviewer_id="chad", plan_digest=digest,
            verdict="approved", db_path=db_path,
        )
    with pytest.raises(memory_mission.MissionError, match="current plan"):
        memory_mission.record_plan_review(
            "life-2", reviewer_id="verifier", plan_digest="b" * 64,
            verdict="approved", db_path=db_path,
        )
    with pytest.raises(memory_mission.MissionError, match="approved plan review"):
        memory_mission.begin_execution("life-2", db_path=db_path)

    memory_mission.record_plan_review(
        "life-2", reviewer_id="verifier", plan_digest=digest,
        verdict="approved", evidence={"review": "separate-process"}, db_path=db_path,
    )
    executing = memory_mission.begin_execution("life-2", db_path=db_path)
    assert executing["status"] == "EXECUTING"
    assert executing["plan"]["review_state"] == "approved"


def test_replacing_mission_supervisor_fences_stale_worker_writes(tmp_path):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    memory_mission.create_mission(
        mission_id="life-2",
        objective="Coordinate Life 2.0",
        definition_of_done=["restart-safe supervision"],
        supervisor_id="chad",
        db_path=db_path,
    )
    replaced = memory_mission.replace_supervisor(
        "life-2", new_supervisor_id="chad-2",
        expected_supervisor_id="chad", expected_epoch=1, db_path=db_path,
    )
    assert replaced["supervisor"] == {"id": "chad-2", "epoch": 2}

    with pytest.raises(memory_mission.MissionError, match="stale supervisor"):
        memory_mission.update_checkpoint(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            checkpoint={"verified": ["old worker"]}, db_path=db_path,
        )

    updated = memory_mission.update_checkpoint(
        "life-2", supervisor_id="chad-2", supervisor_epoch=2,
        checkpoint={"verified": ["research synthesis complete"]}, db_path=db_path,
    )
    assert updated["checkpoint"] == {"verified": ["research synthesis complete"]}


def _executing_life_mission(db_path):
    from gateway import memory_mission

    memory_mission.create_mission(
        mission_id="life-2", objective="Coordinate Life 2.0",
        definition_of_done=["bounded autonomous coordination"],
        supervisor_id="chad", db_path=db_path,
    )
    digest = "c" * 64
    memory_mission.set_plan(
        "life-2", plan_ref="plan://life-2/v1", plan_digest=digest, db_path=db_path
    )
    memory_mission.record_plan_review(
        "life-2", reviewer_id="independent-plan-verifier", plan_digest=digest,
        verdict="approved", db_path=db_path,
    )
    return memory_mission.begin_execution("life-2", db_path=db_path)


def test_mission_cycle_detects_changed_lane_then_stays_silent_on_no_change(tmp_path):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    decisions = []
    delegations = []
    notifications = []

    def decide(context):
        decisions.append(context)
        return {"outcome": "advance", "reason": "resource scout completed", "task": {"owner": "existing-action", "id": "synthesize-resources"}}

    def delegate(task):
        delegations.append(task)
        return {"ok": True, "receipt": "delegation:1"}

    observation = {"source": "research", "locator": "resource-scout", "digest": "result-v1", "observed_at": 1.0}
    first = context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[observation], decide=decide, delegate=delegate,
        notify=notifications.append, db_path=db_path,
    )
    second = context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[observation], decide=decide, delegate=delegate,
        notify=notifications.append, db_path=db_path,
    )

    assert first["outcome"] == "advance"
    assert first["delegation"] == {"ok": True, "receipt": "delegation:1"}
    assert second["outcome"] == "no_change"
    assert len(decisions) == 1
    assert len(delegations) == 1
    assert notifications == []
    reopened = memory_mission.get_mission("life-2", db_path=db_path)
    assert reopened["source_cursors"]["research|resource-scout"] == "result-v1"


def test_mission_cycle_dedupes_human_escalation_across_changed_inputs(tmp_path):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    notifications = []

    def needs_jacob(_context):
        return {
            "outcome": "needs_jacob",
            "reason": "A real-world outreach action needs Jacob's authorization",
            "escalation_key": "authorize:life2:outreach",
        }

    first = context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[{"source": "opportunities", "locator": "peer-support", "digest": "v1"}],
        decide=needs_jacob, notify=notifications.append, db_path=db_path,
    )
    second = context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[{"source": "opportunities", "locator": "peer-support", "digest": "v2"}],
        decide=needs_jacob, notify=notifications.append, db_path=db_path,
    )

    assert first["outcome"] == "needs_jacob"
    assert first["notified"] is True
    assert second["outcome"] == "needs_jacob"
    assert second["notified"] is False
    assert len(notifications) == 1
    reopened = memory_mission.get_mission("life-2", db_path=db_path)
    assert reopened["pending_escalation"]["key"] == "authorize:life2:outreach"


def test_mission_acceptance_is_independent_and_exact_candidate_bound(tmp_path):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    candidate_one = "d" * 64
    verifying = memory_mission.record_candidate(
        "life-2", candidate_ref="candidate://life-2/1",
        candidate_digest=candidate_one, db_path=db_path,
    )
    assert verifying["status"] == "VERIFYING"

    with pytest.raises(memory_mission.MissionError, match="independent"):
        memory_mission.record_acceptance(
            "life-2", reviewer_id="chad", candidate_digest=candidate_one,
            verdict="accepted", db_path=db_path,
        )
    rejected = memory_mission.record_acceptance(
        "life-2", reviewer_id="acceptance-verifier", candidate_digest=candidate_one,
        verdict="rejected", evidence={"defect": "resume gap"}, db_path=db_path,
    )
    assert rejected["status"] == "REPAIRING"

    candidate_two = "e" * 64
    repaired = memory_mission.record_candidate(
        "life-2", candidate_ref="candidate://life-2/2",
        candidate_digest=candidate_two, db_path=db_path,
    )
    assert repaired["acceptance"]["state"] == "unreviewed"
    with pytest.raises(memory_mission.MissionError, match="current candidate"):
        memory_mission.record_acceptance(
            "life-2", reviewer_id="acceptance-verifier", candidate_digest=candidate_one,
            verdict="accepted", db_path=db_path,
        )
    accepted = memory_mission.record_acceptance(
        "life-2", reviewer_id="acceptance-verifier", candidate_digest=candidate_two,
        verdict="accepted", evidence={"exact_candidate": True}, db_path=db_path,
    )
    assert accepted["status"] == "DONE"
    assert accepted["acceptance"]["state"] == "accepted"


def test_mission_pause_resume_and_stop_gate_autonomous_cycles(tmp_path):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    decisions = []

    paused = memory_mission.pause_mission("life-2", reason="Jacob paused it", db_path=db_path)
    assert paused["status"] == "PAUSED"
    paused_cycle = context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[{"source": "research", "locator": "lane", "digest": "v1"}],
        decide=lambda context: decisions.append(context) or {"outcome": "advance"},
        db_path=db_path,
    )
    assert paused_cycle == {"outcome": "paused", "reason": "Jacob paused it"}
    assert decisions == []

    resumed = memory_mission.resume_mission("life-2", db_path=db_path)
    assert resumed["status"] == "EXECUTING"
    stopped = memory_mission.stop_mission("life-2", reason="Mission stopped", db_path=db_path)
    assert stopped["status"] == "STOPPED"
    with pytest.raises(memory_mission.MissionError, match="stopped"):
        memory_mission.resume_mission("life-2", db_path=db_path)


def test_worker_report_is_preserved_without_becoming_verified_state(tmp_path):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    memory_mission.create_mission(
        mission_id="life-2",
        objective="Coordinate Life 2.0",
        definition_of_done=["truthful evidence"],
        supervisor_id="chad",
        db_path=db_path,
    )
    memory_mission.update_checkpoint(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        checkpoint={"verified_state": ["research artifact exists"]}, db_path=db_path,
    )
    updated = memory_mission.record_worker_report(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        worker_id="scout-2", report={"claim": "all resource scouting is complete"},
        evidence_locator="worker://scout-2/result-7", db_path=db_path,
    )

    assert updated["checkpoint"]["verified_state"] == ["research artifact exists"]
    assert updated["checkpoint"]["worker_reports"] == [
        {
            "worker_id": "scout-2",
            "report": {"claim": "all resource scouting is complete"},
            "evidence_locator": "worker://scout-2/result-7",
        }
    ]


def test_mission_cycle_persists_delegation_before_adapter_and_does_not_repeat_unknown_effect(tmp_path):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    calls = []
    observation = {
        "source": "research",
        "locator": "resource-scout",
        "digest": "result-v2",
    }

    def delegate(_task):
        calls.append("called")
        persisted = memory_mission.get_mission("life-2", db_path=db_path)
        assert persisted["source_cursors"]["research|resource-scout"] == "result-v2"
        assert persisted["last_cycle"]["delegation_state"] == "pending"
        raise RuntimeError("adapter lost its reply after the effect may have happened")
    first = context_mission.run_cycle(
        "life-2",
        supervisor_id="chad",
        supervisor_epoch=1,
        observations=[observation],
        decide=lambda _context: {
            "outcome": "advance",
            "reason": "advance changed research",
            "task": {"owner": "existing-action", "id": "synthesize-resources"},
        },
        delegate=delegate,
        db_path=db_path,
    )
    assert first["outcome"] == "blocked"
    assert first["delegation_state"] == "unknown"
    assert len(calls) == 1

    second = context_mission.run_cycle(
        "life-2",
        supervisor_id="chad",
        supervisor_epoch=1,
        observations=[observation],
        decide=lambda _context: (_ for _ in ()).throw(AssertionError("decision repeated")),
        delegate=lambda _task: calls.append("duplicate") or {"ok": True},
        db_path=db_path,
    )
    assert second["outcome"] == "blocked"
    assert "reconcile" in second["reason"].lower()
    assert calls == ["called"]


def test_plan_review_cannot_approve_a_plan_that_changed_after_read(tmp_path, monkeypatch):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    memory_mission.create_mission(
        mission_id="race-plan", objective="x", definition_of_done=["x"],
        supervisor_id="chad", db_path=db_path,
    )
    old_digest, new_digest = "a" * 64, "b" * 64
    memory_mission.set_plan(
        "race-plan", plan_ref="plan://old", plan_digest=old_digest, db_path=db_path
    )
    original_get = memory_mission.get_mission

    def interleaved_get(mission_id, *, db_path=memory_mission.MISSION_DB_FILE):
        snapshot = original_get(mission_id, db_path=db_path)
        monkeypatch.setattr(memory_mission, "get_mission", original_get)
        memory_mission.set_plan(
            mission_id, plan_ref="plan://new", plan_digest=new_digest, db_path=db_path
        )
        return snapshot
    monkeypatch.setattr(memory_mission, "get_mission", interleaved_get)
    with pytest.raises(memory_mission.MissionError, match="current plan"):
        memory_mission.record_plan_review(
            "race-plan", reviewer_id="reviewer", plan_digest=old_digest,
            verdict="approved", db_path=db_path,
        )
    current = original_get("race-plan", db_path=db_path)
    assert current["plan"]["digest"] == new_digest
    assert current["plan"]["review_state"] == "unreviewed"


def test_acceptance_cannot_accept_a_candidate_that_changed_after_read(tmp_path, monkeypatch):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    memory_mission.create_mission(
        mission_id="race-candidate", objective="x", definition_of_done=["x"],
        supervisor_id="chad", db_path=db_path,
    )
    old_digest, new_digest = "c" * 64, "d" * 64
    memory_mission.record_candidate(
        "race-candidate", candidate_ref="candidate://old",
        candidate_digest=old_digest, db_path=db_path,
    )
    original_get = memory_mission.get_mission

    def interleaved_get(mission_id, *, db_path=memory_mission.MISSION_DB_FILE):
        snapshot = original_get(mission_id, db_path=db_path)
        monkeypatch.setattr(memory_mission, "get_mission", original_get)
        memory_mission.record_candidate(
            mission_id, candidate_ref="candidate://new",
            candidate_digest=new_digest, db_path=db_path,
        )
        return snapshot
    monkeypatch.setattr(memory_mission, "get_mission", interleaved_get)
    with pytest.raises(memory_mission.MissionError, match="current candidate"):
        memory_mission.record_acceptance(
            "race-candidate", reviewer_id="reviewer",
            candidate_digest=old_digest, verdict="accepted", db_path=db_path,
        )
    current = original_get("race-candidate", db_path=db_path)
    assert current["candidate"]["digest"] == new_digest
    assert current["acceptance"]["state"] == "unreviewed"
    assert current["status"] == "VERIFYING"


def test_begin_execution_fails_if_plan_changes_after_gate_read(tmp_path, monkeypatch):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    memory_mission.create_mission(
        mission_id="race-exec", objective="x", definition_of_done=["x"],
        supervisor_id="chad", db_path=db_path,
    )
    old_digest, new_digest = "e" * 64, "f" * 64
    memory_mission.set_plan(
        "race-exec", plan_ref="plan://old", plan_digest=old_digest, db_path=db_path
    )
    memory_mission.record_plan_review(
        "race-exec", reviewer_id="reviewer", plan_digest=old_digest,
        verdict="approved", db_path=db_path,
    )
    original_get = memory_mission.get_mission

    def interleaved_get(mission_id, *, db_path=memory_mission.MISSION_DB_FILE):
        snapshot = original_get(mission_id, db_path=db_path)
        monkeypatch.setattr(memory_mission, "get_mission", original_get)
        memory_mission.set_plan(
            mission_id, plan_ref="plan://new", plan_digest=new_digest, db_path=db_path
        )
        return snapshot
    monkeypatch.setattr(memory_mission, "get_mission", interleaved_get)
    with pytest.raises(memory_mission.MissionError, match="approval changed"):
        memory_mission.begin_execution("race-exec", db_path=db_path)
    current = original_get("race-exec", db_path=db_path)
    assert current["plan"]["digest"] == new_digest
    assert current["plan"]["review_state"] == "unreviewed"
    assert current["status"] == "PLAN_REVIEW"


def test_stopped_mission_cannot_reenter_execution_via_begin_execution(tmp_path):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    memory_mission.stop_mission("life-2", reason="stop", db_path=db_path)
    with pytest.raises(memory_mission.MissionError, match="PLAN_REVIEW"):
        memory_mission.begin_execution("life-2", db_path=db_path)
    assert memory_mission.get_mission("life-2", db_path=db_path)["status"] == "STOPPED"


def test_resume_fails_if_approved_plan_changes_after_pause_read(tmp_path, monkeypatch):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    memory_mission.pause_mission("life-2", reason="pause", db_path=db_path)
    original_get = memory_mission.get_mission

    def interleaved_get(mission_id, *, db_path=memory_mission.MISSION_DB_FILE):
        snapshot = original_get(mission_id, db_path=db_path)
        monkeypatch.setattr(memory_mission, "get_mission", original_get)
        memory_mission.set_plan(
            mission_id, plan_ref="plan://replacement", plan_digest="9" * 64,
            db_path=db_path,
        )
        return snapshot
    monkeypatch.setattr(memory_mission, "get_mission", interleaved_get)
    with pytest.raises(memory_mission.MissionError, match="changed before resume"):
        memory_mission.resume_mission("life-2", db_path=db_path)
    current = original_get("life-2", db_path=db_path)
    assert current["status"] == "PLAN_REVIEW"
    assert current["plan"]["review_state"] == "unreviewed"


def test_stopped_mission_cannot_be_changed_back_to_paused(tmp_path):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    memory_mission.stop_mission("life-2", reason="stop", db_path=db_path)
    with pytest.raises(memory_mission.MissionError, match="stopped"):
        memory_mission.pause_mission("life-2", reason="pause", db_path=db_path)
    assert memory_mission.get_mission("life-2", db_path=db_path)["status"] == "STOPPED"


def test_plan_reviewer_cannot_become_supervisor_and_then_execute_same_plan(tmp_path):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    memory_mission.create_mission(
        mission_id="reviewer-supervisor", objective="x",
        definition_of_done=["independent plan gate"], supervisor_id="chad",
        db_path=db_path,
    )
    digest = "7" * 64
    memory_mission.set_plan(
        "reviewer-supervisor", plan_ref="plan://one", plan_digest=digest,
        db_path=db_path,
    )
    memory_mission.record_plan_review(
        "reviewer-supervisor", reviewer_id="reviewer", plan_digest=digest,
        verdict="approved", db_path=db_path,
    )
    memory_mission.replace_supervisor(
        "reviewer-supervisor", new_supervisor_id="reviewer",
        expected_supervisor_id="chad", expected_epoch=1, db_path=db_path,
    )
    with pytest.raises(memory_mission.MissionError, match="independent"):
        memory_mission.begin_execution("reviewer-supervisor", db_path=db_path)
    current = memory_mission.get_mission("reviewer-supervisor", db_path=db_path)
    assert current["status"] == "PLAN_REVIEW"


def test_plan_reviewer_cannot_become_supervisor_and_resume_same_plan(tmp_path):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    memory_mission.pause_mission("life-2", reason="pause", db_path=db_path)
    memory_mission.replace_supervisor(
        "life-2", new_supervisor_id="independent-plan-verifier",
        expected_supervisor_id="chad", expected_epoch=1, db_path=db_path,
    )
    with pytest.raises(memory_mission.MissionError, match="independent"):
        memory_mission.resume_mission("life-2", db_path=db_path)
    assert memory_mission.get_mission("life-2", db_path=db_path)["status"] == "PAUSED"


def test_stopped_mission_rejects_plan_candidate_checkpoint_and_cycle_mutations(tmp_path):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    memory_mission.create_mission(
        mission_id="stopped-boundary", objective="x", definition_of_done=["x"],
        supervisor_id="chad", db_path=db_path,
    )
    memory_mission.stop_mission("stopped-boundary", reason="stop", db_path=db_path)

    with pytest.raises(memory_mission.MissionError, match="stopped"):
        memory_mission.set_plan(
            "stopped-boundary", plan_ref="plan://later", plan_digest="1" * 64,
            db_path=db_path,
        )
    with pytest.raises(memory_mission.MissionError, match="stopped"):
        memory_mission.record_candidate(
            "stopped-boundary", candidate_ref="candidate://later",
            candidate_digest="2" * 64, db_path=db_path,
        )
    with pytest.raises(memory_mission.MissionError, match="stopped"):
        memory_mission.update_checkpoint(
            "stopped-boundary", supervisor_id="chad", supervisor_epoch=1,
            checkpoint={"late": True}, db_path=db_path,
        )
    with pytest.raises(memory_mission.MissionError, match="EXECUTING"):
        memory_mission.record_cycle(
            "stopped-boundary", supervisor_id="chad", supervisor_epoch=1,
            source_cursors={"source|locator": "digest"},
            cycle={"outcome": "no_change"}, db_path=db_path,
        )

    current = memory_mission.get_mission("stopped-boundary", db_path=db_path)
    assert current["status"] == "STOPPED"
    assert current["plan"]["digest"] is None
    assert current["candidate"]["digest"] is None
    assert current["checkpoint"] == {}
    assert current["last_cycle"] is None


@pytest.mark.asyncio
async def test_mission_cycle_composes_with_existing_automation_action_runner(tmp_path, monkeypatch):
    from gateway import (
        action_grants,
        automation_actions,
        automation_runs,
        context_mission,
        memory_mission,
    )

    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(automation_runs, "DB_FILE", db_path)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_path)
    automation_actions.clear_registry()
    _executing_life_mission(db_path)
    decisions = []
    delegations = []

    def observe(_payload):
        return [{"source": "research", "locator": "scout", "digest": "v1"}]

    def decide(context):
        decisions.append(context)
        return {
            "outcome": "advance",
            "reason": "new research",
            "task": {"owner": "existing-action", "id": "synthesize"},
        }

    def delegate(task):
        delegations.append(task)
        return {"ok": True, "receipt": "existing-action:1"}

    action = context_mission.build_automation_action(
        "life-2", observe=observe, decide=decide, delegate=delegate, db_path=db_path
    )
    automation_actions.register_action("mission.life2.cycle", action)

    first = await automation_actions.run_action(
        "mission.life2.cycle", trigger_kind="time",
        automation_id="mission:life-2", schedule_id="life2-schedule",
    )
    second = await automation_actions.run_action(
        "mission.life2.cycle", trigger_kind="time",
        automation_id="mission:life-2", schedule_id="life2-schedule",
    )

    assert first["status"] == "completed"
    assert first["result_pointer"] == "mission:life-2"
    assert second["status"] == "condition_false"
    assert len(decisions) == 1
    assert len(delegations) == 1
    mission = memory_mission.get_mission("life-2", db_path=db_path)
    assert mission["source_cursors"]["research|scout"] == "v1"
    automation_actions.clear_registry()


@pytest.mark.asyncio
async def test_mission_automation_action_resolves_current_supervisor_and_skips_paused_sources(
    tmp_path, monkeypatch
):
    from gateway import (
        action_grants,
        automation_actions,
        automation_runs,
        context_mission,
        memory_mission,
    )

    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(automation_runs, "DB_FILE", db_path)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_path)
    automation_actions.clear_registry()
    _executing_life_mission(db_path)
    observed = []

    def observe(_payload):
        observed.append("called")
        return [{"source": "research", "locator": "lane", "digest": "v2"}]

    action = context_mission.build_automation_action(
        "life-2", observe=observe,
        decide=lambda _context: {"outcome": "blocked", "reason": "proof"},
        db_path=db_path,
    )

    memory_mission.replace_supervisor(
        "life-2", new_supervisor_id="chad-2",
        expected_supervisor_id="chad", expected_epoch=1, db_path=db_path,
    )
    automation_actions.register_action("mission.life2.cycle", action)
    run = await automation_actions.run_action(
        "mission.life2.cycle", trigger_kind="time", automation_id="mission:life-2",
    )
    assert run["status"] == "completed"
    assert observed == ["called"]
    current = memory_mission.get_mission("life-2", db_path=db_path)
    assert current["supervisor"] == {"id": "chad-2", "epoch": 2}

    memory_mission.pause_mission("life-2", reason="pause", db_path=db_path)
    paused = await automation_actions.run_action(
        "mission.life2.cycle", trigger_kind="time", automation_id="mission:life-2",
    )
    assert paused["status"] == "condition_false"
    assert observed == ["called"]
    automation_actions.clear_registry()


@pytest.mark.asyncio
@pytest.mark.parametrize("transition", ["pause", "stop"])
async def test_mission_automation_action_maps_pause_stop_interleaving_to_condition_false(
    tmp_path, monkeypatch, transition
):
    from gateway import (
        action_grants,
        automation_actions,
        automation_runs,
        context_mission,
        memory_mission,
    )

    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(automation_runs, "DB_FILE", db_path)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_path)
    automation_actions.clear_registry()
    _executing_life_mission(db_path)
    decisions = []

    def observe(_payload):
        if transition == "pause":
            memory_mission.pause_mission("life-2", reason="interleaved pause", db_path=db_path)
        else:
            memory_mission.stop_mission("life-2", reason="interleaved stop", db_path=db_path)
        return [{"source": "research", "locator": "lane", "digest": "v2"}]

    action = context_mission.build_automation_action(
        "life-2", observe=observe,
        decide=lambda context: decisions.append(context) or {
            "outcome": "blocked", "reason": "must not run"
        },
        db_path=db_path,
    )
    automation_actions.register_action("mission.life2.cycle", action)

    run = await automation_actions.run_action(
        "mission.life2.cycle", trigger_kind="time", automation_id="mission:life-2",
    )

    assert run["status"] == "condition_false"
    assert run["error"] == f"interleaved {transition}"
    assert decisions == []
    current = memory_mission.get_mission("life-2", db_path=db_path)
    assert current["status"] == ("PAUSED" if transition == "pause" else "STOPPED")
    assert current["source_cursors"] == {}
    automation_actions.clear_registry()


@pytest.mark.asyncio
async def test_mission_automation_action_preserves_source_unavailable_as_run_evidence(
    tmp_path, monkeypatch
):
    from gateway import (
        action_grants,
        automation_actions,
        automation_runs,
        context_mission,
        memory_mission,
    )

    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(automation_runs, "DB_FILE", db_path)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_path)
    automation_actions.clear_registry()
    _executing_life_mission(db_path)

    def observe(_payload):
        raise automation_actions.SourceUnavailable("Life 2.0 source is offline")

    action = context_mission.build_automation_action(
        "life-2", observe=observe,
        decide=lambda _context: {"outcome": "blocked", "reason": "unused"},
        db_path=db_path,
    )
    automation_actions.register_action("mission.life2.cycle", action)
    run = await automation_actions.run_action(
        "mission.life2.cycle", trigger_kind="time", automation_id="mission:life-2",
    )

    assert run["status"] == "source_unavailable"
    assert run["error"] == "Life 2.0 source is offline"
    persisted = automation_runs.get_run(run["id"])
    assert persisted is not None
    assert persisted["status"] == "source_unavailable"
    mission = memory_mission.get_mission("life-2", db_path=db_path)
    assert mission["source_cursors"] == {}
    automation_actions.clear_registry()


def test_mission_global_thread_observation_is_locator_digest_not_copied_thread(
    tmp_path, monkeypatch
):
    from gateway import agent_workspace, context_mission

    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", db_path)
    root = agent_workspace.post_global_message(
        sender_id="dsh", content="Life 2.0 handoff v1", message_kind="handoff"
    )

    first = context_mission.observe_global_thread(root["id"])
    assert first["source"] == "workspace_global"
    assert first["locator"] == f"thread:{root['id']}"
    assert first["message_count"] == 1
    assert first["last_message_id"] == root["id"]
    assert "content" not in first
    assert "messages" not in first

    reply = agent_workspace.post_global_message(
        sender_id="codex", content="Independent evidence arrived", message_kind="result",
        parent_message_id=root["id"],
    )
    second = context_mission.observe_global_thread(reply["id"])
    assert second["locator"] == first["locator"]
    assert second["digest"] != first["digest"]
    assert second["message_count"] == 2
    assert second["last_message_id"] == reply["id"]

    agent_workspace.post_global_message(
        sender_id="dsh", content="unrelated room message", message_kind="status"
    )
    third = context_mission.observe_global_thread(root["id"])
    assert third == second


def test_mission_global_thread_observation_missing_locator_is_source_unavailable(tmp_path, monkeypatch):
    from gateway import agent_workspace, automation_actions, context_mission

    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", tmp_path / "kitty.db")
    with pytest.raises(automation_actions.SourceUnavailable, match="workspace_global thread"):
        context_mission.observe_global_thread("message_missing")


def test_mission_global_thread_observation_fails_closed_at_thread_cap(monkeypatch):
    from gateway import agent_workspace, automation_actions, context_mission

    rows = [
        {
            "id": f"message_{i}", "parent_message_id": None if i == 0 else "message_0",
            "sender_kind": "agent", "sender_id": "dsh", "recipient_id": None,
            "message_kind": "status", "content": "x", "created_at": float(i),
        }
        for i in range(500)
    ]
    monkeypatch.setattr(agent_workspace, "list_thread", lambda _message_id, limit=500: rows)
    with pytest.raises(automation_actions.SourceUnavailable, match="observation cap"):
        context_mission.observe_global_thread("message_0")


@pytest.mark.asyncio
async def test_mission_automation_wake_tracks_only_named_global_thread_changes(tmp_path, monkeypatch):
    from gateway import (
        action_grants,
        agent_workspace,
        automation_actions,
        automation_runs,
        context_mission,
        memory_mission,
    )
    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", db_path)
    monkeypatch.setattr(automation_runs, "DB_FILE", db_path)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_path)
    automation_actions.clear_registry()
    _executing_life_mission(db_path)
    root = agent_workspace.post_global_message(
        sender_id="dsh", content="Life 2.0 handoff", message_kind="handoff"
    )
    decisions = []

    def decide(context):
        decisions.append(context)
        return {"outcome": "blocked", "reason": "source change recorded for synthesis"}

    action = context_mission.build_automation_action(
        "life-2",
        observe=lambda _payload: [context_mission.observe_global_thread(root["id"])],
        decide=decide,
        db_path=db_path,
    )
    automation_actions.register_action("mission.life2.cycle", action)
    first = await automation_actions.run_action(
        "mission.life2.cycle", trigger_kind="time", automation_id="mission:life-2"
    )
    second = await automation_actions.run_action(
        "mission.life2.cycle", trigger_kind="time", automation_id="mission:life-2"
    )
    agent_workspace.post_global_message(
        sender_id="dsh", content="unrelated update", message_kind="status"
    )
    unrelated = await automation_actions.run_action(
        "mission.life2.cycle", trigger_kind="time", automation_id="mission:life-2"
    )
    reply = agent_workspace.post_global_message(
        sender_id="codex", content="new evidence", message_kind="result",
        parent_message_id=root["id"],
    )
    changed = await automation_actions.run_action(
        "mission.life2.cycle", trigger_kind="time", automation_id="mission:life-2"
    )

    assert [first["status"], second["status"], unrelated["status"], changed["status"]] == [
        "completed", "condition_false", "condition_false", "completed"
    ]
    assert len(decisions) == 2
    mission = memory_mission.get_mission("life-2", db_path=db_path)
    assert mission["source_cursors"][f"workspace_global|thread:{root['id']}"] == (
        context_mission.observe_global_thread(reply["id"])["digest"]
    )
    automation_actions.clear_registry()


def test_mission_reconciles_unknown_delegation_then_replaces_worker_same_task(tmp_path):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    observation = {"source": "research", "locator": "lane", "digest": "v1"}

    failed = context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[observation],
        decide=lambda _context: {
            "outcome": "advance", "reason": "delegate synthesis",
            "task": {"id": "task-1", "owner": "existing-action", "worker_id": "worker-a"},
        },
        delegate=lambda _task: (_ for _ in ()).throw(RuntimeError("lost reply")),
        db_path=db_path,
    )
    assert failed["delegation_state"] == "unknown"

    reconciled = context_mission.reconcile_delegation(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        outcome="failed_no_effect", evidence_locator="receipt://worker-a/no-effect",
        db_path=db_path,
    )
    assert reconciled["delegation_state"] == "retryable"
    assert reconciled["task"]["id"] == "task-1"

    memory_mission.replace_supervisor(
        "life-2", new_supervisor_id="chad-2",
        expected_supervisor_id="chad", expected_epoch=1, db_path=db_path,
    )
    calls = []
    replacement = context_mission.replace_delegation_worker(
        "life-2", supervisor_id="chad-2", supervisor_epoch=2,
        replacement_task={
            "id": "task-1", "owner": "existing-action", "worker_id": "worker-b"
        },
        delegate=lambda task: calls.append(task) or {"ok": True, "receipt": "worker-b:done"},
        db_path=db_path,
    )
    assert replacement["outcome"] == "advance"
    assert replacement["delegation_state"] == "completed"
    assert replacement["task"]["id"] == "task-1"
    assert replacement["task"]["worker_id"] == "worker-b"
    assert calls == [{"id": "task-1", "owner": "existing-action", "worker_id": "worker-b"}]
    mission = memory_mission.get_mission("life-2", db_path=db_path)
    assert mission["mission_id"] == "life-2"
    assert mission["supervisor"] == {"id": "chad-2", "epoch": 2}
    assert mission["source_cursors"]["research|lane"] == "v1"


def test_mission_replacement_worker_cannot_change_recovering_task_identity(tmp_path):
    from gateway import context_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[{"source": "research", "locator": "lane", "digest": "v1"}],
        decide=lambda _context: {
            "outcome": "advance", "reason": "delegate",
            "task": {"id": "task-1", "worker_id": "worker-a"},
        },
        delegate=lambda _task: (_ for _ in ()).throw(RuntimeError("unknown")),
        db_path=db_path,
    )
    context_mission.reconcile_delegation(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        outcome="failed_no_effect", evidence_locator="receipt://no-effect", db_path=db_path,
    )
    called = []
    with pytest.raises(context_mission.memory_mission.MissionError, match="task identity"):
        context_mission.replace_delegation_worker(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            replacement_task={"id": "task-2", "worker_id": "worker-b"},
            delegate=lambda task: called.append(task) or {"ok": True}, db_path=db_path,
        )
    assert called == []


def test_mission_reconciliation_completed_does_not_make_delegation_retryable(tmp_path):
    from gateway import context_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[{"source": "research", "locator": "lane", "digest": "v1"}],
        decide=lambda _context: {
            "outcome": "advance", "reason": "delegate",
            "task": {"id": "task-1", "worker_id": "worker-a"},
        },
        delegate=lambda _task: (_ for _ in ()).throw(RuntimeError("unknown")),
        db_path=db_path,
    )
    reconciled = context_mission.reconcile_delegation(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        outcome="completed", evidence_locator="receipt://effect-confirmed", db_path=db_path,
    )
    assert reconciled["delegation_state"] == "completed"
    with pytest.raises(context_mission.memory_mission.MissionError, match="retryable"):
        context_mission.replace_delegation_worker(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            replacement_task={"id": "task-1", "worker_id": "worker-b"},
            delegate=lambda _task: {"ok": True}, db_path=db_path,
        )


def test_mission_stale_reconciliation_cannot_overwrite_completed_effect(tmp_path, monkeypatch):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[{"source": "research", "locator": "lane", "digest": "v1"}],
        decide=lambda _context: {
            "outcome": "advance", "reason": "delegate",
            "task": {"id": "task-1", "worker_id": "worker-a"},
        },
        delegate=lambda _task: (_ for _ in ()).throw(RuntimeError("unknown")),
        db_path=db_path,
    )

    original_persist = context_mission._persist
    interleaved = False

    def race_persist(*args, **kwargs):
        nonlocal interleaved
        if not interleaved:
            interleaved = True
            context_mission.reconcile_delegation(
                "life-2", supervisor_id="chad", supervisor_epoch=1,
                outcome="completed", evidence_locator="receipt://completed", db_path=db_path,
            )
        return original_persist(*args, **kwargs)

    monkeypatch.setattr(context_mission, "_persist", race_persist)
    with pytest.raises(memory_mission.MissionError, match="delegation state changed"):
        context_mission.reconcile_delegation(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            outcome="failed_no_effect", evidence_locator="receipt://stale-no-effect",
            db_path=db_path,
        )

    current = memory_mission.get_mission("life-2", db_path=db_path)["last_cycle"]
    assert current["delegation_state"] == "completed"
    assert current["delegation_reconciliation"]["outcome"] == "completed"


def test_mission_competing_replacement_workers_dispatch_only_one(tmp_path, monkeypatch):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[{"source": "research", "locator": "lane", "digest": "v1"}],
        decide=lambda _context: {
            "outcome": "advance", "reason": "delegate",
            "task": {"id": "task-1", "worker_id": "worker-a"},
        },
        delegate=lambda _task: (_ for _ in ()).throw(RuntimeError("unknown")),
        db_path=db_path,
    )
    context_mission.reconcile_delegation(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        outcome="failed_no_effect", evidence_locator="receipt://no-effect", db_path=db_path,
    )
    original_persist = context_mission._persist
    interleaved = False
    calls: list[tuple[str, str]] = []

    def race_persist(*args, **kwargs):
        nonlocal interleaved
        if not interleaved:
            interleaved = True
            context_mission.replace_delegation_worker(
                "life-2", supervisor_id="chad", supervisor_epoch=1,
                replacement_task={"id": "task-1", "worker_id": "worker-c"},
                delegate=lambda task: calls.append(("nested", task["worker_id"]))
                or {"ok": True, "receipt": "worker-c:done"},
                db_path=db_path,
            )
        return original_persist(*args, **kwargs)

    monkeypatch.setattr(context_mission, "_persist", race_persist)
    with pytest.raises(memory_mission.MissionError, match="delegation state changed"):
        context_mission.replace_delegation_worker(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            replacement_task={"id": "task-1", "worker_id": "worker-b"},
            delegate=lambda task: calls.append(("outer", task["worker_id"]))
            or {"ok": True, "receipt": "worker-b:done"},
            db_path=db_path,
        )

    assert calls == [("nested", "worker-c")]
    current = memory_mission.get_mission("life-2", db_path=db_path)["last_cycle"]
    assert current["delegation_state"] == "completed"
    assert current["task"]["worker_id"] == "worker-c"

def test_mission_delegate_result_cannot_overwrite_concurrent_reconciliation(tmp_path):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)

    def delegate(_task):
        context_mission.reconcile_delegation(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            outcome="completed", evidence_locator="receipt://completed-during-call",
            db_path=db_path,
        )
        return {"ok": False, "error": "stale worker reply"}

    with pytest.raises(memory_mission.MissionError, match="delegation state changed"):
        context_mission.run_cycle(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            observations=[{"source": "research", "locator": "lane", "digest": "v1"}],
            decide=lambda _context: {
                "outcome": "advance", "reason": "delegate",
                "task": {"id": "task-1", "worker_id": "worker-a"},
            },
            delegate=delegate, db_path=db_path,
        )

    current = memory_mission.get_mission("life-2", db_path=db_path)["last_cycle"]
    assert current["delegation_state"] == "completed"
    assert current["delegation_reconciliation"]["evidence_locator"] == (
        "receipt://completed-during-call"
    )

def test_mission_replacement_result_cannot_overwrite_concurrent_reconciliation(tmp_path):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[{"source": "research", "locator": "lane", "digest": "v1"}],
        decide=lambda _context: {
            "outcome": "advance", "reason": "delegate",
            "task": {"id": "task-1", "worker_id": "worker-a"},
        },
        delegate=lambda _task: (_ for _ in ()).throw(RuntimeError("unknown")),
        db_path=db_path,
    )
    context_mission.reconcile_delegation(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        outcome="failed_no_effect", evidence_locator="receipt://no-effect", db_path=db_path,
    )

    def replacement_delegate(_task):
        context_mission.reconcile_delegation(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            outcome="completed", evidence_locator="receipt://replacement-completed",
            db_path=db_path,
        )
        return {"ok": False, "error": "stale replacement reply"}

    with pytest.raises(memory_mission.MissionError, match="delegation state changed"):
        context_mission.replace_delegation_worker(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            replacement_task={"id": "task-1", "worker_id": "worker-b"},
            delegate=replacement_delegate, db_path=db_path,
        )
    current = memory_mission.get_mission("life-2", db_path=db_path)["last_cycle"]
    assert current["delegation_state"] == "completed"
    assert current["task"]["worker_id"] == "worker-b"
    assert current["delegation_reconciliation"]["evidence_locator"] == (
        "receipt://replacement-completed"
    )


def test_concurrent_identical_jacob_escalation_notifies_at_most_once(tmp_path):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    decision_barrier = Barrier(2)
    notifications: list[str] = []

    def invoke_cycle():
        def decide(_context):
            decision_barrier.wait(timeout=5)
            return {
                "outcome": "needs_jacob",
                "reason": "authorization required",
                "escalation_key": "authorize:outreach",
            }

        try:
            return context_mission.run_cycle(
                "life-2", supervisor_id="chad", supervisor_epoch=1,
                observations=[
                    {"source": "research", "locator": "lane", "digest": "v1"}
                ],
                decide=decide,
                notify=lambda item: notifications.append(item["key"]),
                db_path=db_path,
            )
        except memory_mission.MissionError as exc:
            return {"conflict": str(exc)}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result() for future in [pool.submit(invoke_cycle) for _ in range(2)]]

    assert notifications == ["authorize:outreach"]
    assert sum(bool(result.get("notified")) for result in results) <= 1
    mission = memory_mission.get_mission("life-2", db_path=db_path)
    assert mission["pending_escalation"]["key"] == "authorize:outreach"


def test_concurrent_source_cursor_updates_cannot_be_silently_lost(tmp_path):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    decision_barrier = Barrier(2)
    observations = [
        {"source": "research", "locator": "lane", "digest": "r1"},
        {"source": "resources", "locator": "lane", "digest": "o1"},
    ]

    def invoke_cycle(observation):
        def decide(_context):
            decision_barrier.wait(timeout=5)
            return {"outcome": "blocked", "reason": "record changed lane only"}

        try:
            context_mission.run_cycle(
                "life-2", supervisor_id="chad", supervisor_epoch=1,
                observations=[observation], decide=decide, db_path=db_path,
            )
            return "ok"
        except memory_mission.MissionError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(invoke_cycle, observations))

    first = memory_mission.get_mission("life-2", db_path=db_path)
    expected = {"research|lane": "r1", "resources|lane": "o1"}
    if first["source_cursors"] != expected:
        assert "conflict" in statuses, "a lost cursor must never be reported as successful"
        missing = [
            observation
            for observation in observations
            if first["source_cursors"].get(
                f"{observation['source']}|{observation['locator']}"
            ) != observation["digest"]
        ]
        for observation in missing:
            context_mission.run_cycle(
                "life-2", supervisor_id="chad", supervisor_epoch=1,
                observations=[observation],
                decide=lambda _context: {
                    "outcome": "blocked", "reason": "retry conflicted lane"
                },
                db_path=db_path,
            )

    final = memory_mission.get_mission("life-2", db_path=db_path)
    assert final["source_cursors"] == expected



def test_mission_notification_delivery_preserves_newer_committed_cycle(tmp_path):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)

    def notify(_item):
        nested = context_mission.run_cycle(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            observations=[{"source": "research", "locator": "lane", "digest": "v1"}],
            decide=lambda _context: (_ for _ in ()).throw(
                AssertionError("unchanged source must not re-decide")
            ),
            db_path=db_path,
        )
        assert nested["outcome"] == "no_change"

    result = context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[{"source": "research", "locator": "lane", "digest": "v1"}],
        decide=lambda _context: {
            "outcome": "needs_jacob", "reason": "authorization required",
            "escalation_key": "authorize:outreach",
        },
        notify=notify, db_path=db_path,
    )

    assert result["notified"] is True
    current = memory_mission.get_mission("life-2", db_path=db_path)
    assert current["last_cycle"]["outcome"] == "no_change"
    assert current["pending_escalation"]["notification_state"] == "delivered"


def test_mission_notification_delivery_fences_reverse_stale_writer(tmp_path):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[{"source": "research", "locator": "lane", "digest": "v1"}],
        decide=lambda _context: {
            "outcome": "needs_jacob", "reason": "authorization required",
            "escalation_key": "authorize:outreach",
        },
        db_path=db_path,
    )
    stale = memory_mission.get_mission("life-2", db_path=db_path)
    delivered_cycle = dict(stale["last_cycle"])
    delivered_cycle["notified"] = True

    memory_mission.record_notification_delivery(
        "life-2",
        escalation_key="authorize:outreach",
        expected_pending_escalation=stale["pending_escalation"],
        expected_last_cycle=stale["last_cycle"],
        delivered_cycle=delivered_cycle,
        db_path=db_path,
    )

    with pytest.raises(memory_mission.MissionError, match="cycle state"):
        memory_mission.record_cycle(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            source_cursors=stale["source_cursors"],
            cycle={"outcome": "no_change", "reason": "stale", "changed": []},
            pending_escalation=stale["pending_escalation"],
            expected_last_cycle=stale["last_cycle"], db_path=db_path,
        )
    current = memory_mission.get_mission("life-2", db_path=db_path)
    assert current["pending_escalation"]["notification_state"] == "delivered"


@pytest.mark.parametrize("control", ["pause", "stop", "replace"])
def test_mission_notification_receipt_survives_control_state_change(tmp_path, control):
    from gateway import context_mission, memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)

    def notify(_item):
        if control == "pause":
            memory_mission.pause_mission("life-2", reason="pause during delivery", db_path=db_path)
        elif control == "stop":
            memory_mission.stop_mission("life-2", reason="stop during delivery", db_path=db_path)
        else:
            memory_mission.replace_supervisor(
                "life-2", new_supervisor_id="replacement-supervisor",
                expected_supervisor_id="chad", expected_epoch=1, db_path=db_path,
            )

    result = context_mission.run_cycle(
        "life-2", supervisor_id="chad", supervisor_epoch=1,
        observations=[{"source": "research", "locator": "lane", "digest": "v1"}],
        decide=lambda _context: {
            "outcome": "needs_jacob", "reason": "authorization required",
            "escalation_key": "authorize:outreach",
        },
        notify=notify, db_path=db_path,
    )
    assert result["notified"] is True
    current = memory_mission.get_mission("life-2", db_path=db_path)
    assert current["pending_escalation"]["notification_state"] == "delivered"
    if control == "pause":
        assert current["status"] == "PAUSED"
        assert current["supervisor"] == {"id": "chad", "epoch": 1}
    elif control == "stop":
        assert current["status"] == "STOPPED"
        assert current["supervisor"] == {"id": "chad", "epoch": 1}
    else:
        assert current["status"] == "EXECUTING"
        assert current["supervisor"] == {"id": "replacement-supervisor", "epoch": 2}


def test_mission_verifying_pause_resume_returns_to_verifying(tmp_path):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    digest = "a" * 64
    memory_mission.record_candidate(
        "life-2", candidate_ref="candidate://life-2/final",
        candidate_digest=digest, db_path=db_path,
    )
    paused = memory_mission.pause_mission(
        "life-2", reason="pause while verifying", db_path=db_path
    )
    assert paused["status"] == "PAUSED"

    resumed = memory_mission.resume_mission("life-2", db_path=db_path)
    assert resumed["status"] == "VERIFYING"
    assert resumed["acceptance"]["state"] == "unreviewed"
    with pytest.raises(memory_mission.MissionError, match="EXECUTING"):
        memory_mission.record_cycle(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            source_cursors={}, cycle={"outcome": "no_change"}, db_path=db_path,
        )
    accepted = memory_mission.record_acceptance(
        "life-2", reviewer_id="acceptance-verifier", candidate_digest=digest,
        verdict="accepted", db_path=db_path,
    )
    assert accepted["status"] == "DONE"


def test_mission_active_plan_reviewer_cannot_replace_executing_supervisor(tmp_path):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    with pytest.raises(memory_mission.MissionError, match="independent"):
        memory_mission.replace_supervisor(
            "life-2", new_supervisor_id="independent-plan-verifier",
            expected_supervisor_id="chad", expected_epoch=1, db_path=db_path,
        )
    current = memory_mission.get_mission("life-2", db_path=db_path)
    assert current["status"] == "EXECUTING"
    assert current["supervisor"] == {"id": "chad", "epoch": 1}

def test_concurrent_worker_reports_are_accumulated_without_loss(tmp_path, monkeypatch):
    from gateway import memory_mission

    db_path = tmp_path / "kitty.db"
    _executing_life_mission(db_path)
    read_barrier = Barrier(2)
    original_assert_supervisor = memory_mission.assert_supervisor

    def synchronized_assert(*args, **kwargs):
        mission = original_assert_supervisor(*args, **kwargs)
        read_barrier.wait(timeout=5)
        return mission

    monkeypatch.setattr(memory_mission, "assert_supervisor", synchronized_assert)

    def record(worker_id):
        return memory_mission.record_worker_report(
            "life-2", supervisor_id="chad", supervisor_epoch=1,
            worker_id=worker_id, report={"claim": f"{worker_id} complete"},
            evidence_locator=f"worker://{worker_id}/result", db_path=db_path,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        [future.result() for future in [pool.submit(record, "worker-a"), pool.submit(record, "worker-b")]]

    mission = memory_mission.get_mission("life-2", db_path=db_path)
    reports = mission["checkpoint"]["worker_reports"]
    assert sorted(report["worker_id"] for report in reports) == ["worker-a", "worker-b"]
