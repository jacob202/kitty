"""Tests for gateway.routes.builder — Builder HTTP routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes.builder import router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_builder_supervisor_status_returns_200(client):
    response = client.get("/builder/supervisor")
    # May return 200 or 503 depending on whether the DB exists,
    # but must not return 500 unhandled.
    assert response.status_code in (200, 503)


def test_builder_preflight_returns_structured_result(client):
    response = client.get("/builder/preflight/NONEXISTENT/PK-001")
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "refuse"
    assert isinstance(body["reasons"], list)
    assert isinstance(body["budget"], dict)
