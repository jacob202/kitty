"""Defaults for SSE/socket chat tier."""

import pytest

from src.api.shared import default_web_chat_mode


def test_default_web_chat_mode_fast_when_unset(monkeypatch):
    monkeypatch.delenv("KITTY_WEB_DEFAULT_MODE", raising=False)
    assert default_web_chat_mode() == "fast"


@pytest.mark.parametrize(
    "raw,want",
    [
        ("fast", "fast"),
        ("BALANCED", "balanced"),
        ("max", "max"),
        ("nope", "fast"),
        ("", "fast"),
    ],
)
def test_default_web_chat_mode_env(monkeypatch, raw, want):
    monkeypatch.setenv("KITTY_WEB_DEFAULT_MODE", raw)
    assert default_web_chat_mode() == want
