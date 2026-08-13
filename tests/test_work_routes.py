"""Tests for the /work routes — three read-only endpoints over the Work spine."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import builder_queue as bq
from gateway.routes import work as work_route

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    bq.init_db(p)
    return p


@pytest.fixture
def client(db_path: Path, monkeypatch) -> TestClient:
    """TestClient with the work router and a monkeypatched BUILDER_QUEUE_DB.

    Patches the default DB path so the route handlers resolve to the test
    database without needing to pass ``db_path`` explicitly.
    """
    monkeypatch.setattr(bq, "BUILDER_QUEUE_DB", db_path)
    monkeypatch.setattr(work_route, "BUILDER_QUEUE_DB", db_path)
    from gateway import paths

    monkeypatch.setattr(paths, "BUILDER_QUEUE_DB", db_path)
    app = FastAPI()
    app.include_router(work_route.router)
    return TestClient(app)


def _task(db_path: Path) -> dict:
    """Helper: create a task and return it."""
    return bq.create_task(
        title="Route test task",
        description="Created for route testing",
        acceptance_criteria=["works"],
        bridge_source="test",
        db_path=db_path,
    )


# ---------------------------------------------------------------------------
# GET /work
# ---------------------------------------------------------------------------


class TestListWork:
    def test_empty_returns_empty_items(self, client: TestClient):
        response = client.get("/work")
        assert response.status_code == 200
        body = response.json()
        assert body == {"items": []}

    def test_returns_tasks(self, client: TestClient, db_path: Path):
        _task(db_path=db_path)
        response = client.get("/work")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["state"] == "queued"

    def test_state_filter(self, client: TestClient, db_path: Path):
        t = _task(db_path=db_path)
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)

        response = client.get("/work?state=running")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["title"] == "Route test task"

    def test_state_filter_no_match(self, client: TestClient):
        response = client.get("/work?state=completed")
        assert response.status_code == 200
        assert response.json() == {"items": []}

    def test_invalid_state_returns_400(self, client: TestClient):
        response = client.get("/work?state=bogus")
        assert response.status_code == 400

    def test_source_filter(self, client: TestClient, db_path: Path):
        _task(db_path=db_path)  # source=test
        bq.create_task(
            title="Initiative task",
            bridge_source="initiative",
            db_path=db_path,
        )
        response = client.get("/work?source=initiative")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["source"] == "initiative"

    def test_limit(self, client: TestClient, db_path: Path):
        for _ in range(5):
            _task(db_path=db_path)
        response = client.get("/work?limit=2")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 2


# ---------------------------------------------------------------------------
# GET /work/{work_id}
# ---------------------------------------------------------------------------


class TestGetWork:
    def test_known_id_returns_item(self, client: TestClient, db_path: Path):
        t = _task(db_path=db_path)
        work_id = f"builder:{t['id']}"
        response = client.get(f"/work/{work_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["work_id"] == work_id
        assert body["state"] == "queued"
        assert body["title"] == "Route test task"

    def test_missing_id_returns_404(self, client: TestClient):
        response = client.get("/work/builder:kb_nonexistent_0000")
        assert response.status_code == 404

    def test_unrecognised_prefix_returns_400(self, client: TestClient):
        response = client.get("/work/github:42")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /work/{work_id}/events
# ---------------------------------------------------------------------------


class TestGetWorkEvents:
    def test_known_id_returns_events(self, client: TestClient, db_path: Path):
        t = _task(db_path=db_path)
        work_id = f"builder:{t['id']}"
        response = client.get(f"/work/{work_id}/events")
        assert response.status_code == 200
        body = response.json()
        assert "events" in body
        assert len(body["events"]) >= 1  # at least the "created" event
        assert body["events"][0]["type"] == "created"

    def test_missing_id_returns_404(self, client: TestClient):
        response = client.get("/work/builder:kb_nonexistent_0000/events")
        assert response.status_code == 404

    def test_unrecognised_prefix_returns_400(self, client: TestClient):
        response = client.get("/work/github:42/events")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


class TestRouteRegistration:
    def test_work_router_has_tags(self):
        assert hasattr(work_route.router, "tags")
        assert "work" in work_route.router.tags
