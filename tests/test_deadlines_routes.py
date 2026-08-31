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


def test_sweep_endpoint_escalates_by_default_and_reports_delivered_count(client, monkeypatch):
    def fake_sweep(*, llm_fn=None, now=None, project_id=2, push_fn=None):
        assert push_fn is None
        return {"found": 1, "open": 1, "needs_jacob": 0, "blind_spots": [], "top": None, "generated_at": "now"}

    def fake_watch(*, push_fn):
        assert callable(push_fn)
        return {"checked": 1, "due": 1, "attempted": 1, "pushed": 1, "failed": 0, "skipped": 0}

    monkeypatch.setattr("gateway.routes.deadlines.deadline_sweep.sweep", fake_sweep)
    monkeypatch.setattr("gateway.routes.deadlines.deadline_watch.check_and_push", fake_watch)
    resp = client.post("/deadlines/sweep")

    assert resp.status_code == 200
    assert resp.json()["open"] == 1
    assert resp.json()["escalated"] == 1
    assert resp.json()["delivery_status"] == "delivered"
    assert "1 deadline warning delivered" in resp.json()["delivery_message"]


def test_sweep_endpoint_reports_when_due_warning_could_not_be_delivered(client, monkeypatch):
    monkeypatch.setattr(
        "gateway.routes.deadlines.deadline_sweep.sweep",
        lambda **_kwargs: {"found": 1, "open": 1, "needs_jacob": 0, "blind_spots": [], "top": None, "generated_at": "now"},
    )
    monkeypatch.setattr(
        "gateway.routes.deadlines.deadline_watch.check_and_push",
        lambda **_kwargs: {"checked": 1, "due": 1, "attempted": 1, "pushed": 0, "failed": 1, "skipped": 1},
    )

    resp = client.post("/deadlines/sweep")

    assert resp.status_code == 200
    assert resp.json()["escalated"] == 0
    assert resp.json()["delivery_status"] == "source_unavailable"
    assert "nothing was delivered" in resp.json()["delivery_message"].lower()


def test_sweep_endpoint_can_skip_escalation_explicitly(client, monkeypatch):
    monkeypatch.setattr(
        "gateway.routes.deadlines.deadline_sweep.sweep",
        lambda **_kwargs: {"found": 0, "open": 0, "needs_jacob": 0, "blind_spots": [], "top": None, "generated_at": "now"},
    )

    def should_not_run(**_kwargs):
        raise AssertionError("deadline watch must not run when push=false")

    monkeypatch.setattr("gateway.routes.deadlines.deadline_watch.check_and_push", should_not_run)
    resp = client.post("/deadlines/sweep?push=false")

    assert resp.status_code == 200
    assert resp.json()["delivery_status"] == "not_requested"
