"""Tests for the GET /ping liveness endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from gateway.app import app


def test_ping_returns_200_with_status_ok() -> None:
    """GET /ping must return HTTP 200 with JSON exactly {"status": "ok"}."""
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/ping")
    assert r.status_code == 200, r.status_code
    assert r.json() == {"status": "ok"}, r.json()