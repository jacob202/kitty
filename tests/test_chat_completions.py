"""Integration-style tests for Open WebUI / LiteLLM chat path."""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from gateway.app import app


def test_chat_completions_non_stream_health_uses_kitty_private_and_passes_domain():
    """Health domain forces kitty-private model and forwards domain into get_system_prompt."""
    mock_gsp = AsyncMock(return_value="FULL_SYSTEM")
    fake = {"choices": [{"message": {"role": "assistant", "content": "stay hydrated"}}]}
    mock_llm = AsyncMock(return_value=fake)
    with patch("gateway.app.classify_domain", return_value="health"), \
         patch("gateway.context_builder.get_system_prompt", mock_gsp), \
         patch("gateway.app._non_stream_response", mock_llm):
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
    assert payload["model"] == "kitty-private"
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"] == "FULL_SYSTEM"


def test_chat_completions_non_stream_non_health_uses_route_model():
    mock_gsp = AsyncMock(return_value="SYS")
    fake = {"choices": [{"message": {"role": "assistant", "content": "hey"}}]}
    mock_llm = AsyncMock(return_value=fake)
    with patch("gateway.app.classify_domain", return_value="soul"), \
         patch("gateway.app.route_model", return_value="openrouter/test-model"), \
         patch("gateway.context_builder.get_system_prompt", mock_gsp), \
         patch("gateway.app._non_stream_response", mock_llm):
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
