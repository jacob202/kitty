"""Tests for GET /status/glance"""

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from gateway.app import app

    return TestClient(app, raise_server_exceptions=True)


def test_glance_returns_required_keys(client):
    r = client.get("/status/glance")
    assert r.status_code == 200
    body = r.json()
    assert "branch" in body
    assert "uncommitted" in body
    assert "tests" in body


def test_glance_uses_cache(tmp_path, monkeypatch):
    import gateway.routes.status as s

    cache = tmp_path / "test-status.json"
    cache.write_text(json.dumps({"summary": "677 passed"}))
    monkeypatch.setattr(s, "_TEST_CACHE", cache)
    assert s._test_status() == "677 passed"


def test_glance_unknown_when_no_cache(tmp_path, monkeypatch):
    import gateway.routes.status as s

    monkeypatch.setattr(s, "_TEST_CACHE", tmp_path / "missing.json")
    assert s._test_status() == "unknown"
