"""Canonical Builder worker event and runtime-state vocabulary.

The abandoned WorkerSession backend abstraction was removed; production worker
execution is owned directly by builder_runner/builder_runtime. This module keeps
only the shared event/state types consumed by the cockpit and runtime projection.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any


class WorkerEventType(enum.StrEnum):
    """Normalised lifecycle/event types emitted to Builder observers."""

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
    RAW = "raw"


@dataclass
class WorkerEvent:
    """One normalised worker event for replay/cockpit delivery."""

    event_id: str
    seq: int
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""
    packet_id: str = ""
    attempt_id: str = ""
    type: WorkerEventType = WorkerEventType.RAW
    data: dict[str, Any] = field(default_factory=dict)
    raw_payload: Any = None


class WorkerState(enum.StrEnum):
    """Runtime projection states used by Builder status/cockpit surfaces."""

    STARTING = "starting"
    RUNNING = "running"
    IDLE = "idle"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    DISPOSED = "disposed"
