from unittest.mock import patch

import pytest

from gateway import memory
from gateway.llm_client import ProviderConfig


def test_auto_memory_extraction_uses_isolated_litellm_service(monkeypatch):
    monkeypatch.setattr(memory, "LITELLM_BASE", "http://127.0.0.1:8121")
    monkeypatch.setattr(memory, "LITELLM_KEY", "local-proxy-key")

    with patch("gateway.llm_client.selected_provider_name", return_value=None):
        target = memory._mem0_llm_target()

    assert target == {
        "provider": "litellm",
        "model": "kitty-small",
        "api_key": "local-proxy-key",
        "openai_base_url": "http://127.0.0.1:8121/v1",
    }


def test_exact_openrouter_selection_uses_only_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    provider = ProviderConfig(
        name="openrouter",
        route="openrouter_direct",
        base_url="https://openrouter.ai/api/v1",
        api_key_env=("OPENROUTER_API_KEY",),
        model_default="",
    )

    with patch("gateway.llm_client.selected_provider_name", return_value="openrouter"), patch.dict(
        "gateway.llm_client.PROVIDERS", {"openrouter": provider}, clear=True
    ):
        target = memory._mem0_llm_target()

    assert target["provider"] == "openrouter"
    assert target["api_key"] == "or-key"
    assert target["model"] == memory.MEMORY_OPENROUTER_MODEL_DEFAULT
    assert target["openai_base_url"] == "https://openrouter.ai/api/v1"


def test_selected_provider_without_key_fails_instead_of_leaking_elsewhere():
    provider = ProviderConfig(
        name="openai",
        route="openai_direct",
        base_url="https://api.openai.com/v1",
        api_key_env=("MISSING_TEST_KEY",),
        model_default="gpt-test",
    )

    with patch("gateway.llm_client.selected_provider_name", return_value="openai"), patch.dict(
        "gateway.llm_client.PROVIDERS", {"openai": provider}, clear=True
    ), pytest.raises(memory.MemoryError, match="has no API key"):
        memory._mem0_llm_target()


def test_mem0_config_passes_the_resolved_openai_compatible_base():
    target = {
        "provider": "litellm",
        "model": "kitty-small",
        "api_key": "proxy-key",
        "openai_base_url": "http://127.0.0.1:8001/v1",
    }
    with patch.object(memory, "_mem0_llm_target", return_value=target):
        config = memory._build_mem0_config()

    assert config["llm"] == {
        "provider": "openai",
        "config": {
            "model": "kitty-small",
            "api_key": "proxy-key",
            "openai_base_url": "http://127.0.0.1:8001/v1",
        },
    }
