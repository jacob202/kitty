"""Integration-style tests for Open WebUI / LiteLLM chat path."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.context_assembler import ContextBundle


def _post_stream(chunks, bundle, *, body=None, lifecycle_patches=False):
    """POST a streaming completion with a canned upstream and real bundle.

    Returns (response, mocks) where mocks holds start/finish turn mocks when
    ``lifecycle_patches`` is set.
    """

    async def fake_stream(_payload):
        for chunk in chunks:
            yield chunk

    request_body = body or {
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
    }
    mocks = {}
    patches = [
        patch("gateway.routes.completions.classify_domain", return_value="soul"),
        patch("gateway.routes.completions.route_model", return_value="kitty-default"),
        patch(
            "gateway.context_assembler.assemble_context",
            new=AsyncMock(return_value=bundle),
        ),
        patch(
            "gateway.routes.completions.iter_chat_completions_stream",
            new=fake_stream,
        ),
    ]
    if lifecycle_patches:
        handle = MagicMock(turn_id="turn-1", attempt_id="attempt-1")
        start = patch(
            "gateway.routes.completions.chat_lifecycle.start_turn",
            return_value=handle,
        )
        finish = patch("gateway.routes.completions.chat_lifecycle.finish_turn")
        chats = patch(
            "gateway.routes.completions.chats_store.get_chat",
            return_value={"id": "chat-1"},
        )
        patches.extend([start, finish, chats])

    from gateway.app import app

    with patches[0], patches[1], patches[2], patches[3]:
        if lifecycle_patches:
            with patches[4] as mock_start, patches[5] as mock_finish, patches[6]:
                mocks["start"] = mock_start
                mocks["finish"] = mock_finish
                response = TestClient(app).post("/v1/chat/completions", json=request_body)
        else:
            response = TestClient(app).post("/v1/chat/completions", json=request_body)
    return response, mocks


CONTENT_CHUNK_1 = b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
CONTENT_CHUNK_2 = b'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
DONE_CHUNK = b"data: [DONE]\n\n"


class TestMemoryTrailer:
    """CR-04: one memory_items trailer between content and [DONE]."""

    def test_trailer_rides_between_content_and_done(self):
        bundle = ContextBundle(
            system="SYS",
            injected_memory_items=["decided on FastAPI", "prefers dark mode"],
        )
        response, _ = _post_stream(
            [CONTENT_CHUNK_1, CONTENT_CHUNK_2, DONE_CHUNK], bundle
        )
        assert response.status_code == 200
        assert response.content == (
            CONTENT_CHUNK_1
            + CONTENT_CHUNK_2
            + b'data: {"memory_items": ["decided on FastAPI", "prefers dark mode"]}\n\n'
            + DONE_CHUNK
        )

    def test_no_memories_means_no_trailer(self):
        bundle = ContextBundle(system="SYS", injected_memory_items=[])
        response, _ = _post_stream(
            [CONTENT_CHUNK_1, CONTENT_CHUNK_2, DONE_CHUNK], bundle
        )
        assert response.status_code == 200
        assert response.content == CONTENT_CHUNK_1 + CONTENT_CHUNK_2 + DONE_CHUNK
        assert b"memory_items" not in response.content

    def test_trailer_absent_when_stream_never_reaches_done(self):
        """A cut stream (no [DONE]) reached no completion boundary — no
        memory evidence may be emitted for it."""
        bundle = ContextBundle(system="SYS", injected_memory_items=["evidence"])
        response, _ = _post_stream([CONTENT_CHUNK_1, CONTENT_CHUNK_2], bundle)
        assert response.content == CONTENT_CHUNK_1 + CONTENT_CHUNK_2
        assert b"memory_items" not in response.content

    def test_empty_completion_still_gets_trailer_at_done(self):
        bundle = ContextBundle(system="SYS", injected_memory_items=["evidence"])
        response, _ = _post_stream([DONE_CHUNK], bundle)
        assert response.content == (
            b'data: {"memory_items": ["evidence"]}\n\n' + DONE_CHUNK
        )

    def test_trailer_items_truncated_to_200_chars(self):
        long_text = "x" * 300
        bundle = ContextBundle(system="SYS", injected_memory_items=[long_text])
        response, _ = _post_stream([DONE_CHUNK], bundle)
        assert (
            b'data: {"memory_items": ["' + b"x" * 200 + b'"]}\n\n' + DONE_CHUNK
            == response.content
        )

    def test_trailer_preserves_injection_order_and_unicode(self):
        bundle = ContextBundle(
            system="SYS",
            injected_memory_items=["première note", "deuxième — 🎯"],
        )
        response, _ = _post_stream([DONE_CHUNK], bundle)
        assert response.content == (
            'data: {"memory_items": ["première note", "deuxième — 🎯"]}\n\n'.encode("utf-8")
            + DONE_CHUNK
        )

    def test_upstream_error_mid_stream_propagates_without_trailer(self):
        """Errors are not swallowed to force a trailer or [DONE]."""

        async def broken_stream(_payload):
            yield CONTENT_CHUNK_1
            raise RuntimeError("upstream died mid-stream")

        bundle = ContextBundle(system="SYS", injected_memory_items=["evidence"])
        with patch(
            "gateway.routes.completions.classify_domain", return_value="soul"
        ), patch(
            "gateway.routes.completions.route_model", return_value="kitty-default"
        ), patch(
            "gateway.context_assembler.assemble_context",
            new=AsyncMock(return_value=bundle),
        ), patch(
            "gateway.routes.completions.iter_chat_completions_stream",
            new=broken_stream,
        ):
            from gateway.app import app

            with pytest.raises(RuntimeError, match="upstream died mid-stream"):
                TestClient(app).post(
                    "/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": True,
                    },
                )

    def test_lifecycle_transcript_excludes_trailer(self):
        """The recorded assistant text is the model's content only — the
        trailer never leaks into the lifecycle ledger."""
        bundle = ContextBundle(system="SYS", injected_memory_items=["evidence"])
        response, mocks = _post_stream(
            [CONTENT_CHUNK_1, CONTENT_CHUNK_2, DONE_CHUNK],
            bundle,
            body={
                "conversation_id": "chat-1",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
            lifecycle_patches=True,
        )
        assert response.status_code == 200
        assert b'data: {"memory_items": ["evidence"]}\n\n' in response.content
        finish_kwargs = mocks["finish"].call_args.kwargs
        assert finish_kwargs["assistant_text"] == "Hello"
        assert finish_kwargs["status"] == "succeeded"


def test_thread_objective_reaches_lifecycle_and_context():
    mock_payload = {
        "choices": [{"message": {"role": "assistant", "content": "next step"}}],
        "usage": {"total_tokens": 10},
        "model": "kitty-default",
    }
    mock_chat = AsyncMock(return_value=mock_payload)
    mock_bundle = MagicMock(system="FULL_SYSTEM")
    mock_assemble = AsyncMock(return_value=mock_bundle)
    mock_handle = MagicMock(turn_id="turn-1")

    with patch(
        "gateway.routes.completions.classify_domain", return_value="soul"
    ), patch(
        "gateway.routes.completions.route_model", return_value="kitty-default"
    ), patch(
        "gateway.routes.completions.chats_store.get_chat",
        return_value={"id": "chat-1", "objective": "Submit one application"},
    ), patch(
        "gateway.routes.completions.chat_lifecycle.start_turn",
        return_value=mock_handle,
    ) as mock_start, patch(
        "gateway.routes.completions.chat_lifecycle.finish_turn"
    ), patch(
        "gateway.context_assembler.assemble_context", new=mock_assemble
    ), patch(
        "gateway.routes.completions.chat_completions_non_stream", new=mock_chat
    ):
        from gateway.app import app

        response = TestClient(app).post(
            "/v1/chat/completions",
            json={
                "conversation_id": "chat-1",
                "messages": [{"role": "user", "content": "what next?"}],
                "stream": False,
            },
        )

    assert response.status_code == 200
    assert mock_start.call_args.kwargs["objective"] == "Submit one application"
    assert mock_assemble.call_args.kwargs["objective"] == "Submit one application"


def test_chat_completions_non_stream_health_uses_route_model_and_passes_domain():
    """Health domain goes through route_model (no longer hardcoded kitty-private)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "stay hydrated"}}],
        "usage": {"total_tokens": 10},
        "model": "kitty-default",
    }

    mock_payload = mock_resp.json.return_value
    mock_chat = AsyncMock(return_value=mock_payload)

    with patch(
        "gateway.routes.completions.classify_domain", return_value="health"
    ), patch(
        "gateway.routes.completions.route_model", return_value="kitty-default"
    ), patch(
        "gateway.context_assembler.get_system_prompt",
        new=AsyncMock(return_value="FULL_SYSTEM"),
    ), patch(
        "gateway.llm_client.chat_completions_non_stream", new=mock_chat
    ), patch(
        "gateway.routes.completions.chat_completions_non_stream", new=mock_chat
    ):

        from gateway.app import app

        client = TestClient(app)
        response = client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "my blood pressure reading"}],
                "stream": False,
            },
        )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "stay hydrated"


def test_chat_completions_non_stream_non_health_uses_route_model():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "hey"}}],
        "usage": {"total_tokens": 10},
        "model": "openrouter/test-model",
    }

    mock_payload = mock_resp.json.return_value
    mock_chat = AsyncMock(return_value=mock_payload)

    with patch(
        "gateway.routes.completions.classify_domain", return_value="soul"
    ), patch(
        "gateway.routes.completions.route_model", return_value="openrouter/test-model"
    ), patch(
        "gateway.context_assembler.get_system_prompt", new=AsyncMock(return_value="SYS")
    ), patch(
        "gateway.llm_client.chat_completions_non_stream", new=mock_chat
    ), patch(
        "gateway.routes.completions.chat_completions_non_stream", new=mock_chat
    ):

        from gateway.app import app

        client = TestClient(app)
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}], "stream": False},
        )
    assert response.status_code == 200


def test_chat_completions_non_stream_logs_usage():
    from gateway.llm_client import chat_completions_non_stream, extract_assistant_text

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "model": "kitty-default",
        "choices": [{"message": {"role": "assistant", "content": "hi"}}],
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5,
        },
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    async def run_test():
        with patch(
            "gateway.http_client.get_http_client",
            new=AsyncMock(return_value=mock_client),
        ), patch("gateway.llm_client.log_llm_usage") as mock_log:
            result = await chat_completions_non_stream(
                {
                    "model": "kitty-default",
                    "messages": [{"role": "user", "content": "hi"}],
                }
            )
        assert result["usage"]["total_tokens"] == 5
        assert extract_assistant_text(result) == "hi"
        assert mock_log.call_args.args[0] == "litellm"

    import asyncio

    asyncio.run(run_test())


def test_close_session_uses_typed_payload() -> None:
    with patch("gateway.memory.consolidate_session"):
        from gateway.app import app

        client = TestClient(app)
        response = client.post(
            "/sessions/close",
            json={
                "session_id": "session-123",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "session_id": "session-123"}


def test_close_session_surfaces_memory_failure() -> None:
    """A memory outage during session close must be loud, not a fake 'ok'.

    consolidate_session now raises MemoryError on persistence failure; the
    route deliberately lets it propagate to the global KittyError handler
    instead of reporting success while the session was silently dropped.
    """
    from gateway.memory import MemoryError as KittyMemoryError

    error = KittyMemoryError(
        "memory consolidation failed (OSError)",
        details={"operation": "memory consolidation"},
    )
    with patch("gateway.memory.consolidate_session", side_effect=error):
        from gateway.app import app

        client = TestClient(app)
        response = client.post(
            "/sessions/close",
            json={
                "session_id": "session-123",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "storage.unavailable"
    assert body["message"] == "memory consolidation failed (OSError)"


def test_models_endpoint_surfaces_litellm_http_failure() -> None:
    import asyncio

    from fastapi import HTTPException

    response = MagicMock(status_code=401, text="invalid master key")
    client = MagicMock()
    client.get = AsyncMock(return_value=response)

    async def run_test() -> None:
        with patch(
            "gateway.routes.completions.get_http_client",
            new=AsyncMock(return_value=client),
        ):
            from gateway.routes.completions import api_models

            try:
                await api_models()
            except HTTPException as exc:
                assert exc.status_code == 502
                assert "HTTP 401" in str(exc.detail)
            else:
                raise AssertionError("api_models hid a LiteLLM HTTP failure")

    asyncio.run(run_test())
