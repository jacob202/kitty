"""Backend-neutral worker-session contract for KittyBuilder.

Defines the ``WorkerSession`` abstract interface that every worker backend
implements, plus the canonical event taxonomy and snapshot shape.

KB-BRAIN-01: the first production adapter is ``OpenCodeServerSession``;
``ShellWorkerSession`` wraps the existing subprocess runner as a compatibility
fallback. Neither backend may create Kitty tasks, choose packets, mutate
queue state, or manage worktrees — the session boundary stops at worker
lifecycle and event delivery.

References:
  docs/research/kittybuilder-brain-v1-harvest.md — Canonical WorkerSession
    contract and event taxonomy.
"""

from __future__ import annotations

import abc
import enum
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Session identity — returned by start / resume, passed back to every other
# method so the adapter can route without binding process-local state.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SessionIdentity:
    """Opaque handle for a running worker session.

    Backends may subclass this to carry their own routing data (PID, server
    URL, session UUID), but callers must treat it as an opaque token and pass
    it back only to the backend that produced it.
    """

    session_id: str
    backend: str
    created_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Event taxonomy
# ---------------------------------------------------------------------------


class WorkerEventType(enum.StrEnum):
    """Every event a worker session may emit.

    Events are ordered by logical phase, not alphabetically.
    """

    SESSION_STARTED = "session_started"
    SESSION_RESUMED = "session_resumed"
    BRIEF_DELIVERED = "brief_delivered"
    INSTRUCTION_SENT = "instruction_sent"

    TEXT_DELTA = "text_delta"
    MESSAGE_COMPLETE = "message_complete"

    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    COMMAND_START = "command_start"
    COMMAND_END = "command_end"

    FILE_CHANGE = "file_change"
    COMMIT = "commit"

    MODEL_SWITCH = "model_switch"
    PROVIDER_SWITCH = "provider_switch"
    USAGE = "usage"

    ATTENTION_REQUEST = "attention_request"
    PERMISSION_REQUEST = "permission_request"

    HEARTBEAT = "heartbeat"
    IDLE = "idle"

    ERROR = "error"
    CANCELLED = "cancelled"
    SESSION_ENDED = "session_ended"

    # Raw backend payload for debugging — never parsed structurally by Kitty.
    RAW = "raw"


@dataclass
class WorkerEvent:
    """One event from a worker session.

    A stable ``event_id`` and monotonically increasing ``seq`` allow cursor-
    based replay (KB-BRAIN-03). Backends emit richer events; Kitty normalises
    into this shape and discards nothing.
    """

    event_id: str
    seq: int
    timestamp: float = field(default_factory=time.time)

    session_id: str = ""
    packet_id: str = ""
    attempt_id: str = ""

    type: WorkerEventType = WorkerEventType.RAW
    data: dict[str, Any] = field(default_factory=dict)

    # Backend payload preserved unmodified so every integration-surface byte
    # is available for debugging. Never used for control flow.
    raw_payload: Any = None


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


class WorkerState(enum.StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    IDLE = "idle"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    DISPOSED = "disposed"


@dataclass
class WorkerSnapshot:
    """Point-in-time picture of a worker session.

    This is a read model — never written back to the backend. It exists so the
    cockpit can render worker state without polling every event.
    """

    session_id: str = ""
    packet_id: str = ""
    attempt_id: str = ""

    state: WorkerState = WorkerState.STARTING
    model: str | None = None
    provider: str | None = None

    events_count: int = 0
    last_activity: float = 0.0

    changed_paths: list[str] = field(default_factory=list)
    scope_violations: list[str] = field(default_factory=list)

    # Structured evidence block for cross-compaction persistence (oh-my-
    # claudecode pattern). Three categories mirror what workers produce.
    learnings: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Model policy
# ---------------------------------------------------------------------------


@dataclass
class ModelPolicy:
    """What model/provider the loop wants the session to use."""

    model: str | None = None
    provider: str | None = None
    free_only: bool = False
    fallback_models: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Abstract contract
# ---------------------------------------------------------------------------


class WorkerSession(abc.ABC):
    """Backend-neutral interface for a single worker run.

    One session = one packet execution. The session owns the worker process
    (or API connection); the loop owns task state, lease, worktree, scope
    checking, and finalisation.

    Every method receives ``identity`` so the adapter can remain stateless
    across loop restarts — a loop crash can ``resume`` an orphaned session
    without rebuilding backend state.
    """

    @abc.abstractmethod
    def start(
        self,
        worktree: Path,
        brief: str,
        model_policy: ModelPolicy | None = None,
        *,
        packet_id: str = "",
        attempt_id: str = "",
    ) -> SessionIdentity:
        """Create a new session and deliver the initial brief.

        Must be idempotent — calling ``start`` on an already-started session
        is a no-op that returns the existing identity.
        """
        ...

    @abc.abstractmethod
    def resume(self, identity: SessionIdentity) -> SessionIdentity:
        """Reconnect to an orphaned session.

        Returns the same identity if the session is still alive, or a new
        identity if the backend restarted and the old one is unreachable.
        Raises ``WorkerSessionError`` if the session cannot be recovered.
        """
        ...

    @abc.abstractmethod
    def send_instruction(self, identity: SessionIdentity, text: str) -> None:
        """Deliver a follow-up instruction to a running session."""
        ...

    @abc.abstractmethod
    def events(
        self,
        identity: SessionIdentity,
        *,
        cursor: int | None = None,
    ) -> list[WorkerEvent]:
        """Return events since *cursor* (inclusive).

        When *cursor* is ``None``, return all events from the start.
        An empty list means no new events — not that the session is done.
        """
        ...

    @abc.abstractmethod
    def snapshot(self, identity: SessionIdentity) -> WorkerSnapshot:
        """Return a point-in-time snapshot of the session."""
        ...

    @abc.abstractmethod
    def cancel(self, identity: SessionIdentity, *, reason: str = "") -> None:
        """Request cancellation. Non-blocking — the session may finish
        in-progress work before stopping."""
        ...

    @abc.abstractmethod
    def transcript(self, identity: SessionIdentity) -> Path | None:
        """Return a file-system path to the full transcript / combined log.

        ``None`` means no transcript is available (e.g. the backend
        streams events but does not persist a log).
        """
        ...

    @abc.abstractmethod
    def dispose(self, identity: SessionIdentity) -> None:
        """Release backend resources for this session.

        After ``dispose``, the identity is invalid and must not be reused.
        Idempotent — calling twice is a no-op.
        """
        ...

    @abc.abstractmethod
    def is_alive(self, identity: SessionIdentity) -> bool:
        """True when the backend process/connection is still reachable."""
        ...


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WorkerSessionError(Exception):
    """A worker session operation failed at the backend level."""


class WorkerSessionNotFoundError(WorkerSessionError):
    """The session identity refers to a session that no longer exists."""


class WorkerSessionTimeoutError(WorkerSessionError):
    """The session did not respond within the expected window."""
