"""Integration-style tests for Open WebUI / LiteLLM chat path."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


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
