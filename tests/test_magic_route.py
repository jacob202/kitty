"""Tests for Magic Kitty route behavior."""

import threading

import pytest

from gateway.routes import magic as magic_route


@pytest.mark.asyncio
async def test_magic_route_does_not_block_event_loop(monkeypatch):
    event_loop_thread = threading.get_ident()
    discovery_threads: list[int] = []

    def discover_connections(force: bool = False):
        discovery_threads.append(threading.get_ident())
        return {"connections": [], "generated_at": 123.0, "projects_used": 0}

    monkeypatch.setattr(
        magic_route.magic_kitty,
        "discover_connections",
        discover_connections,
    )

    result = await magic_route.get_magic_insights()

    assert len(discovery_threads) == 1
    assert discovery_threads[0] != event_loop_thread
    assert result == {
        "connections": [],
        "generated_at": 123.0,
        "projects_used": 0,
    }
