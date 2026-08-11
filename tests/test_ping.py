"""Tests for the /ping liveness endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from gateway.app import app


def _client():
    return TestClient(app, raise_server_exceptions=False)


class TestPing:
    """GET /ping must return HTTP 200 with JSON {"status": "ok"}."""

    def test_ping_returns_ok(self):
        resp = _client().get("/ping")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
