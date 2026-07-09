"""Tests for /logs/tail — whitelisted read-only log tail for the UI."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import logs as logs_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(logs_route, "LOGS_DIR", tmp_path)
    app = FastAPI()
    app.include_router(logs_route.router)
    return TestClient(app)


def test_tail_returns_last_lines(client, tmp_path):
    (tmp_path / "gateway.log").write_text("\n".join(f"line {i}" for i in range(10)) + "\n")
    resp = client.get("/logs/tail?file=gateway&lines=3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["file"] == "gateway.log"
    assert body["lines"] == ["line 7", "line 8", "line 9"]


def test_unknown_file_is_400(client):
    resp = client.get("/logs/tail?file=../etc/passwd")
    assert resp.status_code == 400


def test_missing_file_is_404(client):
    resp = client.get("/logs/tail?file=litellm")
    assert resp.status_code == 404


def test_lines_bounds_enforced(client, tmp_path):
    (tmp_path / "gateway.log").write_text("x\n")
    assert client.get("/logs/tail?lines=0").status_code == 422
    assert client.get("/logs/tail?lines=501").status_code == 422
