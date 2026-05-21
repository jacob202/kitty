"""Integration-style tests for Open WebUI / LiteLLM chat path."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from gateway.app import app


def test_chat_completions_non_stream_health_uses_route_model_and_passes_domain():
    """Health domain goes through route_model (no longer hardcoded kitty-private)."""
    mock_gsp = AsyncMock(return_value="FULL_SYSTEM")
    fake = {"choices": [{"message": {"role": "assistant", "content": "stay hydrated"}}]}
    mock_llm = AsyncMock(return_value=fake)
    with patch(
        "gateway.routes.completions.classify_domain", return_value="health"
    ), patch(
        "gateway.routes.completions.route_model", return_value="kitty-default"
    ), patch(
        "gateway.context_builder.get_system_prompt", mock_gsp
    ), patch(
        "gateway.routes.completions._non_stream_response", mock_llm
    ):
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
    mock_gsp.assert_awaited_once()
    assert mock_gsp.await_args.kwargs["domain"] == "health"
    assert mock_gsp.await_args.kwargs["parts_mode"] is False
    payload = mock_llm.call_args[0][0]
    assert payload["model"] == "kitty-default"
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"] == "FULL_SYSTEM"


def test_chat_completions_non_stream_non_health_uses_route_model():
    mock_gsp = AsyncMock(return_value="SYS")
    fake = {"choices": [{"message": {"role": "assistant", "content": "hey"}}]}
    mock_llm = AsyncMock(return_value=fake)
    with patch(
        "gateway.routes.completions.classify_domain", return_value="soul"
    ), patch(
        "gateway.routes.completions.route_model", return_value="openrouter/test-model"
    ), patch(
        "gateway.context_builder.get_system_prompt", mock_gsp
    ), patch(
        "gateway.routes.completions._non_stream_response", mock_llm
    ):
        client = TestClient(app)
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}], "stream": False},
        )
    assert response.status_code == 200
    mock_gsp.assert_awaited_once()
    assert mock_gsp.await_args.kwargs["domain"] == "soul"
    payload = mock_llm.call_args[0][0]
    assert payload["model"] == "openrouter/test-model"


def test_non_stream_response_logs_usage():
    from gateway.routes import completions as completion_routes

    class FakeResponse:
        def json(self):
            return {
                "model": "kitty-default",
                "choices": [{"message": {"role": "assistant", "content": "hi"}}],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                },
            }

    class FakeClient:
        async def post(self, *args, **kwargs):
            return FakeResponse()

    async def run_test():
        with patch(
            "gateway.routes.completions.get_http_client", return_value=FakeClient()
        ), patch("gateway.routes.completions.log_llm_usage") as mock_log:
            result = await completion_routes._non_stream_response(
                {"model": "kitty-default"}
            )
        assert result["usage"]["total_tokens"] == 5
        assert completion_routes.extract_assistant_text(result) == "hi"
        assert mock_log.call_args.args[0] == "litellm"
        assert mock_log.call_args.args[2] == "chat.completions.create"
        assert mock_log.call_args.kwargs == {}
        assert mock_log.call_args.args[4]["route"] == "gateway_chat_nonstream"

    import asyncio

    asyncio.run(run_test())


def test_close_session_uses_typed_payload() -> None:
    with patch("gateway.memory.consolidate_session") as mock_consolidate:
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
    mock_consolidate.assert_called_once_with(
        "session-123", [{"role": "user", "content": "hi"}]
    )
