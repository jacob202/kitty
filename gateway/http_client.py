"""Shared async HTTP client for LiteLLM proxy calls."""

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
            # Don't await aclose() here if the old loop is closed, 
            # as it will raise RuntimeError: Event loop is closed.
            # Just let it be garbage collected or close it if possible.
            try:
                if _loop is not None and _loop.is_running():
                    await _http_client.aclose()
            except Exception:
                pass
                
        _http_client = httpx.AsyncClient(
            timeout=60, limits=httpx.Limits(max_connections=100)
        )
        _loop = current_loop
        
    return _http_client
