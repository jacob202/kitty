"""Tests for the Kitty Brief OWUI tool."""

from unittest.mock import MagicMock, patch

from gateway.openwebui_library_tools.kitty_gateway_brief import Tools


def test_brief_hits_gateway_brief_route(monkeypatch):
    seen = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"brief": "Jacob is working on audio projects."}

    def fake_get(url, timeout=None):
        seen["url"] = url
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("requests.get", fake_get)

    tool = Tools()
    result = tool.get_brief()

    assert seen["url"] == "http://127.0.0.1:8000/brief"
    assert "Jacob is working" in result


def test_brief_gateway_error(monkeypatch):
    class FakeResponse:
        status_code = 500

        def json(self):
            return {}

    def fake_get(url, timeout=None):
        return FakeResponse()

    monkeypatch.setattr("requests.get", fake_get)

    tool = Tools()
    result = tool.get_brief()
    assert "500" in result


def test_brief_connection_error(monkeypatch):
    def fake_get(url, timeout=None):
        raise ConnectionError("refused")

    monkeypatch.setattr("requests.get", fake_get)

    tool = Tools()
    result = tool.get_brief()
    assert "Brief unavailable" in result
