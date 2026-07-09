"""Tests for Magic Kitty route behavior."""

import asyncio
import time

import pytest

from gateway.routes import magic as magic_route


@pytest.mark.asyncio
async def test_magic_route_does_not_block_event_loop(monkeypatch):
    def slow_discover_connections(force: bool = False):
        time.sleep(0.2)
        return {"connections": [], "generated_at": time.time(), "projects_used": 0}

    monkeypatch.setattr(
        magic_route.magic_kitty,
        "discover_connections",
        slow_discover_connections,
    )

    task = asyncio.create_task(magic_route.get_magic_insights())
    start = time.perf_counter()
    await asyncio.sleep(0.01)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.1
    assert await task == {
        "connections": [],
        "generated_at": pytest.approx(time.time(), abs=1.0),
        "projects_used": 0,
    }
