"""Tests for gateway/llm_client.py — model routing and normalization helpers."""
import pytest
from unittest.mock import patch, MagicMock


# ── normalize_litellm_request_model ──────────────────────────────────────────

def test_normalize_none_returns_none():
    from gateway.llm_client import normalize_litellm_request_model
    assert normalize_litellm_request_model(None) is None


def test_normalize_empty_string():
    from gateway.llm_client import normalize_litellm_request_model
    assert normalize_litellm_request_model("") == ""


def test_normalize_legacy_kitty_agent():
    from gateway.llm_client import normalize_litellm_request_model
    result = normalize_litellm_request_model("kitty-agent")
    assert result == "kitty-default"


def test_normalize_legacy_kitty_smart():
    from gateway.llm_client import normalize_litellm_request_model
    result = normalize_litellm_request_model("kitty-smart")
    assert result == "kitty-default"


def test_normalize_legacy_deepseek():
    from gateway.llm_client import normalize_litellm_request_model
    result = normalize_litellm_request_model("deepseek/deepseek-chat")
    assert result == "kitty-default"


def test_normalize_unknown_passthrough():
    """Unknown model IDs are passed through unchanged."""
    from gateway.llm_client import normalize_litellm_request_model
    result = normalize_litellm_request_model("anthropic/claude-3-opus")
    assert result == "anthropic/claude-3-opus"


def test_normalize_strips_whitespace():
    from gateway.llm_client import normalize_litellm_request_model
    result = normalize_litellm_request_model("  kitty-default  ")
    assert result == "kitty-default"


# ── normalize_agentrouter_api_base ───────────────────────────────────────────

def test_agentrouter_base_adds_v1():
    from gateway.llm_client import normalize_agentrouter_api_base
    result = normalize_agentrouter_api_base("https://agentrouter.org")
    assert result == "https://agentrouter.org/v1"


def test_agentrouter_base_no_double_v1():
    from gateway.llm_client import normalize_agentrouter_api_base
    result = normalize_agentrouter_api_base("https://agentrouter.org/v1")
    assert result == "https://agentrouter.org/v1"


def test_agentrouter_base_strips_trailing_slash():
    from gateway.llm_client import normalize_agentrouter_api_base
    result = normalize_agentrouter_api_base("https://agentrouter.org/v1/")
    assert result == "https://agentrouter.org/v1"


def test_agentrouter_base_none_returns_default():
    from gateway.llm_client import normalize_agentrouter_api_base
    result = normalize_agentrouter_api_base(None)
    assert result == "https://agentrouter.org/v1"


# ── _sanitize_agentrouter_model_id ───────────────────────────────────────────

def test_sanitize_plain_model():
    from gateway.llm_client import _sanitize_agentrouter_model_id
    assert _sanitize_agentrouter_model_id("gpt-4o") == "gpt-4o"


def test_sanitize_strips_quotes():
    from gateway.llm_client import _sanitize_agentrouter_model_id
    assert _sanitize_agentrouter_model_id('"gpt-4o"') == "gpt-4o"


def test_sanitize_rejects_concatenated_key():
    """Detects 'model sk-...' concatenation in .env and uses only model part."""
    from gateway.llm_client import _sanitize_agentrouter_model_id
    result = _sanitize_agentrouter_model_id("gpt-4o sk-abc123xyz")
    assert result == "gpt-4o"


# ── route_model ───────────────────────────────────────────────────────────────

def test_route_model_default():
    """Generic messages go to kitty-default."""
    from gateway.llm_client import route_model
    assert route_model("what's the weather like?") == "kitty-default"


def test_route_model_reasoning_keyword():
    """Messages with reasoning keywords go to kitty-sonnet."""
    from gateway.llm_client import route_model
    assert route_model("explain how recursion works") == "kitty-sonnet"


def test_route_model_best_trigger():
    """'Use your best model' triggers sonnet routing."""
    from gateway.llm_client import route_model
    assert route_model("use your best model for this") == "kitty-sonnet"


def test_route_model_analyze():
    from gateway.llm_client import route_model
    assert route_model("analyze this codebase") == "kitty-sonnet"


def test_route_model_why():
    from gateway.llm_client import route_model
    assert route_model("why does this error happen?") == "kitty-sonnet"


def test_route_model_step_by_step():
    from gateway.llm_client import route_model
    assert route_model("walk me through this step by step") == "kitty-sonnet"


def test_route_model_case_insensitive():
    from gateway.llm_client import route_model
    assert route_model("EXPLAIN THIS TO ME") == "kitty-sonnet"
    assert route_model("WHAT IS THIS") == "kitty-default"


# ── resolve_agentrouter_api_key ───────────────────────────────────────────────
# load_dotenv(override=True) inside the function would overwrite patched env vars
# from a real .env file, so we stub it out in all these tests.

def test_resolve_agentrouter_key_from_env():
    from gateway.llm_client import resolve_agentrouter_api_key
    with patch("gateway.llm_client.load_dotenv"), \
         patch.dict("os.environ", {"AGENTROUTER_API_KEY": "sk-test-key"}):
        key = resolve_agentrouter_api_key()
    assert key == "sk-test-key"


def test_resolve_agentrouter_key_strips_quotes():
    from gateway.llm_client import resolve_agentrouter_api_key
    with patch("gateway.llm_client.load_dotenv"), \
         patch.dict("os.environ", {"AGENTROUTER_API_KEY": '"sk-test-key"'}):
        key = resolve_agentrouter_api_key()
    assert key == "sk-test-key"


def test_resolve_agentrouter_key_multiline_uses_first():
    """Multi-line key uses only the first line."""
    from gateway.llm_client import resolve_agentrouter_api_key
    with patch("gateway.llm_client.load_dotenv"), \
         patch.dict("os.environ", {"AGENTROUTER_API_KEY": "sk-line1\nsk-line2"}):
        key = resolve_agentrouter_api_key()
    assert key == "sk-line1"


def test_resolve_agentrouter_key_missing_returns_empty():
    from gateway.llm_client import resolve_agentrouter_api_key
    with patch("gateway.llm_client.load_dotenv"), \
         patch.dict("os.environ", {}, clear=True):
        import os
        os.environ.pop("AGENTROUTER_API_KEY", None)
        os.environ.pop("AGENT_ROUTER_TOKEN", None)
        key = resolve_agentrouter_api_key()
    assert key == ""


# ── call_llm integration (mocked network) ────────────────────────────────────

def test_call_llm_returns_content_on_success():
    """call_llm extracts message content from a well-formed LiteLLM response."""
    from gateway.llm_client import call_llm

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Hello, Jacob."}}],
        "model": "kitty-default",
    }
    with patch("requests.post", return_value=fake_response):
        result = call_llm(
            messages=[{"role": "user", "content": "hello"}],
            model="kitty-default",
        )
    assert result == "Hello, Jacob."


def test_call_llm_falls_back_on_litellm_error():
    """call_llm falls back gracefully when LiteLLM connection is refused."""
    from gateway.llm_client import call_llm
    import requests as req

    with patch("requests.post", side_effect=req.exceptions.ConnectionError("refused")):
        with patch("gateway.llm_client._call_openrouter_direct", return_value="Fallback response"):
            result = call_llm(
                messages=[{"role": "user", "content": "hello"}],
                model="kitty-default",
            )
    assert result == "Fallback response"
