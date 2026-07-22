"""Tests for gateway/routes/network.py."""
from __future__ import annotations

import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes.network import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_tailnet_connected(client, monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout='{"Self": {"TailscaleIPs": ["100.64.1.2"]}}',
        )

    monkeypatch.setattr("gateway.routes.network.subprocess.run", fake_run)
    resp = client.get("/network/tailnet")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "tailnet_ip": "100.64.1.2", "ui_url": "http://100.64.1.2:4000"}


def test_tailnet_daemon_not_running(client, monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="")

    monkeypatch.setattr("gateway.routes.network.subprocess.run", fake_run)
    resp = client.get("/network/tailnet")
    assert resp.status_code == 200
    assert resp.json() == {"ok": False, "tailnet_ip": None, "ui_url": None}


def test_tailnet_cli_not_installed(client, monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("tailscale not found")

    monkeypatch.setattr("gateway.routes.network.subprocess.run", fake_run)
    resp = client.get("/network/tailnet")
    assert resp.status_code == 200
    assert resp.json() == {"ok": False, "tailnet_ip": None, "ui_url": None}


def test_tailnet_unexpected_json_shape(client, monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout='{"unexpected": true}')

    monkeypatch.setattr("gateway.routes.network.subprocess.run", fake_run)
    resp = client.get("/network/tailnet")
    assert resp.status_code == 200
    assert resp.json() == {"ok": False, "tailnet_ip": None, "ui_url": None}
