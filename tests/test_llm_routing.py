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


def test_litellm_fallback_prefers_local_before_the_cloud_lanes(all_provider_keys):
    """When LiteLLM is down, the local MLX server is tried before any cloud lane.

    It costs nothing and needs no credit, so paying OpenAI to answer "hi" only
    makes sense once local has declined.
    """
    with patch("gateway.llm_client._post", side_effect=Exception("down")), \
         patch(
             "gateway.llm_client._call_provider",
             side_effect=lambda provider, *args, **kwargs: provider.name,
         ):
        result = call_llm([{"role": "user", "content": "hello"}], model="kitty-default")

    assert result == "local"


def test_openai_leads_the_cloud_lanes(all_provider_keys):
    """Once local declines, OpenAI is the first paid lane tried."""
    def fake_provider(provider, *args, **kwargs):
        return "" if provider.name == "local" else provider.name

    with patch("gateway.llm_client._post", side_effect=Exception("down")), \
         patch("gateway.llm_client._call_provider", side_effect=fake_provider):
        result = call_llm([{"role": "user", "content": "hello"}], model="kitty-default")

    assert result == "openai"


def test_disable_agentrouter_env_skips_agentrouter_fallback(monkeypatch, all_provider_keys):
    monkeypatch.setenv("KITTY_DISABLE_AGENTROUTER", "1")
    called = []

    def fake_provider(provider, *args, **kwargs):
        called.append(provider.name)
        return "" if provider.name in ("local", "openai") else provider.name

    with patch("gateway.llm_client._post", side_effect=Exception("down")), \
         patch("gateway.llm_client._call_provider", side_effect=fake_provider):
        result = call_llm([{"role": "user", "content": "hello"}], model="kitty-default")

    assert result == "nvidia"
    # local then openai decline, agentrouter is skipped by the kill switch, nvidia wins.
    assert called == ["local", "openai", "nvidia"]


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


def test_route_model_kitty_reasoning_model_override(monkeypatch):
    """KITTY_REASONING_MODEL env var overrides the deep-tier alias."""
    monkeypatch.setenv("KITTY_REASONING_MODEL", "anthropic/claude-sonnet-4")
    assert route_model("explain quantum physics") == "anthropic/claude-sonnet-4"

    monkeypatch.delenv("KITTY_REASONING_MODEL")
    assert route_model("explain quantum physics") == "kitty-sonnet"
