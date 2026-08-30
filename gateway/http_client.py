"""Shared async HTTP client for LiteLLM proxy calls.

The client is bound to the event loop that first calls `get_http_client()`. If
a caller later runs in a *different* event loop (FastAPI lifespan re-init, a
test that creates a fresh loop, the auth hot-reload path), the cached client
is dropped and a new one is built. We intentionally do **not** await
`aclose()` on the old client if its loop is closed — awaiting from a live
loop against a closed loop raises `RuntimeError: Event loop is closed`. The
old client is left to be garbage-collected.

This module is intentionally a tiny global seam. Do not pass the client
around in a DI container; callers always go through `get_http_client()` so
loop-switch re-init stays in one place.
"""

from __future__ import annotations

import asyncio

import httpx

_http_client: httpx.AsyncClient | None = None
_loop: asyncio.AbstractEventLoop | None = None


async def get_http_client() -> httpx.AsyncClient:
    global _http_client, _loop

    current_loop = asyncio.get_running_loop()

    if _http_client is None or _http_client.is_closed or _loop is not current_loop:
        if _http_client is not None and not _http_client.is_closed:
            # Only close on the same live loop that created the client. A
            # loop switch means the old client belongs to a different loop, so
            # awaiting `aclose()` here can fail for reasons the caller cannot
            # recover from cleanly.
            if _loop is current_loop:
                await _http_client.aclose()

        _http_client = httpx.AsyncClient(timeout=60, limits=httpx.Limits(max_connections=100))
        _loop = current_loop

    return _http_client


def _reset_for_tests() -> None:
    """Clear the cached client and loop reference. Test-only."""
    global _http_client, _loop
    _http_client = None
    _loop = None
