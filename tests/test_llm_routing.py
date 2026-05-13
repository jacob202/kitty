"""Unit tests for the model router (LiteLLM virtual ids sent to the local proxy)."""
import os
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
    with patch("gateway.llm_client._is_offline", return_value=True), \
         patch.dict(os.environ, {"KITTY_DISABLE_LOCAL": ""}, clear=False):
        assert route_model("Use your best model for this important decision") == "mlx-local"


def test_disable_local_skips_offline_routing():
    with patch("gateway.llm_client._is_offline", return_value=True), \
         patch.dict(os.environ, {"KITTY_DISABLE_LOCAL": "1"}):
        result = route_model("Use your best model for this important decision")
        assert result == "kitty-smart"


def test_litellm_fallback_prefers_agentrouter_before_openrouter():
    """When LiteLLM is down, AgentRouter should be tried before OpenRouter."""
    with patch("gateway.llm_client.requests.post", side_effect=requests.RequestException("down")), \
         patch("gateway.llm_client._call_agentrouter_direct", return_value="agentrouter"), \
         patch("gateway.llm_client._call_openrouter_direct", return_value="openrouter"), \
         patch("gateway.llm_client._call_gemini_direct", return_value="gemini"), \
         patch("gateway.llm_client._call_nvidia_direct", return_value="nvidia"):
        result = call_llm([{"role": "user", "content": "hello"}], model="kitty-default")

    assert result == "agentrouter"


def test_disable_agentrouter_env_skips_agentrouter_fallback(monkeypatch):
    monkeypatch.setenv("KITTY_DISABLE_AGENTROUTER", "1")
    with patch("gateway.llm_client.requests.post", side_effect=requests.RequestException("down")), \
         patch("gateway.llm_client._call_agentrouter_direct", return_value="agentrouter") as mock_agent, \
         patch("gateway.llm_client._call_openrouter_direct", return_value="openrouter") as mock_openrouter, \
         patch("gateway.llm_client._call_gemini_direct", return_value="gemini"), \
         patch("gateway.llm_client._call_nvidia_direct", return_value="nvidia"):
        result = call_llm([{"role": "user", "content": "hello"}], model="kitty-default")

    assert result == "openrouter"
    mock_agent.assert_not_called()
    mock_openrouter.assert_called_once()
