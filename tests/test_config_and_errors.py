"""Tests for the central config (Lane D) and typed errors."""

from __future__ import annotations

import pytest

from gateway import config, errors


# --- config: env-var helpers ---


def test_get_setting_returns_default_when_unset(monkeypatch):
    monkeypatch.delenv("KITTY_TEST_NOPE", raising=False)
    assert config.get_setting("KITTY_TEST_NOPE", "fallback") == "fallback"


def test_get_setting_returns_default_with_cast(monkeypatch):
    monkeypatch.delenv("KITTY_TEST_INT", raising=False)
    assert config.get_setting("KITTY_TEST_INT", 42, cast=int) == 42


def test_get_setting_uses_caster(monkeypatch):
    monkeypatch.setenv("KITTY_TEST_INT", "7")
    assert config.get_setting("KITTY_TEST_INT", 0, cast=int) == 7


def test_get_setting_raises_config_error_on_bad_cast(monkeypatch):
    monkeypatch.setenv("KITTY_TEST_INT", "not-an-int")
    with pytest.raises(errors.ConfigError, match="KITTY_TEST_INT"):
        config.get_setting("KITTY_TEST_INT", 0, cast=int)


def test_require_setting_raises_config_error_when_missing(monkeypatch):
    monkeypatch.delenv("KITTY_TEST_REQUIRED", raising=False)
    with pytest.raises(errors.ConfigError, match="KITTY_TEST_REQUIRED"):
        config.require_setting("KITTY_TEST_REQUIRED")


def test_require_setting_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("KITTY_TEST_REQUIRED", "abc")
    assert config.require_setting("KITTY_TEST_REQUIRED") == "abc"


def test_require_setting_rejects_empty_string(monkeypatch):
    monkeypatch.setenv("KITTY_TEST_REQUIRED", "")
    with pytest.raises(errors.ConfigError, match="KITTY_TEST_REQUIRED"):
        config.require_setting("KITTY_TEST_REQUIRED")


def test_env_name_default_is_local(monkeypatch):
    monkeypatch.delenv("KITTY_ENV", raising=False)
    assert config.env_name() == "local"


def test_env_name_reads_override(monkeypatch):
    monkeypatch.setenv("KITTY_ENV", "staging")
    assert config.env_name() == "staging"


def test_is_test_env_recognises_pytest(monkeypatch):
    monkeypatch.setenv("KITTY_ENV", "pytest")
    assert config.is_test_env() is True


def test_is_test_env_recognises_ci_prefix(monkeypatch):
    monkeypatch.setenv("KITTY_ENV", "ci-staging")
    assert config.is_test_env() is True


def test_is_test_env_false_for_local(monkeypatch):
    monkeypatch.setenv("KITTY_ENV", "local")
    assert config.is_test_env() is False


def test_gateway_constants_have_expected_defaults():
    # Module-level constants are bound at import time; their values
    # are whatever the runtime is configured for. We just verify the
    # shape — the URL was built from the components and parses back.
    assert config.GATEWAY_HOST
    assert isinstance(config.GATEWAY_PORT, int)
    assert config.GATEWAY_PORT > 0
    assert config.GATEWAY_BASE_URL.startswith(f"http://{config.GATEWAY_HOST}:")
    assert config.LITELLM_BASE_URL.startswith(f"http://{config.LITELLM_HOST}:")


# --- errors: hierarchy + HTTP shape ---


def test_kitty_error_default_status_is_500():
    err = errors.KittyError("boom")
    assert err.status_code == 500
    assert err.code == "internal_error"
    assert err.message == "boom"
    assert err.details == {}


def test_kitty_error_to_dict_includes_details():
    err = errors.StorageNotFound("missing todo", details={"id": 42})
    body = err.to_dict()
    assert body == {
        "error": "storage.not_found",
        "message": "missing todo",
        "details": {"id": 42},
    }


def test_subclasses_have_distinct_codes_and_statuses():
    cases = [
        (errors.ConfigError("x"), 500, "config_error"),
        (errors.StorageNotFound("x"), 404, "storage.not_found"),
        (errors.StorageConflict("x"), 409, "storage.conflict"),
        (errors.StorageUnavailable("x"), 503, "storage.unavailable"),
        (errors.ProviderError("x"), 502, "provider.error"),
        (errors.ProviderTimeout("x"), 504, "provider.timeout"),
        (errors.AuthError("x"), 401, "auth.unauthorized"),
        (errors.AuthForbidden("x"), 403, "auth.forbidden"),
        (errors.ValidationError("x"), 400, "validation_error"),
    ]
    for err, status, code in cases:
        assert err.status_code == status, f"{type(err).__name__} status wrong"
        assert err.code == code, f"{type(err).__name__} code wrong"
        body = err.to_dict()
        assert body["error"] == code
        assert body["message"] == "x"


def test_kitty_error_can_be_raised_and_caught():
    with pytest.raises(errors.KittyError):
        raise errors.ProviderError("llm down")
