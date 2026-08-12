"""Tests for the /ping health-check endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes.ping import router


def test_ping_returns_200_with_ok_true() -> None:
    """GET /ping must return HTTP 200 with body {"ok": true}."""
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/ping")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
