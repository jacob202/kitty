from __future__ import annotations

import json

import pytest

from gateway import llm_client, provider_prefs


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_prefs, "PROVIDER_PREFS_FILE", tmp_path / "providers.json")


def select_agentrouter(monkeypatch):
    monkeypatch.setenv("AGENTROUTER_API_KEY", "test-key")
    provider_prefs.save_preferences(
        ["agentrouter"], [], known=tuple(llm_client.PROVIDERS), active="agentrouter"
    )


def test_selected_provider_skips_litellm(monkeypatch):
    select_agentrouter(monkeypatch)
    calls = []

    def fake_provider(provider, messages, *args, **kwargs):
        calls.append(provider.name)
        return "agent router answered"

    monkeypatch.setattr(llm_client, "_call_provider", fake_provider)
    monkeypatch.setattr(
        llm_client,
        "_post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LiteLLM must be skipped")),
    )
    assert llm_client.call_llm([{"role": "user", "content": "hello"}]) == "agent router answered"
    assert calls == ["agentrouter"]


@pytest.mark.asyncio
async def test_selected_provider_works_through_streaming_ui_path(monkeypatch):
    select_agentrouter(monkeypatch)
    monkeypatch.setattr(llm_client, "_call_provider", lambda *args, **kwargs: "streamed direct")
    chunks = [
        chunk
        async for chunk in llm_client.iter_chat_completions_stream(
            {"model": "kitty-default", "messages": [{"role": "user", "content": "hello"}]}
        )
    ]
    assert chunks[-1] == b"data: [DONE]" + bytes([10, 10])
    payload = json.loads(chunks[0].decode().removeprefix("data: ").strip())
    assert payload["model"] == "agentrouter"
    assert payload["choices"][0]["delta"]["content"] == "streamed direct"


def test_active_provider_cannot_be_unknown_or_disabled():
    known = tuple(llm_client.PROVIDERS)
    with pytest.raises(ValueError, match="unknown active provider"):
        provider_prefs.save_preferences([], [], known=known, active="typo")
    with pytest.raises(ValueError, match="cannot also be disabled"):
        provider_prefs.save_preferences([], ["agentrouter"], known=known, active="agentrouter")
