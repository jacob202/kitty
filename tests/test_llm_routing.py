"""Unit tests for the 2-decision model router."""
from gateway.llm_client import route_model


def test_default_routes_to_qwen():
    assert route_model("What should I have for breakfast?") == "kitty-default"


def test_reasoning_keyword_routes_to_deepseek():
    result = route_model("Can you explain why the sky is blue?")
    assert result == "kitty-agent"


def test_analyze_keyword_routes_to_deepseek():
    result = route_model("Analyze the pros and cons of this approach")
    assert result == "kitty-agent"


def test_best_trigger_routes_to_claude():
    result = route_model("Use your best model for this important decision")
    assert result == "kitty-smart"


def test_use_claude_routes_to_claude():
    result = route_model("Use claude for this")
    assert result == "kitty-smart"
