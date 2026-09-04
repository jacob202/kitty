"""Chat-turn failure contract: friendly copy, SSE error events, no raw jargon.

See gateway/chat_errors.py and the failures surfaced by
llm_client.iter_chat_completions_stream and the streaming route.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from gateway.chat_errors import (
    FRIENDLY_MESSAGES,
    ChatErrorKind,
    ChatTurnError,
    sse_error_event,
)
from gateway.llm_client import ProviderChainExhausted

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


def _sse_frames(event: bytes) -> list[str]:
    return [
        line[len("data: "):]
        for line in event.decode().split("\n\n")
        if line.startswith("data: ")
    ]


def test_sse_error_event_payload():
    event = sse_error_event(ChatErrorKind.ROUTING, "plain words for the phone")
    assert event.startswith(b"data: ")
    payload = json.loads(_sse_frames(event)[0])
    assert payload == {"error": {"kind": "routing", "message": "plain words for the phone"}}


def test_sse_error_event_puts_kitty_frame_first():
    """chat-client.ts throws on the error frame and never reads past it.

    If anything preceded it, Kitty's own UI would render that and then throw —
    the same failure shown twice.
    """
    frames = _sse_frames(sse_error_event(ChatErrorKind.ROUTING, "no credit"))
    assert json.loads(frames[0])["error"]["kind"] == "routing"


def test_sse_error_event_is_readable_by_an_openai_client():
    """Open WebUI cannot parse Kitty's error frame.

    Without an OpenAI-shaped chunk carrying the same copy, a provider rejection
    reached the user as a blank assistant reply and nothing else. The standard
    finish reason must remain valid for strict OpenAI-compatible clients.
    """
    frames = _sse_frames(sse_error_event(ChatErrorKind.ROUTING, "no credit"))
    chunk = json.loads(frames[1])
    assert chunk["choices"][0]["delta"]["content"] == "no credit"
    assert chunk["choices"][0]["finish_reason"] == "stop"
    assert chunk["kitty_error_kind"] == "routing"


def test_sse_error_event_closes_the_stream():
    """The re-raise used to tear the connection down with no boundary, which
    OpenAI-compatible clients report as a cut connection, not the real cause."""
    assert _sse_frames(sse_error_event(ChatErrorKind.UPSTREAM, "boom"))[-1] == "[DONE]"


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
    resp.aread = AsyncMock(return_value=error_body)
    stream_cm = AsyncMock()
    stream_cm.__aenter__.return_value = resp

    client = MagicMock()
    client.stream = MagicMock(return_value=stream_cm)

    async def run():
        with (
            patch("gateway.llm_client.selected_provider_name", return_value=None),
            patch("gateway.http_client.get_http_client", new=AsyncMock(return_value=client)),
            patch("gateway.llm_client.call_llm", side_effect=ProviderChainExhausted(["fallbacks exhausted"])),
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


def test_stream_non_2xx_litellm_falls_back_when_provider_is_auto():
    from gateway.llm_client import iter_chat_completions_stream

    request = httpx.Request("POST", "http://127.0.0.1:8001/v1/chat/completions")
    resp = httpx.Response(403, request=request, content=b'{"error":{"message":"Key limit exceeded"}}')
    stream_cm = AsyncMock()
    stream_cm.__aenter__.return_value = resp
    client = MagicMock()
    client.stream = MagicMock(return_value=stream_cm)

    async def run():
        with (
            patch("gateway.llm_client.selected_provider_name", return_value=None),
            patch("gateway.http_client.get_http_client", new=AsyncMock(return_value=client)),
            patch("gateway.llm_client.call_llm", return_value="fallback answered") as fallback,
        ):
            chunks = await _collect(
                iter_chat_completions_stream(
                    {"model": "kitty-default", "messages": [{"role": "user", "content": "hi"}]}
                )
            )
        return chunks, fallback

    chunks, fallback = asyncio.run(run())
    assert fallback.call_count == 1
    payload = json.loads(chunks[0].decode().removeprefix("data: ").strip())
    assert payload["choices"][0]["delta"]["content"] == "fallback answered"
    assert chunks[-1] == b"data: [DONE]\n\n"


def test_stream_5xx_litellm_raises_upstream_error():
    from gateway.llm_client import iter_chat_completions_stream

    resp = MagicMock()
    resp.status_code = 503
    resp.json = MagicMock(return_value={"error": {"message": "upstream unavailable"}})
    resp.content = b"{}"
    resp.aread = AsyncMock(return_value=b"{}")
    stream_cm = AsyncMock()
    stream_cm.__aenter__.return_value = resp

    client = MagicMock()
    client.stream = MagicMock(return_value=stream_cm)

    async def run():
        with (
            patch("gateway.llm_client.selected_provider_name", return_value=None),
            patch("gateway.http_client.get_http_client", new=AsyncMock(return_value=client)),
            patch("gateway.llm_client.call_llm", side_effect=ProviderChainExhausted(["fallbacks exhausted"])),
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
