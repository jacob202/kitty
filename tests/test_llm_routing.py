"""Unit tests for the model router (LiteLLM virtual ids sent to the local proxy)."""
from unittest.mock import patch

import requests

from gateway.llm_client import call_llm, route_model


def test_default_routes_to_kitty_default():
    with patch("gateway.llm_client._is_offline", return_value=False):
        assert route_model("What should I have for breakfast?") == "kitty-default"


def test_reasoning_keyword_routes_to_kitty_agent():
    with patch("gateway.llm_client._is_offline", return_value=False):
        result = route_model("Can you explain why the sky is blue?")
    assert result == "kitty-agent"


def test_analyze_keyword_routes_to_kitty_agent():
    with patch("gateway.llm_client._is_offline", return_value=False):
        result = route_model("Analyze the pros and cons of this approach")
    assert result == "kitty-agent"


def test_best_trigger_routes_to_kitty_smart():
    with patch("gateway.llm_client._is_offline", return_value=False):
        result = route_model("Use your best model for this important decision")
    assert result == "kitty-smart"


def test_use_claude_routes_to_kitty_smart():
    with patch("gateway.llm_client._is_offline", return_value=False):
        result = route_model("Use claude for this")
    assert result == "kitty-smart"


def test_offline_routes_to_local_model():
    with patch("gateway.llm_client._is_offline", return_value=True):
        assert route_model("Use your best model for this important decision") == "mlx-local"


def test_litellm_fallback_prefers_openrouter_before_agentrouter():
    """When LiteLLM is down, OpenRouter should be tried before AgentRouter."""
    with patch("gateway.llm_client.requests.post", side_effect=requests.RequestException("down")), \
         patch("gateway.llm_client._call_openrouter_direct", return_value="openrouter"), \
         patch("gateway.llm_client._call_gemini_direct", return_value="gemini"), \
         patch("gateway.llm_client._call_agentrouter_direct", return_value="agentrouter"), \
         patch("gateway.llm_client._call_nvidia_direct", return_value="nvidia"):
        result = call_llm([{"role": "user", "content": "hello"}], model="kitty-default")

    assert result == "openrouter"
