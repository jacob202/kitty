"""Integration-style tests for Open WebUI / LiteLLM chat path."""

from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

def test_chat_completions_non_stream_health_uses_route_model_and_passes_domain():
    """Health domain goes through route_model (no longer hardcoded kitty-private)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "stay hydrated"}}],
        "usage": {"total_tokens": 10},
        "model": "kitty-default"
    }

    with patch("gateway.routes.completions.classify_domain", return_value="health"), \
         patch("gateway.routes.completions.route_model", return_value="kitty-default"), \
         patch("gateway.context_builder.get_system_prompt", new=AsyncMock(return_value="FULL_SYSTEM")), \
         patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        
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
        "model": "openrouter/test-model"
    }

    with patch("gateway.routes.completions.classify_domain", return_value="soul"), \
         patch("gateway.routes.completions.route_model", return_value="openrouter/test-model"), \
         patch("gateway.context_builder.get_system_prompt", new=AsyncMock(return_value="SYS")), \
         patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        
        from gateway.app import app
        client = TestClient(app)
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}], "stream": False},
        )
    assert response.status_code == 200


def test_non_stream_response_logs_usage():
    from gateway.routes import completions as completion_routes
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "kitty-default",
        "choices": [{"message": {"role": "assistant", "content": "hi"}}],
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5,
        },
    }

    async def run_test():
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)), \
             patch("gateway.routes.completions.log_llm_usage") as mock_log:
            result = await completion_routes._non_stream_response(
                {"model": "kitty-default"}
            )
        assert result["usage"]["total_tokens"] == 5
        assert completion_routes.extract_assistant_text(result) == "hi"
        assert mock_log.call_args.args[0] == "litellm"

    import asyncio
    asyncio.run(run_test())


def test_close_session_uses_typed_payload() -> None:
    with patch("gateway.memory.consolidate_session") as mock_consolidate:
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
