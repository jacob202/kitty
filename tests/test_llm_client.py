"""Tests for gateway/llm_client.py — model routing and normalization helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ── _post retry policy ───────────────────────────────────────────────────────


def test_post_retries_server_errors():
    from gateway.llm_client import _post

    unavailable = MagicMock(status_code=503)
    recovered = MagicMock(status_code=200)

    with patch("gateway.llm_client.httpx.post", side_effect=[unavailable, recovered]) as mock_post:
        result = _post("https://example.test/chat")

    assert result is recovered
    assert mock_post.call_count == 2


def test_post_does_not_retry_client_errors():
    from gateway.llm_client import _post

    unauthorized = MagicMock(status_code=401)

    with patch("gateway.llm_client.httpx.post", return_value=unauthorized) as mock_post:
        result = _post("https://example.test/chat")

    assert result is unauthorized
    assert mock_post.call_count == 1


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

    with (
        patch("gateway.llm_client.load_dotenv"),
        patch.dict("os.environ", {"AGENTROUTER_API_KEY": "sk-test-key"}),
    ):
        key = resolve_agentrouter_api_key()
    assert key == "sk-test-key"


def test_resolve_agentrouter_key_strips_quotes():
    from gateway.llm_client import resolve_agentrouter_api_key

    with (
        patch("gateway.llm_client.load_dotenv"),
        patch.dict("os.environ", {"AGENTROUTER_API_KEY": '"sk-test-key"'}),
    ):
        key = resolve_agentrouter_api_key()
    assert key == "sk-test-key"


def test_resolve_agentrouter_key_multiline_uses_first():
    """Multi-line key uses only the first line."""
    from gateway.llm_client import resolve_agentrouter_api_key

    with (
        patch("gateway.llm_client.load_dotenv"),
        patch.dict("os.environ", {"AGENTROUTER_API_KEY": "sk-line1\nsk-line2"}),
    ):
        key = resolve_agentrouter_api_key()
    assert key == "sk-line1"


def test_resolve_agentrouter_key_missing_returns_empty():
    from gateway.llm_client import resolve_agentrouter_api_key

    with patch("gateway.llm_client.load_dotenv"), patch.dict("os.environ", {}, clear=True):
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
    with patch("gateway.llm_client.httpx.post", return_value=fake_response):
        result = call_llm(
            messages=[{"role": "user", "content": "hello"}],
            model="kitty-default",
        )
    assert result == "Hello, Jacob."


def test_call_llm_falls_back_on_litellm_error():
    """call_llm falls back via the provider dispatcher when LiteLLM fails."""
    from gateway.llm_client import call_llm

    with (
        patch("gateway.llm_client._post", side_effect=Exception("litellm down")),
        patch("gateway.llm_client._call_provider", return_value="Fallback response"),
    ):
        result = call_llm(
            messages=[{"role": "user", "content": "hello"}],
            model="kitty-default",
        )
    assert result == "Fallback response"


# ── chat_completions_non_stream ───────────────────────────────────────────────


def test_chat_completions_non_stream_falls_back_on_http_failure():
    """Async LiteLLM failure triggers sync call_llm fallback."""
    import asyncio

    from gateway.llm_client import chat_completions_non_stream

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("connection refused"))

    async def run_test():
        with (
            patch(
                "gateway.http_client.get_http_client",
                new=AsyncMock(return_value=mock_client),
            ),
            patch("gateway.llm_client.call_llm", return_value="Fallback reply"),
        ):
            return await chat_completions_non_stream(
                {
                    "model": "kitty-default",
                    "messages": [{"role": "user", "content": "hello"}],
                }
            )

    result = asyncio.run(run_test())
    assert result["choices"][0]["message"]["content"] == "Fallback reply"
    assert result["model"] == "kitty-default"


# ── retry_with_backoff ────────────────────────────────────────────────────


def test_retry_with_backoff_429_triggers_retry():
    """429 rate-limit response triggers retry with backoff."""
    from gateway.llm_client import retry_with_backoff

    call_count = 0

    def _failing():
        nonlocal call_count
        call_count += 1
        resp = MagicMock(status_code=429)
        err = Exception("rate limited")
        err.response = resp
        raise err

    wrapped = retry_with_backoff(_failing, max_retries=2, base_delay=0.01, max_delay=0.1)
    with patch("gateway.llm_client.time.sleep"):
        with pytest.raises(Exception):
            wrapped()

    assert call_count == 3  # initial + 2 retries


def test_retry_with_backoff_non_429_re_raises():
    """Non-429 errors do not trigger retry."""
    from gateway.llm_client import retry_with_backoff

    call_count = 0

    def _failing():
        nonlocal call_count
        call_count += 1
        raise ValueError("auth error")

    wrapped = retry_with_backoff(_failing, max_retries=3, base_delay=0.01, max_delay=0.1)
    with patch("gateway.llm_client.time.sleep"):
        with pytest.raises(ValueError):
            wrapped()

    assert call_count == 1


def test_retry_with_backoff_max_retries_exhausted():
    """After max_retries of 429s, the last error is re-raised."""
    from gateway.llm_client import retry_with_backoff

    call_count = 0

    def _failing():
        nonlocal call_count
        call_count += 1
        resp = MagicMock(status_code=429)
        err = Exception("rate limited")
        err.response = resp
        raise err

    wrapped = retry_with_backoff(_failing, max_retries=1, base_delay=0.01, max_delay=0.1)
    with patch("gateway.llm_client.time.sleep"):
        with pytest.raises(Exception):
            wrapped()

    assert call_count == 2  # initial + 1 retry


# ── _call_provider edge cases ─────────────────────────────────────────────


def test_call_provider_empty_api_key_returns_empty():
    """Missing API key -> _call_provider returns '' without network call."""
    from gateway.llm_client import PROVIDERS, _call_provider

    with (
        patch("gateway.llm_client.load_dotenv"),
        patch("gateway.llm_client._resolve_provider_api_key", return_value=""),
    ):
        result = _call_provider(
            PROVIDERS["openai"],
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            temperature=0.7,
            timeout=10,
        )

    assert result == ""


def test_call_provider_non_success_response_returns_empty():
    """Provider returns non-2xx -> _call_provider returns ''."""
    from gateway.llm_client import PROVIDERS, _call_provider

    mock_resp = MagicMock()
    mock_resp.is_success = False
    mock_resp.status_code = 401
    mock_resp.text = "unauthorized"

    with (
        patch("gateway.llm_client.load_dotenv"),
        patch("gateway.llm_client._post", return_value=mock_resp),
        patch("gateway.llm_client._resolve_provider_api_key", return_value="sk-test"),
        patch("gateway.llm_client.log_llm_usage"),
    ):
        result = _call_provider(
            PROVIDERS["openai"],
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            temperature=0.7,
            timeout=10,
        )

    assert result == ""


def test_call_provider_exception_returns_empty():
    """Transport/network error -> _call_provider returns ''."""
    from gateway.llm_client import PROVIDERS, _call_provider

    with (
        patch("gateway.llm_client.load_dotenv"),
        patch("gateway.llm_client._post", side_effect=httpx.ConnectError("connection refused")),
        patch("gateway.llm_client._resolve_provider_api_key", return_value="sk-test"),
        patch("gateway.llm_client.log_llm_usage"),
    ):
        result = _call_provider(
            PROVIDERS["openai"],
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            temperature=0.7,
            timeout=10,
        )

    assert result == ""


def test_call_provider_success_path_with_response_format():
    """Successful _call_provider returns extracted text and includes response_format."""
    from gateway.llm_client import PROVIDERS, _call_provider

    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "  JSON output  "}}],
        "model": "gpt-4o-mini",
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }

    with (
        patch("gateway.llm_client.load_dotenv"),
        patch("gateway.llm_client._post", return_value=mock_resp) as mock_post,
        patch("gateway.llm_client._resolve_provider_api_key", return_value="sk-test"),
        patch("gateway.llm_client.log_llm_usage"),
    ):
        result = _call_provider(
            PROVIDERS["openai"],
            messages=[{"role": "user", "content": "give me json"}],
            max_tokens=100,
            temperature=0.7,
            timeout=10,
            response_format={"type": "json_object"},
        )

    assert result == "JSON output"
    # Verify response_format was included in the payload sent to _post
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["response_format"] == {"type": "json_object"}
    assert call_kwargs["json"]["model"] == "gpt-4o-mini"


# ── call_llm fallback exhaustion ──────────────────────────────────────────


def test_call_llm_passes_response_format_to_litellm():
    """call_llm includes response_format in the LiteLLM payload when provided."""
    from gateway.llm_client import call_llm

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "json"}}],
        "model": "kitty-default",
    }
    with (
        patch("gateway.llm_client.httpx.post", return_value=fake_response) as mock_post,
        patch("gateway.llm_client.log_llm_usage"),
    ):
        result = call_llm(
            messages=[{"role": "user", "content": "give json"}],
            model="kitty-default",
            response_format={"type": "json_object"},
        )
    assert result == "json"
    assert mock_post.call_args.kwargs["json"]["response_format"] == {"type": "json_object"}


def test_call_llm_full_fallback_exhaustion_raises_chain_exhausted():
    """All providers in the fallback chain fail -> call_llm raises ProviderChainExhausted."""
    from gateway.llm_client import ProviderChainExhausted, call_llm

    with (
        patch("gateway.llm_client._post", side_effect=Exception("litellm down")),
        patch("gateway.llm_client._call_provider", return_value=""),
    ):
        with pytest.raises(ProviderChainExhausted) as excinfo:
            call_llm(
                [{"role": "user", "content": "hello"}],
                model="kitty-default",
            )

    assert excinfo.value.errors[0].startswith("litellm:")
    assert any("no response" in e for e in excinfo.value.errors)


def test_call_llm_partial_fallback_second_provider_succeeds():
    """First provider fails, second provider succeeds."""
    from gateway.llm_client import call_llm

    call_count = [0]

    def _fake_provider(*args, **kwargs):
        call_count[0] += 1
        return "" if call_count[0] == 1 else "second provider response"

    with (
        patch("gateway.llm_client._post", side_effect=Exception("litellm down")),
        patch("gateway.llm_client._call_provider", side_effect=_fake_provider),
    ):
        result = call_llm(
            [{"role": "user", "content": "hello"}],
            model="kitty-default",
        )

    assert result == "second provider response"
    assert call_count[0] == 2


def test_call_llm_fallback_deadline_exhausted():
    """When deadline budget is already consumed, call_llm raises ProviderChainExhausted."""
    from gateway.llm_client import ProviderChainExhausted, call_llm

    with (
        patch("gateway.llm_client._post", side_effect=Exception("litellm down")),
        patch("gateway.llm_client._LLM_CHAIN_DEADLINE", -1.0),
    ):
        with pytest.raises(ProviderChainExhausted) as excinfo:
            call_llm(
                [{"role": "user", "content": "hello"}],
                model="kitty-default",
            )

    assert any("deadline" in e for e in excinfo.value.errors)


# ── extract_assistant_text ────────────────────────────────────────────────


def test_extract_assistant_text_normal():
    from gateway.llm_client import extract_assistant_text

    data = {"choices": [{"message": {"content": "Hello!"}}]}
    assert extract_assistant_text(data) == "Hello!"


def test_extract_assistant_text_non_dict():
    from gateway.llm_client import extract_assistant_text

    assert extract_assistant_text("not a dict") == ""
    assert extract_assistant_text(None) == ""
    assert extract_assistant_text(42) == ""


def test_extract_assistant_text_missing_keys():
    from gateway.llm_client import extract_assistant_text

    assert extract_assistant_text({}) == ""
    assert extract_assistant_text({"choices": []}) == ""
    assert extract_assistant_text({"choices": [{}]}) == ""
    assert extract_assistant_text({"choices": [{"message": {}}]}) == ""
    assert extract_assistant_text({"choices": [{"message": {"content": None}}]}) == ""
    assert extract_assistant_text({"choices": [{"message": {"content": 42}}]}) == ""
    assert extract_assistant_text({"choices": [{"message": 42}]}) == ""


# ── _finalize_openai_shape_response ───────────────────────────────────────


def test_finalize_openai_shape_response_normal():
    """Well-formed response returns trimmed content and calls log_llm_usage."""
    from gateway.llm_client import _finalize_openai_shape_response

    data = {
        "choices": [{"message": {"content": "  Hello, world.  "}}],
        "model": "gpt-4o",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    with patch("gateway.llm_client.log_llm_usage") as mock_log:
        result = _finalize_openai_shape_response(
            data,
            provider="openai",
            model_logged="gpt-4o",
            operation="llm.call",
            route="openai_direct",
            request_model=None,
            metadata={"key": "val"},
        )

    assert result == "Hello, world."
    mock_log.assert_called_once()


def test_finalize_openai_shape_response_malformed():
    """Missing choices or malformed structure returns ''."""
    from gateway.llm_client import _finalize_openai_shape_response

    with patch("gateway.llm_client.log_llm_usage"):
        result = _finalize_openai_shape_response(
            {},
            provider="openai",
            model_logged="gpt-4o",
            operation="llm.call",
            route="openai_direct",
            request_model="test-model",
            metadata=None,
        )

    assert result == ""


# ── chat wrapper + observability ──────────────────────────────────────────


def test_chat_calls_call_llm_with_expected_args():
    """chat() delegates to call_llm with correct args inside record_chat context."""
    from gateway.llm_client import chat

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
    mock_ctx.__exit__ = MagicMock(return_value=None)

    with (
        patch("gateway.observability.record_chat", return_value=mock_ctx) as mock_record,
        patch("gateway.llm_client.call_llm", return_value="chat response") as mock_call,
    ):
        result = chat("kitty-default", [{"role": "user", "content": "hi"}], max_tokens=100, temperature=0.5)

    assert result == "chat response"
    mock_record.assert_called_once_with("kitty-default", operation="llm.chat")
    mock_call.assert_called_once_with(
        [{"role": "user", "content": "hi"}],
        model="kitty-default",
        max_tokens=100,
        temperature=0.5,
    )


# ── _resolve_provider_api_key ─────────────────────────────────────────────


def test_resolve_provider_api_key_found():
    from gateway.llm_client import _resolve_provider_api_key

    with patch.dict("os.environ", {"TEST_KEY": "sk-found"}):
        result = _resolve_provider_api_key(("TEST_KEY",))

    assert result == "sk-found"


def test_resolve_provider_api_key_missing():
    from gateway.llm_client import _resolve_provider_api_key

    with patch.dict("os.environ", {}, clear=True):
        result = _resolve_provider_api_key(("TEST_KEY",))

    assert result == ""


def test_resolve_provider_api_key_strips_quotes():
    from gateway.llm_client import _resolve_provider_api_key

    with patch.dict("os.environ", {"TEST_KEY": '"sk-quoted"'}):
        result = _resolve_provider_api_key(("TEST_KEY",))

    assert result == "sk-quoted"


# ── agentrouter_model_for_request ──────────────────────────────────────────


def test_agentrouter_model_for_request_explicit_model():
    """Explicit non-default model is returned directly (sanitized)."""
    from gateway.llm_client import agentrouter_model_for_request

    with patch("gateway.llm_client.load_dotenv"):
        result = agentrouter_model_for_request("anthropic/claude-opus-4")
    assert result == "anthropic/claude-opus-4"


def test_agentrouter_model_for_request_default_reads_env():
    """No explicit model -> reads AGENTROUTER_MODEL env or uses hardcoded default."""
    from gateway.llm_client import agentrouter_model_for_request

    with (
        patch("gateway.llm_client.load_dotenv"),
        patch.dict("os.environ", {"AGENTROUTER_MODEL": "env-model"}, clear=True),
    ):
        result = agentrouter_model_for_request("kitty-default")
    assert result == "env-model"


# ── _openrouter_fallback_model ────────────────────────────────────────────


def test_openrouter_fallback_model_uses_env():
    """KITTY_OPENROUTER_DIRECT_MODEL overrides the default mapping."""
    from gateway.llm_client import _openrouter_fallback_model

    with patch.dict("os.environ", {"KITTY_OPENROUTER_DIRECT_MODEL": "custom-model"}, clear=True):
        result = _openrouter_fallback_model("any-model")
    assert result == "custom-model"


def test_openrouter_fallback_model_falls_back_to_map():
    """No env set -> uses _LITELLM_TO_OPENROUTER mapping or passes through."""
    from gateway.llm_client import _openrouter_fallback_model

    with patch.dict("os.environ", {}, clear=True):
        result = _openrouter_fallback_model("kitty-default")
    assert result == "deepseek/deepseek-v4-flash"

    with patch.dict("os.environ", {}, clear=True):
        result = _openrouter_fallback_model("unknown-model")
    assert result == "unknown-model"


# ── _resolve_provider_model ───────────────────────────────────────────────


def test_resolve_provider_model_with_resolver():
    """model_resolver callback takes priority."""
    from unittest.mock import MagicMock

    from gateway.llm_client import _resolve_provider_model

    provider = MagicMock()
    provider.model_resolver = lambda rm: "resolved-model"
    provider.model_env = None
    provider.model_default = "default-model"

    result = _resolve_provider_model(provider, "request-model")
    assert result == "resolved-model"


def test_resolve_provider_model_with_env():
    """model_env overrides model_default when set."""
    from unittest.mock import MagicMock

    from gateway.llm_client import _resolve_provider_model

    provider = MagicMock()
    provider.model_resolver = None
    provider.model_env = "MY_MODEL_ENV"
    provider.model_default = "default-model"

    with patch.dict("os.environ", {"MY_MODEL_ENV": "env-model"}):
        result = _resolve_provider_model(provider, None)

    assert result == "env-model"


def test_resolve_provider_model_falls_back_to_default():
    """When resolver and env are unset, model_default is used."""
    from unittest.mock import MagicMock

    from gateway.llm_client import _resolve_provider_model

    provider = MagicMock()
    provider.model_resolver = None
    provider.model_env = None
    provider.model_default = "default-model"

    result = _resolve_provider_model(provider, None)
    assert result == "default-model"


# ── _agentrouter_request_mutator ──────────────────────────────────────────


def test_agentrouter_request_mutator_adds_headers():
    """AgentRouter request mutator adds User-Agent, Originator, Version headers."""
    from gateway.llm_client import _agentrouter_request_mutator

    payload = {"model": "gpt-4o", "messages": []}
    headers = {"Authorization": "Bearer test-key", "Content-Type": "application/json"}

    with patch("gateway.llm_client.load_dotenv"), patch.dict("os.environ", {}, clear=True):
        result_payload, result_headers = _agentrouter_request_mutator(payload, headers, "gpt-4o")

    assert result_payload is payload
    assert result_headers["Authorization"] == "Bearer test-key"
    assert "User-Agent" in result_headers
    assert "Originator" in result_headers
    assert "Version" in result_headers


def test_agentrouter_request_mutator_loads_extra_json_headers():
    """KITTY_AGENTROUTER_EXTRA_HEADERS_JSON adds custom headers."""
    from gateway.llm_client import _agentrouter_request_mutator

    payload = {"model": "gpt-4o", "messages": []}
    headers = {"Authorization": "Bearer test-key"}

    with (
        patch("gateway.llm_client.load_dotenv"),
        patch.dict(
            "os.environ",
            {"KITTY_AGENTROUTER_EXTRA_HEADERS_JSON": '{"X-Custom": "value123"}'},
            clear=True,
        ),
    ):
        _p, result_headers = _agentrouter_request_mutator(payload, headers, "gpt-4o")

    assert result_headers["X-Custom"] == "value123"


def test_agentrouter_request_mutator_ignores_bad_extra_json():
    """Invalid KITTY_AGENTROUTER_EXTRA_HEADERS_JSON is silently ignored."""
    from gateway.llm_client import _agentrouter_request_mutator

    payload = {"model": "gpt-4o", "messages": []}
    headers = {"Authorization": "Bearer test-key"}

    with (
        patch("gateway.llm_client.load_dotenv"),
        patch.dict(
            "os.environ",
            {"KITTY_AGENTROUTER_EXTRA_HEADERS_JSON": "not-json"},
            clear=True,
        ),
    ):
        _p, result_headers = _agentrouter_request_mutator(payload, headers, "gpt-4o")

    assert "X-Custom" not in result_headers


# ── _agentrouter_client_rejected ──────────────────────────────────────────


def test_agentrouter_client_rejected_matches_401_unauthorized_client():
    from gateway.llm_client import _agentrouter_client_rejected

    resp = MagicMock()
    resp.status_code = 401
    resp.text = '{"error":{"message":"Unauthorized client"}}'
    assert _agentrouter_client_rejected(resp) is True


def test_agentrouter_client_rejected_non_401():
    from gateway.llm_client import _agentrouter_client_rejected

    resp = MagicMock()
    resp.status_code = 403
    resp.text = "forbidden"
    assert _agentrouter_client_rejected(resp) is False


def test_agentrouter_client_rejected_none():
    from gateway.llm_client import _agentrouter_client_rejected

    assert _agentrouter_client_rejected(None) is False


# ── _is_agentrouter_disabled ──────────────────────────────────────────────


def test_is_agentrouter_disabled_true():
    from gateway.llm_client import _is_agentrouter_disabled

    with patch.dict("os.environ", {"KITTY_DISABLE_AGENTROUTER": "1"}, clear=True):
        assert _is_agentrouter_disabled() is True


def test_is_agentrouter_disabled_false():
    from gateway.llm_client import _is_agentrouter_disabled

    with patch.dict("os.environ", {}, clear=True):
        assert _is_agentrouter_disabled() is False
