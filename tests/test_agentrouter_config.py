"""Pure config helpers for AgentRouter (no network)."""

import pytest

from gateway import llm_client as lc


@pytest.fixture(autouse=True)
def _no_dotenv_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent real ``.env`` from overriding monkeypatched values in these unit tests."""
    monkeypatch.setattr("gateway.llm_client.load_dotenv", lambda *a, **k: None)


def test_normalize_agentrouter_api_base_appends_v1() -> None:
    assert lc.normalize_agentrouter_api_base("https://agentrouter.org") == "https://agentrouter.org/v1"
    assert lc.normalize_agentrouter_api_base("https://agentrouter.org/v1") == "https://agentrouter.org/v1"
    assert lc.normalize_agentrouter_api_base("https://agentrouter.org/v1/") == "https://agentrouter.org/v1"


def test_agentrouter_model_defaults(clear_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    assert lc.agentrouter_model_for_request("kitty-default") == "gpt-5.4-mini"


def test_agentrouter_model_override(clear_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTROUTER_MODEL", "custom-router-model")
    assert lc.agentrouter_model_for_request("kitty-default") == "custom-router-model"


def test_openrouter_kitty_model_does_not_override_agentrouter_model(
    clear_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KITTY_MODEL", "deepseek/deepseek-v4-flash")
    assert lc.agentrouter_model_for_request("kitty-default") == "gpt-5.4-mini"


def test_agentrouter_model_explicit_passthrough(clear_env: None) -> None:
    assert lc.agentrouter_model_for_request("gpt-4o") == "gpt-4o"


@pytest.fixture
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "AGENTROUTER_MODEL",
        "KITTY_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_resolve_agentrouter_key_order_and_strip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_ROUTER_TOKEN", raising=False)
    monkeypatch.setenv("AGENTROUTER_API_KEY", '  "sk-primary"  ')
    assert lc.resolve_agentrouter_api_key() == "sk-primary"

    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    monkeypatch.setenv("AGENT_ROUTER_TOKEN", "sk-token")
    assert lc.resolve_agentrouter_api_key() == "sk-token"


def test_normalize_litellm_request_model_maps_legacy_routes_to_single_route() -> None:
    assert lc.normalize_litellm_request_model("kitty-smart") == "kitty-default"
    assert lc.normalize_litellm_request_model("kitty-agent") == "kitty-default"
    assert lc.normalize_litellm_request_model("kitty-fallback-or") == "kitty-default"


def test_normalize_litellm_request_model_passthrough_for_explicit_ids() -> None:
    assert lc.normalize_litellm_request_model("openrouter/test-model") == "openrouter/test-model"
