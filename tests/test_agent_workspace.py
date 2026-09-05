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
