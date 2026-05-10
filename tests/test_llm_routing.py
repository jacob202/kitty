"""Unit tests for the 3-decision model router."""
from unittest.mock import patch

from gateway.llm_client import route_model


def test_default_routes_to_qwen():
    with patch("gateway.llm_client._is_offline", return_value=False):
        assert route_model("What should I have for breakfast?") == "qwen/qwen3-235b-a22b:free"


def test_reasoning_keyword_routes_to_deepseek():
    with patch("gateway.llm_client._is_offline", return_value=False):
        result = route_model("Can you explain why the sky is blue?")
    assert result == "deepseek/deepseek-r1-0528"


def test_analyze_keyword_routes_to_deepseek():
    with patch("gateway.llm_client._is_offline", return_value=False):
        result = route_model("Analyze the pros and cons of this approach")
    assert result == "deepseek/deepseek-r1-0528"


def test_best_trigger_routes_to_claude():
    with patch("gateway.llm_client._is_offline", return_value=False):
        result = route_model("Use your best model for this important decision")
    assert result == "claude-sonnet-4-6"


def test_use_claude_routes_to_claude():
    with patch("gateway.llm_client._is_offline", return_value=False):
        result = route_model("Use claude for this")
    assert result == "claude-sonnet-4-6"


def test_offline_routes_to_local():
    with patch("gateway.llm_client._is_offline", return_value=True):
        result = route_model("Anything at all")
    assert result == "mlx-local"


def test_offline_checked_first():
    """Offline status beats best/reasoning triggers."""
    with patch("gateway.llm_client._is_offline", return_value=True):
        result = route_model("Use your best model and explain why")
    assert result == "mlx-local"
