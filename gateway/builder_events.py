"""Structured live event stream for the Builder cockpit.

Extends the bare ``SSEBroadcaster`` with cursor-based replay, a bounded
ring buffer, and gap detection for slow clients. Normalises WorkerSession
events and Builder queue events into one versioned envelope.

KB-BRAIN-03: exposes replayable events without polling combined.log.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from typing import Any, AsyncGenerator

from gateway.builder_worker_session import WorkerEvent

logger = logging.getLogger("kitty.builder_events")

EVENT_SCHEMA_VERSION = 1
DEFAULT_RETENTION = 500          # max events kept in ring buffer
DEFAULT_HEARTBEAT_SECONDS = 15.0  # SSE keepalive
GAP_SIGNAL = "gap"


class BuilderEventEnvelope:
    """Versioned envelope for every streamed event."""

    __slots__ = (
        "event_id",
        "seq",
        "timestamp",
        "initiative_id",
        "packet_id",
        "attempt_id",
        "session_id",
        "type",
        "payload",
        "raw_log_ref",
    )

    def __init__(
        self,
        *,
        event_id: str = "",
        seq: int = 0,
        timestamp: float | None = None,
        initiative_id: str = "",
        packet_id: str = "",
        attempt_id: str = "",
        session_id: str = "",
        type: str = "",
        payload: dict[str, Any] | None = None,
        raw_log_ref: str | None = None,
    ):
        self.event_id = event_id
        self.seq = seq
        self.timestamp = timestamp or time.time()
        self.initiative_id = initiative_id
        self.packet_id = packet_id
        self.attempt_id = attempt_id
        self.session_id = session_id
        self.type = type
        self.payload = payload or {}
        self.raw_log_ref = raw_log_ref

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "event_id": self.event_id,
            "seq": self.seq,
            "timestamp": self.timestamp,
            "initiative_id": self.initiative_id,
            "packet_id": self.packet_id,
            "attempt_id": self.attempt_id,
            "session_id": self.session_id,
            "type": self.type,
            "payload": self.payload,
        }
        if self.raw_log_ref:
            result["raw_log_ref"] = self.raw_log_ref
        return result

    def to_sse(self) -> str:
        return f"id: {self.seq}\ndata: {json.dumps(self.to_dict(), default=str)}\n\n"

    @classmethod
    def from_worker_event(
        cls,
        event: WorkerEvent,
        *,
        seq: int,
        initiative_id: str = "",
        packet_id: str = "",
        attempt_id: str = "",
    ) -> "BuilderEventEnvelope":
        return cls(
            event_id=event.event_id,
            seq=seq,
            timestamp=event.timestamp,
            initiative_id=initiative_id,
            packet_id=packet_id,
            attempt_id=attempt_id,
            session_id=event.session_id,
            type=str(event.type),
            payload=event.data,
            raw_log_ref=None,
        )

    @classmethod
    def from_queue_event(
        cls,
        event: dict[str, Any],
        *,
        seq: int,
        task_id: str = "",
        initiative_id: str = "",
        packet_id: str = "",
        attempt_id: str = "",
        session_id: str = "",
    ) -> "BuilderEventEnvelope":
        return cls(
            event_id=f"queue:{event.get('id', '')}",
            seq=seq,
            timestamp=event.get("created_at", time.time()),
            initiative_id=initiative_id,
            packet_id=packet_id,
            attempt_id=attempt_id,
            session_id=session_id,
            type=f"queue.{event.get('type', 'unknown')}",
            payload={
                k: v
                for k, v in event.items()
                if k not in ("id", "type", "created_at")
            },
        )


class BuilderEventBroadcaster:
    """SSE broadcaster with replay buffer and cursor-based reconnect.

    Differences from the bare ``SSEBroadcaster``:
    - Every event carries a monotonically increasing ``seq`` for cursor replay.
    - A bounded ring buffer retains the last *retention* events so reconnecting
      clients can catch up without missing history.
    - When a client's cursor falls behind the oldest retained event, it
      receives an explicit ``gap`` signal rather than silently skipping data.
    - Broadcast is non-blocking: a slow client receives the gap signal and the
      broadcaster keeps emitting without waiting.
    """

    def __init__(self, *, retention: int = DEFAULT_RETENTION):
        self._retention = retention
        self._buffer: deque[BuilderEventEnvelope] = deque(maxlen=retention)
        self._seq = 0
        self._queues: dict[str, asyncio.Queue[str | None]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def subscribe(
        self,
        session_id: str,
        *,
        cursor: int | None = None,
        packet_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Subscribe to the event stream.

        - *cursor*: replay events with seq >= cursor. If cursor is behind the
          oldest retained event, a gap signal is sent first.
        - *packet_id*: when set, only events matching this packet are delivered.
        """
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

        # Clean up old connection for the same session.
        if session_id in self._queues:
            try:
                self._queues[session_id].put_nowait(None)
            except Exception:
                logger.warning(
                    "BuilderEventBroadcaster: failed to clean up old queue for %s",
                    session_id,
                )

        q: asyncio.Queue[str | None] = asyncio.Queue()
        self._queues[session_id] = q

        try:
            # -- Replay buffered events -----------------------------------
            if cursor is not None:
                delivered = 0
                # Signal gap if the client missed events that left the buffer.
                if cursor < self._oldest_seq():
                    yield self._gap_message(cursor, self._oldest_seq())
                for envelope in self._buffer:
                    if envelope.seq < cursor:
                        continue
                    if packet_id and envelope.packet_id != packet_id:
                        continue
                    yield envelope.to_sse()
                    delivered += 1
            else:
                # No cursor: deliver the latest event only as a snapshot.
                if self._buffer:
                    envelope = self._buffer[-1]
                    if not packet_id or envelope.packet_id == packet_id:
                        yield envelope.to_sse()

            # -- Live stream ----------------------------------------------
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    msg = await asyncio.wait_for(
                        q.get(), timeout=DEFAULT_HEARTBEAT_SECONDS
                    )
                    if msg is None:
                        break  # Replaced by a newer connection.
                    if packet_id:
                        # Filter on the fly — envelope has packet_id in its data.
                        try:
                            parsed = json.loads(msg)
                            if parsed.get("packet_id") != packet_id:
                                continue
                        except json.JSONDecodeError:
                            pass
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if self._queues.get(session_id) is q:
                del self._queues[session_id]

    def broadcast(self, envelope: BuilderEventEnvelope) -> None:
        """Thread-safe broadcast to all connected SSE clients."""
        self._seq += 1
        envelope.seq = self._seq
        # Ensure event_id is set.
        if not envelope.event_id:
            envelope.event_id = f"evt:{self._seq}"
        self._buffer.append(envelope)

        msg = json.dumps(envelope.to_dict(), default=str)
        if not self._queues or self._loop is None:
            return

        for q in list(self._queues.values()):
            try:
                self._loop.call_soon_threadsafe(q.put_nowait, msg)
            except Exception as exc:
                logger.error("BuilderEventBroadcaster broadcast error: %s", exc)

    def emit_worker_event(
        self,
        event: WorkerEvent,
        *,
        initiative_id: str = "",
        packet_id: str = "",
        attempt_id: str = "",
    ) -> None:
        """Convenience: emit a WorkerEvent as a BuilderEventEnvelope."""
        envelope = BuilderEventEnvelope.from_worker_event(
            event,
            seq=0,  # will be set by broadcast()
            initiative_id=initiative_id,
            packet_id=packet_id,
            attempt_id=attempt_id,
        )
        self.broadcast(envelope)

    def emit_queue_event(
        self,
        event: dict[str, Any],
        *,
        task_id: str = "",
        initiative_id: str = "",
        packet_id: str = "",
        attempt_id: str = "",
        session_id: str = "",
    ) -> None:
        """Convenience: emit a Builder queue event as a BuilderEventEnvelope."""
        envelope = BuilderEventEnvelope.from_queue_event(
            event,
            seq=0,
            task_id=task_id,
            initiative_id=initiative_id,
            packet_id=packet_id,
            attempt_id=attempt_id,
            session_id=session_id,
        )
        self.broadcast(envelope)

    def emit_gap(self, *, reason: str = "buffer overflow") -> None:
        """Emit an explicit gap signal."""
        envelope = BuilderEventEnvelope(
            event_id=f"gap:{self._seq + 1}",
            type=GAP_SIGNAL,
            payload={"reason": reason, "oldest_retained_seq": self._oldest_seq()},
        )
        self.broadcast(envelope)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _oldest_seq(self) -> int:
        if not self._buffer:
            return 0
        return self._buffer[0].seq

    def _gap_message(self, requested: int, oldest: int) -> str:
        envelope = BuilderEventEnvelope(
            event_id=f"gap:{oldest}",
            type=GAP_SIGNAL,
            payload={
                "reason": "requested cursor predates retention window",
                "requested_cursor": requested,
                "oldest_retained": oldest,
            },
        )
        envelope.seq = oldest  # mark at the oldest retained position
        return envelope.to_sse()


# Global singleton for the builder event stream.
builder_events = BuilderEventBroadcaster()
