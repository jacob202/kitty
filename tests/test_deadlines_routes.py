"""Tests for gateway/routes/deadlines.py."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gateway import deadline_store, project_store
from gateway.routes.deadlines import router


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "kitty.db"
    monkeypatch.setattr("gateway.deadline_store.DEADLINES_DB_FILE", db)
    monkeypatch.setattr("gateway.project_store.PROJECTS_DB_FILE", db)
    monkeypatch.setattr("gateway.db.KITTY_DB_FILE", db)
    monkeypatch.setattr("gateway.paths.KITTY_DB_FILE", db)
    deadline_store.init_db()
    project_store.create("benefits-admin", "admin")

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_list_deadlines_empty(client):
    resp = client.get("/deadlines")
    assert resp.status_code == 200
    assert resp.json() == {"deadlines": []}


def test_list_deadlines_with_status(client):
    deadline_store.upsert(
        {
            "project_id": 2,
            "source": "test",
            "due_date": "2026-08-01",
            "obligation": "x",
            "confidence": "needs_jacob",
            "status": "needs_jacob",
        }
    )
    resp = client.get("/deadlines?status=needs_jacob")
    assert resp.status_code == 200
    assert len(resp.json()["deadlines"]) == 1


def test_get_deadline(client):
    d = deadline_store.upsert(
        {
            "project_id": 2,
            "source": "test",
            "due_date": "2026-08-01",
            "obligation": "x",
            "confidence": "high",
        }
    )
    resp = client.get(f"/deadlines/{d['id']}")
    assert resp.status_code == 200
    assert resp.json()["obligation"] == "x"


def test_get_deadline_missing(client):
    resp = client.get("/deadlines/9999")
    assert resp.status_code == 404


def test_close_deadline(client):
    d = deadline_store.upsert(
        {
            "project_id": 2,
            "source": "test",
            "due_date": "2026-08-01",
            "obligation": "x",
            "confidence": "high",
        }
    )
    resp = client.post(f"/deadlines/{d['id']}/close")
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


def test_sweep_endpoint(client, monkeypatch):
    def fake_sweep(*, push_fn, llm_fn=None, now=None, project_id=2):
        return {"open": 0, "blind_spots": [], "top": None}

    monkeypatch.setattr("gateway.routes.deadlines.deadline_sweep.sweep", fake_sweep)
    resp = client.post("/deadlines/sweep")
    assert resp.status_code == 200
    assert resp.json()["open"] == 0
