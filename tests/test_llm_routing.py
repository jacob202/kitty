"""Unit tests for the model router (LiteLLM virtual ids sent to the proxy)."""
from unittest.mock import patch

import requests

from gateway.llm_client import call_llm, route_model


def test_default_routes_to_kitty_default():
    assert route_model("What should I have for breakfast?") == "kitty-default"


def test_route_model_sends_reasoning_to_sonnet():
    assert route_model("Can you explain why the sky is blue?") == "kitty-sonnet"
    assert route_model("Analyze the pros and cons of this approach") == "kitty-sonnet"
    assert route_model("Use your best model for this important decision") == "kitty-sonnet"
    assert route_model("Use claude for this") == "kitty-sonnet"


def test_litellm_fallback_prefers_openai_before_other_providers():
    """When LiteLLM is down, OpenAI should be tried before the dead provider lanes."""
    with patch("gateway.llm_client.requests.post", side_effect=requests.RequestException("down")), \
         patch("gateway.llm_client._call_openai_direct", return_value="openai"), \
         patch("gateway.llm_client._call_nvidia_direct", return_value="nvidia"), \
         patch("gateway.llm_client._call_agentrouter_direct", return_value="agentrouter"), \
         patch("gateway.llm_client._call_openrouter_direct", return_value="openrouter"), \
         patch("gateway.llm_client._call_gemini_direct", return_value="gemini"):
        result = call_llm([{"role": "user", "content": "hello"}], model="kitty-default")

    assert result == "openai"


def test_disable_agentrouter_env_skips_agentrouter_fallback(monkeypatch):
    monkeypatch.setenv("KITTY_DISABLE_AGENTROUTER", "1")
    with patch("gateway.llm_client.requests.post", side_effect=requests.RequestException("down")), \
         patch("gateway.llm_client._call_openai_direct", return_value=""), \
         patch("gateway.llm_client._call_nvidia_direct", return_value="nvidia") as mock_nvidia, \
         patch("gateway.llm_client._call_agentrouter_direct", return_value="agentrouter") as mock_agent, \
         patch("gateway.llm_client._call_openrouter_direct", return_value="openrouter") as mock_openrouter, \
         patch("gateway.llm_client._call_gemini_direct", return_value="gemini"):
        result = call_llm([{"role": "user", "content": "hello"}], model="kitty-default")

    assert result == "nvidia"
    mock_nvidia.assert_called_once()
    mock_agent.assert_not_called()
    mock_openrouter.assert_not_called()


def test_call_llm_normalizes_legacy_deepseek_alias():
    mock_response = type(
        "Resp",
        (),
        {
            "status_code": 200,
            "reason": "OK",
            "raise_for_status": lambda self: None,
            "json": lambda self: {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "model": "kitty-default",
            },
        },
    )()
    with patch("gateway.llm_client.requests.post", return_value=mock_response) as mock_post:
        result = call_llm(
            [{"role": "user", "content": "hello"}],
            model="deepseek/deepseek-v4-flash",
        )

    assert result == "ok"
    assert mock_post.call_args.kwargs["json"]["model"] == "kitty-default"
