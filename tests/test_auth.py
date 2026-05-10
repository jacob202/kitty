# tests/test_auth.py
import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from gateway.app import app


def test_health_always_accessible():
    with patch.dict(os.environ, {"GATEWAY_SECRET": "test-secret"}):
        client = TestClient(app)
        resp = client.get("/health")
    assert resp.status_code == 200


def test_protected_without_auth_returns_401():
    with patch.dict(os.environ, {"GATEWAY_SECRET": "test-secret"}):
        client = TestClient(app)
        resp = client.get("/weekly")
    assert resp.status_code == 401


def test_protected_with_wrong_token_returns_401():
    with patch.dict(os.environ, {"GATEWAY_SECRET": "test-secret"}):
        client = TestClient(app)
        resp = client.get("/weekly", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_protected_with_correct_token_passes_auth():
    with patch.dict(os.environ, {"GATEWAY_SECRET": "test-secret"}):
        client = TestClient(app)
        resp = client.get("/weekly", headers={"Authorization": "Bearer test-secret"})
    assert resp.status_code != 401


def test_no_secret_allows_protected_routes():
    with patch.dict(os.environ, {"GATEWAY_SECRET": ""}):
        client = TestClient(app)
        # With no secret set, protected routes pass through auth (may still fail for other reasons)
        resp = client.get("/weekly")
    assert resp.status_code != 401
