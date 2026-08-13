"""Tests for the /version endpoint — contract validation."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import version as version_route


def test_get_version_returns_200_and_semver():
    """GET /version returns HTTP 200 with exactly {"version": "0.1.0"}."""
    app = FastAPI()
    app.include_router(version_route.router)
    client = TestClient(app)

    r = client.get("/version")

    assert r.status_code == 200
    assert r.json() == {"version": "0.1.0"}


def test_get_version_honors_runtime_override(monkeypatch):
    """GET /version reflects the configured KITTY_VERSION runtime fact."""
    monkeypatch.setenv("KITTY_VERSION", "1.2.3")
    app = FastAPI()
    app.include_router(version_route.router)
    client = TestClient(app)

    r = client.get("/version")

    assert r.status_code == 200
    assert r.json() == {"version": "1.2.3"}
