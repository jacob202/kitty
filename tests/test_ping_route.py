"""Tests for GET /ping — lightweight liveness probe."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from gateway.app import app

    return TestClient(app, raise_server_exceptions=True)


class TestPingRoute:
    """GET /ping returns HTTP 200 with exact body {\"ok\": true}."""

    def test_ping_returns_200(self, client):
        r = client.get("/ping")
        assert r.status_code == 200

    def test_ping_returns_ok_true(self, client):
        r = client.get("/ping")
        assert r.json() == {"ok": True}

    def test_ping_content_type_is_json(self, client):
        r = client.get("/ping")
        assert r.headers["content-type"].startswith("application/json")
