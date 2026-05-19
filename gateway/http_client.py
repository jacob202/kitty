"""Shared async HTTP client for LiteLLM proxy calls."""

from __future__ import annotations

import httpx

_http_client: httpx.AsyncClient | None = None


async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=60, limits=httpx.Limits(max_connections=100)
        )
    return _http_client
