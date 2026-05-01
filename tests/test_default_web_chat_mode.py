"""Defaults for SSE/socket chat tier."""

import os

import pytest

from src.api.shared import default_web_chat_mode


def test_default_web_chat_mode_balanced(monkeypatch):
    monkeypatch.delenv("KITTY_WEB_DEFAULT_MODE", raising=False)
    assert default_web_chat_mode() == "balanced"


@pytest.mark.parametrize(
    "raw,want",
    [
        ("fast", "fast"),
        ("BALANCED", "balanced"),
        ("max", "max"),
        ("nope", "balanced"),
        ("", "balanced"),
    ],
)
def test_default_web_chat_mode_env(monkeypatch, raw, want):
    monkeypatch.setenv("KITTY_WEB_DEFAULT_MODE", raw)
    assert default_web_chat_mode() == want
