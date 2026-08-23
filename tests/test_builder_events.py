"""Tests for gateway/builder_events.py — replayable SSE event stream."""

from __future__ import annotations

import asyncio
import json

import pytest

from gateway.builder_events import (
    EVENT_SCHEMA_VERSION,
    BuilderEventBroadcaster,
    BuilderEventEnvelope,
)
from gateway.builder_worker_session import WorkerEvent, WorkerEventType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_data_events(raw: str) -> list[dict]:
    """Parse only data events (skip heartbeat, connected, empty)."""
    events: list[dict] = []
    for msg in raw.split("\n\n"):
        if not msg.strip():
            continue
        for line in msg.split("\n"):
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "{}":
                    continue
                try:
                    events.append(json.loads(data_str))
                except json.JSONDecodeError:
                    continue
    return events


async def _take_events(gen, count: int, timeout: float = 2.0) -> list[dict]:
    """Take up to *count* parsed events from the generator."""
    parsed: list[dict] = []
    try:
        async with asyncio.timeout(timeout):
            async for msg in gen:
                parsed.extend(_parse_data_events(msg))
                if len(parsed) >= count:
                    break
    except asyncio.TimeoutError:
        pass
    try:
        await gen.aclose()
    except Exception:
        pass
    return parsed


# ---------------------------------------------------------------------------
# BuilderEventEnvelope
# ---------------------------------------------------------------------------


class TestBuilderEventEnvelope:
    def test_defaults(self) -> None:
        env = BuilderEventEnvelope(event_id="ev1", seq=1)
        d = env.to_dict()
        assert d["schema_version"] == EVENT_SCHEMA_VERSION
        assert d["event_id"] == "ev1"
        assert d["seq"] == 1

    def test_full_constructor(self) -> None:
        env = BuilderEventEnvelope(
            event_id="ev2",
            seq=5,
            timestamp=100.0,
            initiative_id="i1",
            packet_id="p1",
            attempt_id="a1",
            session_id="s1",
            type="text_delta",
            payload={"text": "hello"},
            raw_log_ref="/tmp/log",
        )
        d = env.to_dict()
        assert d["initiative_id"] == "i1"
        assert d["raw_log_ref"] == "/tmp/log"

    def test_sse_format(self) -> None:
        env = BuilderEventEnvelope(event_id="ev3", seq=1, type="test")
        sse = env.to_sse()
        assert sse.startswith("id: 1\n")
        assert "data: " in sse

    def test_from_worker_event(self) -> None:
        we = WorkerEvent(
            event_id="we1", seq=42, session_id="s1",
            type=WorkerEventType.TEXT_DELTA, data={"text": "hi"},
        )
        env = BuilderEventEnvelope.from_worker_event(
            we, seq=100, initiative_id="i1", packet_id="p1", attempt_id="a1",
        )
        assert env.type == "text_delta"
        assert env.seq == 100

    def test_from_queue_event(self) -> None:
        qe = {"id": 5, "type": "task_claimed", "created_at": "2024-01-01T00:00:00Z", "extra": "value"}
        env = BuilderEventEnvelope.from_queue_event(
            qe, seq=10, task_id="t1", initiative_id="i1", packet_id="p1",
        )
        assert env.type == "queue.task_claimed"
        assert "extra" in env.payload


# ---------------------------------------------------------------------------
# BuilderEventBroadcaster
# ---------------------------------------------------------------------------


class TestBuilderEventBroadcaster:
    @pytest.mark.asyncio
    async def test_subscribe_receives_broadcast(self) -> None:
        bc = BuilderEventBroadcaster(retention=10)
        gen = bc.subscribe("client-1")
        bc.broadcast(BuilderEventEnvelope(event_id="ev1", type="test"))
        events = await _take_events(gen, count=1)
        assert len(events) >= 1
        assert events[0]["type"] == "test"

    @pytest.mark.asyncio
    async def test_cursor_replays_buffered_events(self) -> None:
        bc = BuilderEventBroadcaster(retention=10)
        for i in range(5):
            bc.broadcast(BuilderEventEnvelope(event_id=f"ev{i}", type="test"))
        gen = bc.subscribe("client-2", cursor=3)
        events = await _take_events(gen, count=3)
        assert all(e["seq"] >= 3 for e in events)

    @pytest.mark.asyncio
    async def test_cursor_before_retention_receives_gap(self) -> None:
        bc = BuilderEventBroadcaster(retention=3)
        for i in range(5):
            bc.broadcast(BuilderEventEnvelope(event_id=f"ev{i}", type="test"))
        gen = bc.subscribe("client-3", cursor=1)
        events = await _take_events(gen, count=5, timeout=1.0)
        types = [e["type"] for e in events]
        assert "gap" in types

    @pytest.mark.asyncio
    async def test_packet_filtering(self) -> None:
        bc = BuilderEventBroadcaster(retention=10)
        bc.broadcast(BuilderEventEnvelope(event_id="a1", type="test", packet_id="p1"))
        bc.broadcast(BuilderEventEnvelope(event_id="a2", type="test", packet_id="p2"))
        bc.broadcast(BuilderEventEnvelope(event_id="a3", type="test", packet_id="p1"))
        gen = bc.subscribe("client-4", cursor=1, packet_id="p1")
        events = await _take_events(gen, count=2)
        assert len(events) == 2
        assert all(e["packet_id"] == "p1" for e in events)

    @pytest.mark.asyncio
    async def test_no_cursor_delivers_latest_only(self) -> None:
        bc = BuilderEventBroadcaster(retention=10)
        for i in range(5):
            bc.broadcast(BuilderEventEnvelope(event_id=f"ev{i}", type=f"test{i}"))
        gen = bc.subscribe("client-5")
        events = await _take_events(gen, count=1, timeout=1.0)
        assert len(events) == 1
        assert events[0]["seq"] == 5

    @pytest.mark.asyncio
    async def test_emit_worker_event(self) -> None:
        bc = BuilderEventBroadcaster(retention=10)
        we = WorkerEvent(event_id="we1", seq=1, type=WorkerEventType.TEXT_DELTA, data={"text": "hello"})
        bc.emit_worker_event(we, initiative_id="i1", packet_id="p1")
        gen = bc.subscribe("client-6", cursor=1)
        events = await _take_events(gen, count=1)
        assert len(events) == 1
        assert events[0]["type"] == "text_delta"

    @pytest.mark.asyncio
    async def test_emit_queue_event(self) -> None:
        bc = BuilderEventBroadcaster(retention=10)
        bc.emit_queue_event({"id": 1, "type": "run_started", "created_at": "now"}, task_id="t1", packet_id="p1")
        gen = bc.subscribe("client-7", cursor=1)
        events = await _take_events(gen, count=1)
        assert len(events) == 1
        assert events[0]["type"] == "queue.run_started"

    @pytest.mark.asyncio
    async def test_emit_gap(self) -> None:
        bc = BuilderEventBroadcaster(retention=10)
        bc.emit_gap(reason="test overflow")
        assert len(bc._buffer) == 1
        assert bc._buffer[0].type == "gap"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        bc = BuilderEventBroadcaster(retention=10)
        gen1 = bc.subscribe("client-a")
        gen2 = bc.subscribe("client-b")
        bc.broadcast(BuilderEventEnvelope(event_id="shared", type="test"))
        e1 = await _take_events(gen1, count=1)
        e2 = await _take_events(gen2, count=1)
        assert len(e1) >= 1
        assert len(e2) >= 1

    @pytest.mark.asyncio
    async def test_close_unregisters_subscriber(self) -> None:
        bc = BuilderEventBroadcaster(retention=10)
        gen = bc.subscribe("client-c")

        assert await anext(gen) == "event: connected\ndata: {}\n\n"
        assert "client-c" in bc._queues

        await gen.aclose()

        assert "client-c" not in bc._queues
