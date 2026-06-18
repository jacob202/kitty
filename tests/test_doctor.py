from __future__ import annotations

from gateway.doctor import _check_env


def test_gateway_secret_warning_matches_fail_closed_auth() -> None:
    checks = _check_env({"OPENROUTER_API_KEY": "set"})

    gateway_secret = next(c for c in checks if c.name == "env:gateway_secret")

    assert gateway_secret.level == "WARN"
    assert "fails closed" in gateway_secret.detail
    assert "accepts any request" not in gateway_secret.detail
