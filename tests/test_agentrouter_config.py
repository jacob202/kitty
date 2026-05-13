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


@pytest.fixture
def clear_agentrouter_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "KITTY_AGENTROUTER_MODEL_DEFAULT",
        "KITTY_AGENTROUTER_MODEL_AGENT",
        "KITTY_AGENTROUTER_MODEL_SMART",
        "KITTY_AGENTROUTER_MODEL_PARTS",
        "KITTY_AGENTROUTER_CHAT_MODEL",
        "AGENTROUTER_MODEL",
        "KITTY_AGENTROUTER_CODING_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_agentrouter_model_defaults(clear_agentrouter_model_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    assert lc.agentrouter_model_for_request("kitty-default") == "gpt-5.4-mini"
    assert lc.agentrouter_model_for_request("kitty-agent") == "gpt-5.1-codex-mini"
    assert lc.agentrouter_model_for_request("kitty-smart") == "gpt-5.5"


def test_chat_env_does_not_override_coding_or_smart(
    clear_agentrouter_model_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KITTY_AGENTROUTER_CHAT_MODEL", "only-chat")
    assert lc.agentrouter_model_for_request("kitty-default") == "only-chat"
    assert lc.agentrouter_model_for_request("kitty-agent") == "gpt-5.1-codex-mini"
    assert lc.agentrouter_model_for_request("kitty-smart") == "gpt-5.5"


def test_coding_env_overrides_builtin(clear_agentrouter_model_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITTY_AGENTROUTER_CODING_MODEL", "custom-coder")
    assert lc.agentrouter_model_for_request("kitty-agent") == "custom-coder"


def test_agentrouter_model_per_tier(clear_agentrouter_model_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITTY_AGENTROUTER_MODEL_DEFAULT", "model-a")
    monkeypatch.setenv("KITTY_AGENTROUTER_MODEL_AGENT", "model-b")
    monkeypatch.setenv("KITTY_AGENTROUTER_MODEL_SMART", "model-c")
    assert lc.agentrouter_model_for_request("kitty-default") == "model-a"
    assert lc.agentrouter_model_for_request("kitty-agent") == "model-b"
    assert lc.agentrouter_model_for_request("kitty-smart") == "model-c"


def test_agentrouter_model_explicit_passthrough(clear_agentrouter_model_env: None) -> None:
    assert lc.agentrouter_model_for_request("glm-4.6") == "glm-4.6"


def test_agentrouter_model_global_fallback_overrides_tier(
    clear_agentrouter_model_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KITTY_AGENTROUTER_CHAT_MODEL", "from-chat-env")
    assert lc.agentrouter_model_for_request("kitty-default") == "from-chat-env"


def test_resolve_agentrouter_key_order_and_strip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_ROUTER_TOKEN", raising=False)
    monkeypatch.setenv("AGENTROUTER_API_KEY", '  "sk-primary"  ')
    assert lc.resolve_agentrouter_api_key() == "sk-primary"

    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    monkeypatch.setenv("AGENT_ROUTER_TOKEN", "sk-token")
    assert lc.resolve_agentrouter_api_key() == "sk-token"
