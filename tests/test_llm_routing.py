"""Unit tests for the model router (LiteLLM virtual ids sent to the proxy)."""
from unittest.mock import patch

from gateway.llm_client import call_llm, route_model


def test_default_routes_to_kitty_default():
    assert route_model("What should I have for breakfast?") == "kitty-default"


def test_route_model_sends_reasoning_to_sonnet():
    assert route_model("Can you explain why the sky is blue?") == "kitty-sonnet"
    assert route_model("Analyze the pros and cons of this approach") == "kitty-sonnet"
    assert route_model("Use your best model for this important decision") == "kitty-sonnet"
    assert route_model("Use claude for this") == "kitty-sonnet"


def test_litellm_fallback_prefers_openai_before_other_providers():
    """When LiteLLM is down, OpenAI is tried before the other provider lanes."""
    with patch("gateway.llm_client._post", side_effect=Exception("down")), \
         patch(
             "gateway.llm_client._call_provider",
             side_effect=lambda provider, *args, **kwargs: provider.name,
         ):
        result = call_llm([{"role": "user", "content": "hello"}], model="kitty-default")

    assert result == "openai"


def test_disable_agentrouter_env_skips_agentrouter_fallback(monkeypatch):
    monkeypatch.setenv("KITTY_DISABLE_AGENTROUTER", "1")
    called = []

    def fake_provider(provider, *args, **kwargs):
        called.append(provider.name)
        return "" if provider.name == "openai" else provider.name

    with patch("gateway.llm_client._post", side_effect=Exception("down")), \
         patch("gateway.llm_client._call_provider", side_effect=fake_provider):
        result = call_llm([{"role": "user", "content": "hello"}], model="kitty-default")

    assert result == "nvidia"
    # openai is tried first (returns ""), agentrouter is skipped, nvidia wins.
    assert called == ["openai", "nvidia"]


def test_call_llm_normalizes_legacy_deepseek_alias():
    from unittest.mock import MagicMock

    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        "model": "kitty-default",
    }
    with patch("gateway.llm_client.httpx.post", return_value=mock_response) as mock_post:
        result = call_llm(
            [{"role": "user", "content": "hello"}],
            model="deepseek/deepseek-v4-flash",
        )

    assert result == "ok"
    assert mock_post.call_args.kwargs["json"]["model"] == "kitty-default"
