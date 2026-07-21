"""Contract tests for call_llm's ProviderChainExhausted error."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gateway.llm_client import ProviderChainExhausted, call_llm


class TestProviderChainExhausted:
    """call_llm raises ProviderChainExhausted when the whole provider chain fails."""

    def test_error_carries_diagnostics(self):
        """ProviderChainExhausted carries per-provider error messages."""
        err = ProviderChainExhausted(["litellm: timeout", "openai: rate limit"])
        assert "litellm" in str(err)
        assert "openai" in str(err)
        assert err.errors == ["litellm: timeout", "openai: rate limit"]

    def test_error_has_code(self):
        """ProviderChainExhausted has a machine-readable code."""
        err = ProviderChainExhausted(["x"])
        assert err.code == "llm.chain_exhausted"

    def test_call_llm_raises_on_total_failure(self, monkeypatch):
        """When LiteLLM and all fallbacks fail, call_llm raises."""
        # Make LiteLLM fail
        monkeypatch.setattr(
            "gateway.llm_client._post",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("litellm down")),
        )
        # Make all fallback providers fail
        monkeypatch.setattr(
            "gateway.llm_client._call_provider",
            lambda *a, **kw: "",
        )
        # Ensure agentrouter is enabled so it gets tried
        monkeypatch.setattr("gateway.llm_client._is_agentrouter_disabled", lambda: False)

        with pytest.raises(ProviderChainExhausted):
            call_llm([{"role": "user", "content": "test"}])

    def test_call_llm_succeeds_on_first_try(self, monkeypatch):
        """When LiteLLM succeeds, no fallback is tried."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "hello"}}],
            "model": "test-model",
        }
        mock_resp.raise_for_status = MagicMock()
        monkeypatch.setattr("gateway.llm_client._post", lambda *a, **kw: mock_resp)

        result = call_llm([{"role": "user", "content": "test"}])
        assert result == "hello"
