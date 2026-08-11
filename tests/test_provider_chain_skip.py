"""Keyless providers must be skipped without a network call."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from gateway import llm_client


@pytest.fixture(autouse=True)
def isolated_prefs(tmp_path, monkeypatch):
    from gateway import provider_prefs

    monkeypatch.setattr(provider_prefs, "PROVIDER_PREFS_FILE", tmp_path / "providers.json")
    monkeypatch.setattr(llm_client, "load_dotenv", lambda *args, **kwargs: False)


@pytest.fixture(autouse=True)
def no_provider_keys(monkeypatch):
    for name in (
        "OPENAI_API_KEY", "NVIDIA_API_KEY", "AGENTROUTER_API_KEY",
        "AGENT_ROUTER_TOKEN", "OPENROUTER_API_KEY", "GEMINI_API_KEY",
    ):
        monkeypatch.setenv(name, "")


def test_keyless_provider_is_never_dialled():
    """The whole point: an empty OPENROUTER_API_KEY used to cost a connect
    timeout per attempt before the chain gave up."""
    calls: list[str] = []

    def _record(url, **kwargs):
        calls.append(url)
        raise RuntimeError("network should not be reached")

    with patch.object(llm_client, "_post", side_effect=_record):
        with pytest.raises(llm_client.ProviderChainExhausted) as excinfo:
            llm_client.call_llm([{"role": "user", "content": "hi"}], model="kitty-default")

    # LiteLLM and the keyless local server are dialled; no cloud provider is.
    assert not any(("openrouter" in u or "openai.com" in u or "nvidia" in u) for u in calls), calls
    assert any("no api key configured" in e for e in excinfo.value.errors)


def test_local_is_tried_even_with_no_keys_anywhere():
    dialled: list[str] = []

    def _record(url, **kwargs):
        dialled.append(url)
        raise RuntimeError("down")

    with patch.object(llm_client, "_post", side_effect=_record):
        with pytest.raises(llm_client.ProviderChainExhausted):
            llm_client.call_llm([{"role": "user", "content": "hi"}], model="kitty-default")

    assert any("8010" in u for u in dialled), dialled


def test_direct_openrouter_ids_carry_no_litellm_prefix():
    """This map feeds the direct OpenRouter call, whose value goes straight into
    payload["model"]. "openrouter/" is LiteLLM's routing prefix — verified
    against the live API, it answers HTTP 400 "is not a valid model ID"."""
    for route, upstream in llm_client._LITELLM_TO_OPENROUTER.items():
        assert not upstream.startswith("openrouter/"), f"{route} -> {upstream}"
        assert upstream.count("/") == 1, f"{route} -> {upstream}"
