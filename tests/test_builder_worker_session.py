"""Tests for gateway/builder_worker_session.py — contract types and taxonomy."""

from __future__ import annotations

from gateway.builder_worker_session import (
    ModelPolicy,
    SessionIdentity,
    WorkerEvent,
    WorkerEventType,
    WorkerSession,
    WorkerSessionError,
    WorkerSessionNotFoundError,
    WorkerSnapshot,
    WorkerState,
)


class TestWorkerEventType:
    def test_all_event_types_exist(self) -> None:
        """The taxonomy covers the canonical lifecycle."""
        expected = {
            WorkerEventType.SESSION_STARTED,
            WorkerEventType.SESSION_RESUMED,
            WorkerEventType.BRIEF_DELIVERED,
            WorkerEventType.INSTRUCTION_SENT,
            WorkerEventType.TEXT_DELTA,
            WorkerEventType.MESSAGE_COMPLETE,
            WorkerEventType.TOOL_START,
            WorkerEventType.TOOL_END,
            WorkerEventType.COMMAND_START,
            WorkerEventType.COMMAND_END,
            WorkerEventType.FILE_CHANGE,
            WorkerEventType.COMMIT,
            WorkerEventType.MODEL_SWITCH,
            WorkerEventType.PROVIDER_SWITCH,
            WorkerEventType.USAGE,
            WorkerEventType.ATTENTION_REQUEST,
            WorkerEventType.PERMISSION_REQUEST,
            WorkerEventType.HEARTBEAT,
            WorkerEventType.IDLE,
            WorkerEventType.ERROR,
            WorkerEventType.CANCELLED,
            WorkerEventType.SESSION_ENDED,
            WorkerEventType.RAW,
        }
        actual = set(WorkerEventType)
        assert actual == expected, f"missing: {expected - actual}, extra: {actual - expected}"

    def test_enum_is_str_enum(self) -> None:
        """WorkerEventType values are strings for JSON serialisation."""
        for member in WorkerEventType:
            assert isinstance(member.value, str)
            assert member.value == str(member)


class TestWorkerState:
    def test_all_states_exist(self) -> None:
        expected = {
            WorkerState.STARTING,
            WorkerState.RUNNING,
            WorkerState.IDLE,
            WorkerState.COMPLETED,
            WorkerState.CANCELLED,
            WorkerState.FAILED,
            WorkerState.DISPOSED,
        }
        assert set(WorkerState) == expected


class TestSessionIdentity:
    def test_frozen_dataclass(self) -> None:
        identity = SessionIdentity(session_id="abc", backend="shell")
        assert identity.session_id == "abc"
        assert identity.backend == "shell"
        assert identity.created_at > 0

        # Frozen — assignment should raise
        try:
            identity.session_id = "xyz"
            assert False, "expected FrozenInstanceError"
        except Exception:
            pass


class TestWorkerEvent:
    def test_defaults(self) -> None:
        event = WorkerEvent(event_id="ev1", seq=0)
        assert event.event_id == "ev1"
        assert event.seq == 0
        assert event.type == WorkerEventType.RAW
        assert event.data == {}
        assert event.raw_payload is None

    def test_full_constructor(self) -> None:
        event = WorkerEvent(
            event_id="ev2",
            seq=5,
            timestamp=100.0,
            session_id="s1",
            packet_id="p1",
            attempt_id="a1",
            type=WorkerEventType.TEXT_DELTA,
            data={"text": "hello"},
            raw_payload={"raw": True},
        )
        assert event.event_id == "ev2"
        assert event.seq == 5
        assert event.type == WorkerEventType.TEXT_DELTA
        assert event.data["text"] == "hello"
        assert event.raw_payload == {"raw": True}


class TestWorkerSnapshot:
    def test_defaults(self) -> None:
        snap = WorkerSnapshot()
        assert snap.state == WorkerState.STARTING
        assert snap.model is None
        assert snap.provider is None
        assert snap.events_count == 0
        assert snap.changed_paths == []
        assert snap.scope_violations == []
        assert snap.learnings == []
        assert snap.decisions == []
        assert snap.issues == []

    def test_full_constructor(self) -> None:
        snap = WorkerSnapshot(
            session_id="s1",
            packet_id="p1",
            attempt_id="a1",
            state=WorkerState.COMPLETED,
            model="deepseek-v4",
            provider="openrouter",
            events_count=42,
            last_activity=12345.0,
            changed_paths=["src/app.py"],
            scope_violations=[],
            learnings=["use dataclass for contracts"],
            decisions=["adopt OpenCode server API"],
            issues=[],
            error=None,
            metadata={"exit_code": 0},
        )
        assert snap.state == WorkerState.COMPLETED
        assert snap.learnings == ["use dataclass for contracts"]


class TestModelPolicy:
    def test_defaults(self) -> None:
        policy = ModelPolicy()
        assert policy.model is None
        assert policy.provider is None
        assert policy.free_only is False
        assert policy.fallback_models == []

    def test_full(self) -> None:
        policy = ModelPolicy(
            model="deepseek-v4",
            provider="openrouter",
            free_only=True,
            fallback_models=["mimo-v2.5", "nemotron-3"],
        )
        assert policy.model == "deepseek-v4"
        assert policy.fallback_models == ["mimo-v2.5", "nemotron-3"]


class TestWorkerSessionAbstract:
    def test_cannot_instantiate(self) -> None:
        try:
            WorkerSession()  # type: ignore[abstract]
            assert False, "expected TypeError"
        except TypeError:
            pass

    def test_concrete_subclass_must_implement_all(self) -> None:
        class Partial(WorkerSession):
            def start(self, worktree, brief, model_policy=None, *, packet_id="", attempt_id=""):
                return SessionIdentity(session_id="1", backend="test")

            # Missing: resume, send_instruction, events, snapshot, cancel,
            # transcript, dispose, is_alive

        try:
            Partial()  # type: ignore[abstract]
            assert False, "expected TypeError for missing abstract methods"
        except TypeError:
            pass


class TestWorkerSessionErrors:
    def test_error_hierarchy(self) -> None:
        assert issubclass(WorkerSessionError, Exception)
        assert issubclass(WorkerSessionNotFoundError, WorkerSessionError)
        assert issubclass(WorkerSessionNotFoundError, Exception)

    def test_not_found_message(self) -> None:
        err = WorkerSessionNotFoundError("session abc gone")
        assert "abc" in str(err)
        assert "gone" in str(err)
