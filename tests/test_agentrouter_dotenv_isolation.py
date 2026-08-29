from unittest.mock import patch


def test_generic_provider_dotenv_reload_does_not_cache_agentrouter_key(monkeypatch):
    """A generic provider refresh must not turn a removed AgentRouter dotenv key into process state."""
    import os

    from gateway import llm_client

    monkeypatch.delenv("AGENT_ROUTER_TOKEN", raising=False)
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)

    def fake_load_dotenv(*_args, **_kwargs):
        os.environ.setdefault("AGENT_ROUTER_TOKEN", "stale-dotenv-key")
        return True

    monkeypatch.setattr(llm_client, "load_dotenv", fake_load_dotenv)
    monkeypatch.setattr(llm_client, "_resolve_provider_api_key", lambda _envs: "")

    with patch("gateway.llm_client._post") as post:
        result = llm_client._call_provider(
            llm_client.PROVIDERS["openai"],
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=10,
            temperature=0.0,
            timeout=1,
        )

    assert result == ""
    post.assert_not_called()
    assert "AGENT_ROUTER_TOKEN" not in os.environ
    assert "AGENTROUTER_API_KEY" not in os.environ
