"""Defaults for SSE/socket chat tier."""

import pytest
from flask import Flask

from src.api.shared import default_web_chat_mode
from src.api.streaming_routes import streaming_bp


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


def test_stream_without_mode_uses_fast_default(monkeypatch):
    monkeypatch.delenv("KITTY_WEB_DEFAULT_MODE", raising=False)
    seen = {}

    def fake_stream_response(query, client_id, mode, reasoning):
        seen.update(
            {
                "query": query,
                "client_id": client_id,
                "mode": mode,
                "reasoning": reasoning,
            }
        )

    monkeypatch.setattr(
        "src.api.web_orchestrator.stream_response",
        fake_stream_response,
    )

    app = Flask(__name__)
    app.register_blueprint(streaming_bp)

    response = app.test_client().get(
        "/stream?query=hello&client_id=mode-default-test",
        buffered=True,
    )

    assert response.status_code == 200
    assert seen["mode"] == "fast"
