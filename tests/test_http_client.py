"""Tests for the loop-bound re-init seam in gateway/http_client.py.

The shared httpx client is bound to the event loop that first calls
`get_http_client()`. When a caller runs in a different loop (FastAPI lifespan
re-init, a test that creates a fresh loop), the cached client is dropped and
a new one is built. These tests pin the behavior so the workaround can't
silently regress.
"""

from __future__ import annotations

import asyncio

import pytest

from gateway import http_client


@pytest.fixture(autouse=True)
def _reset_http_client_state():
    """Each test starts with no cached client/loop."""
    http_client._reset_for_tests()
    yield
    http_client._reset_for_tests()


@pytest.mark.asyncio
async def test_same_loop_reuses_cached_client():
    client1 = await http_client.get_http_client()
    client2 = await http_client.get_http_client()
    assert client1 is client2
    assert http_client._http_client is client1
    assert http_client._loop is asyncio.get_running_loop()


@pytest.mark.asyncio
async def test_closed_client_is_replaced():
    client1 = await http_client.get_http_client()
    await client1.aclose()
    assert client1.is_closed
    client2 = await http_client.get_http_client()
    assert client2 is not client1
    assert not client2.is_closed


def test_loop_switch_replaces_client_without_raising():
    """A second event loop must get a fresh client without RuntimeError."""

    async def _get():
        return await http_client.get_http_client()

    loop1 = asyncio.new_event_loop()
    try:
        client1 = loop1.run_until_complete(_get())
    finally:
        loop1.run_until_complete(client1.aclose())
        loop1.close()

    loop2 = asyncio.new_event_loop()
    try:
        client2 = loop2.run_until_complete(_get())
        assert client2 is not client1
        assert not client2.is_closed
        assert http_client._loop is loop2
    finally:
        loop2.run_until_complete(client2.aclose())
        loop2.close()


@pytest.mark.asyncio
async def test_aclose_http_client_closes_and_clears_cache():
    client = await http_client.get_http_client()
    await http_client.aclose_http_client()
    assert client.is_closed
    assert http_client._http_client is None
    assert http_client._loop is None


@pytest.mark.asyncio
async def test_aclose_http_client_is_safe_with_no_cached_client():
    """Lifespan shutdown runs even when no request ever built a client."""
    await http_client.aclose_http_client()
    assert http_client._http_client is None


@pytest.mark.asyncio
async def test_aclose_http_client_is_idempotent():
    client = await http_client.get_http_client()
    await http_client.aclose_http_client()
    await http_client.aclose_http_client()
    assert client.is_closed
    assert http_client._http_client is None


def test_aclose_http_client_drops_client_bound_to_a_closed_loop():
    """The dangerous shutdown case: the cached client's loop is already gone.

    Awaiting `aclose()` from a live loop against a transport owned by a closed
    loop raises RuntimeError, and lifespan shutdown has no recovery from that.
    The reference must be dropped instead of closed.
    """
    async def _get():
        return await http_client.get_http_client()

    loop1 = asyncio.new_event_loop()
    try:
        client1 = loop1.run_until_complete(_get())
    finally:
        loop1.close()

    loop2 = asyncio.new_event_loop()
    try:
        loop2.run_until_complete(http_client.aclose_http_client())
        assert http_client._http_client is None
        assert http_client._loop is None
        # The client is abandoned rather than closed; nothing awaited against
        # the dead loop, which is the property that matters.
        assert client1 is not None
    finally:
        loop2.close()
