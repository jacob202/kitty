"""Chat-turn failure contract: friendly copy, SSE error events, no raw jargon.

See gateway/chat_errors.py and the failures surfaced by
llm_client.iter_chat_completions_stream and the streaming route.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.chat_errors import (
    FRIENDLY_MESSAGES,
    ChatErrorKind,
    ChatTurnError,
    sse_error_event,
)

# ── ChatTurnError + copy ──────────────────────────────────────────────────────


def test_chat_turn_error_has_user_facing_default_message():
    err = ChatTurnError(kind=ChatErrorKind.ROUTING, detail="litellm: HTTP 404")
    assert err.message == FRIENDLY_MESSAGES[ChatErrorKind.ROUTING]
    assert "out of credit" in err.message or "different model" in err.message
    assert err.detail == "litellm: HTTP 404"
    # The raw detail must never be the user-facing message.
    assert "404" not in err.message


def test_chat_turn_error_carries_override_message():
    err = ChatTurnError(kind=ChatErrorKind.UPSTREAM, user_message="custom copy")
    assert err.message == "custom copy"


def test_chat_turn_error_from_exception_keeps_detail():
    err = ChatTurnError.from_exception(
        RuntimeError("stream died"), kind=ChatErrorKind.CUT_OFF, detail="net cut"
    )
    assert err.kind == ChatErrorKind.CUT_OFF
    assert err.detail == "net cut"


# ── SSE error event shape ─────────────────────────────────────────────────────


def test_sse_error_event_payload():
    event = sse_error_event(ChatErrorKind.ROUTING, "plain words for the phone")
    assert event.startswith(b"data: ")
    payload = json.loads(event[len(b"data: "):].strip())
    assert payload == {"error": {"kind": "routing", "message": "plain words for the phone"}}
    assert b"[DONE]" not in event


# ── iter_chat_completions_stream surfaces failures ────────────────────────────


async def _collect(agen):
    return [chunk async for chunk in agen]


def test_stream_non_2xx_litellm_raises_routing_error():
    from gateway.llm_client import iter_chat_completions_stream

    error_body = json.dumps(
        {"error": {"message": "Provider returned an invalid balance bucket", "type": "api_error"}}
    ).encode()
    resp = MagicMock()
    resp.status_code = 400
    resp.json = MagicMock(
        return_value={"error": {"message": "Provider returned an invalid balance bucket"}}
    )
    resp.content = error_body
    stream_cm = AsyncMock()
    stream_cm.__aenter__.return_value = resp

    client = MagicMock()
    client.stream = MagicMock(return_value=stream_cm)

    async def run():
        with (
            patch("gateway.llm_client.selected_provider_name", return_value=None),
            patch("gateway.http_client.get_http_client", new=AsyncMock(return_value=client)),
        ):
            with pytest.raises(ChatTurnError) as excinfo:
                await _collect(
                    iter_chat_completions_stream(
                        {"model": "kitty-default", "messages": [{"role": "user", "content": "hi"}]}
                    )
                )
        return excinfo.value

    err = asyncio.run(run())
    assert err.kind == ChatErrorKind.ROUTING
    assert "HTTP 400" in err.detail
    assert err.message == FRIENDLY_MESSAGES[ChatErrorKind.ROUTING]


def test_stream_5xx_litellm_raises_upstream_error():
    from gateway.llm_client import iter_chat_completions_stream

    resp = MagicMock()
    resp.status_code = 503
    resp.json = MagicMock(return_value={"error": {"message": "upstream unavailable"}})
    resp.content = b"{}"
    stream_cm = AsyncMock()
    stream_cm.__aenter__.return_value = resp

    client = MagicMock()
    client.stream = MagicMock(return_value=stream_cm)

    async def run():
        with (
            patch("gateway.llm_client.selected_provider_name", return_value=None),
            patch("gateway.http_client.get_http_client", new=AsyncMock(return_value=client)),
        ):
            with pytest.raises(ChatTurnError) as excinfo:
                await _collect(
                    iter_chat_completions_stream(
                        {"model": "kitty-default", "messages": [{"role": "user", "content": "hi"}]}
                    )
                )
        return excinfo.value

    err = asyncio.run(run())
    assert err.kind == ChatErrorKind.UPSTREAM


def test_stream_connection_error_raises_upstream_error():
    from gateway.llm_client import iter_chat_completions_stream

    stream_cm = AsyncMock()
    stream_cm.__aenter__.side_effect = ConnectionError("refused")
    stream_cm.__aexit__.return_value = False
    # httpx.ConnectError is imported at module scope; ConnectionError checks the
    # broad `except Exception` branch so both map to UPSTREAM.
    client = MagicMock()
    client.stream = MagicMock(return_value=stream_cm)

    async def run():
        with (
            patch("gateway.llm_client.selected_provider_name", return_value=None),
            patch("gateway.http_client.get_http_client", new=AsyncMock(return_value=client)),
        ):
            with pytest.raises(ChatTurnError) as excinfo:
                await _collect(
                    iter_chat_completions_stream(
                        {"model": "kitty-default", "messages": [{"role": "user", "content": "hi"}]}
                    )
                )
        return excinfo.value

    err = asyncio.run(run())
    assert err.kind == ChatErrorKind.UPSTREAM


def test_stream_selected_provider_exhausted_raises_routing_error():
    from gateway.chat_errors import ChatTurnError as CTE
    from gateway.llm_client import ProviderChainExhausted, iter_chat_completions_stream

    async def run():
        with patch(
            "gateway.llm_client.selected_provider_name", return_value="openrouter"
        ), patch(
            "gateway.llm_client.normalize_litellm_request_model",
            return_value="deepseek/deepseek-v4-pro",
        ), patch(
            "gateway.llm_client.route_model", return_value="deepseek/deepseek-v4-pro",
        ), patch(
            "gateway.llm_client.call_selected_provider",
            side_effect=ProviderChainExhausted(["openrouter: out of credit"]),
        ):
            with pytest.raises(CTE) as excinfo:
                await _collect(
                    iter_chat_completions_stream(
                        {"model": "kitty-default", "messages": [{"role": "user", "content": "hi"}]}
                    )
                )
        return excinfo.value

    err = asyncio.run(run())
    assert err.kind == ChatErrorKind.ROUTING
