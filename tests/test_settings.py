"""Tests for the pydantic-settings configuration model."""

import pytest

from gateway.settings import get_settings


def test_get_settings_reads_monkeypatched_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_settings() must re-read os.environ on each call (no cached singleton)."""
    monkeypatch.setenv("GATEWAY_PORT", "9123")
    assert get_settings().GATEWAY_PORT == 9123

    monkeypatch.setenv("GATEWAY_PORT", "9456")
    assert get_settings().GATEWAY_PORT == 9456


def test_get_settings_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GATEWAY_HOST", raising=False)
    monkeypatch.delenv("LITELLM_PORT", raising=False)
    s = get_settings()
    assert s.GATEWAY_HOST == "127.0.0.1"
    assert s.LITELLM_PORT == 8001


def test_secret_keys_are_masked_and_unwrappable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    s = get_settings()
    # SecretStr keeps the raw value out of repr/logs but allows explicit unwrap.
    assert "sk-secret-value" not in repr(s)
    assert s.OPENAI_API_KEY is not None
    assert s.OPENAI_API_KEY.get_secret_value() == "sk-secret-value"


def test_unset_secret_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    assert get_settings().NVIDIA_API_KEY is None
