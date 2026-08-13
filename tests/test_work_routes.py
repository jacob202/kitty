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
        assert body["items"] == []
        assert body["schema_version"] == 1

    def test_returns_tasks(self, client: TestClient, db_path: Path):
        _task(db_path=db_path)
        response = client.get("/work")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["state"] == "pending"
        assert body["items"][0]["source"] == "builder"

    def test_state_filter_pending(self, client: TestClient, db_path: Path):
        t = _task(db_path=db_path)
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)
        _task(db_path=db_path)  # another queued task

        response = client.get("/work?state=pending")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1

    def test_state_filter_running(self, client: TestClient, db_path: Path):
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
        body = response.json()
        assert body["items"] == []
        assert body["total_items"] == 0

    def test_invalid_state_returns_400(self, client: TestClient):
        response = client.get("/work?state=bogus")
        assert response.status_code == 400

    def test_source_builder_works(self, client: TestClient, db_path: Path):
        _task(db_path=db_path)
        response = client.get("/work?source=builder")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1

    def test_non_builder_source_returns_400(self, client: TestClient):
        response = client.get("/work?source=initiative")
        assert response.status_code == 400

    def test_limit(self, client: TestClient, db_path: Path):
        for _ in range(5):
            _task(db_path=db_path)
        response = client.get("/work?limit=2")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 2

    def test_item_has_all_required_fields(self, client: TestClient, db_path: Path):
        _task(db_path=db_path)
        response = client.get("/work")
        item = response.json()["items"][0]
        assert "work_id" in item
        assert "source" in item
        assert "source_id" in item
        assert "title" in item
        assert "summary" in item
        assert "state" in item
        assert "source_state" in item
        assert "priority" in item
        assert "created_at" in item
        assert "updated_at" in item
        assert "blocker" in item
        assert "error" in item
        assert "latest_run" in item
        assert "latest_pr" in item
        assert "evidence" in item
        assert "links" in item

    def test_campaign_fields(self, client: TestClient, db_path: Path):
        """GET /work returns schema_version, observed_at, valid_until, source_health."""
        _task(db_path=db_path)
        response = client.get("/work")
        body = response.json()
        assert body["schema_version"] == 1
        assert "T" in body["observed_at"]
        assert "T" in body["valid_until"]
        assert body["source_health"] == {"kind": "builder", "state": "available"}

    def test_campaign_total_items(self, client: TestClient, db_path: Path):
        """total_items reflects the full matching set, not the page."""
        for _ in range(5):
            _task(db_path=db_path)
        response = client.get("/work?limit=2")
        body = response.json()
        assert body["total_items"] == 5
        assert body["item_limit"] == 2
        assert len(body["items"]) == 2

    def test_campaign_state_counts(self, client: TestClient, db_path: Path):
        """state_counts aggregates all matching items."""
        _task(db_path=db_path)
        t2 = bq.create_task(
            title="Running task",
            description="A running task",
            acceptance_criteria=["works"],
            bridge_source="test",
            db_path=db_path,
        )
        bq.transition_task(t2["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t2["id"], bq.RUNNING, db_path=db_path)
        response = client.get("/work")
        body = response.json()
        assert body["state_counts"]["pending"] >= 1
        assert body["state_counts"]["running"] == 1

    def test_item_approval_always_unavailable(self, client: TestClient, db_path: Path):
        """Every item's evidence.approval is state=unavailable with binding reason."""
        _task(db_path=db_path)
        response = client.get("/work")
        item = response.json()["items"][0]
        assert item["evidence"]["approval"]["state"] == "unavailable"
        assert "binding" in item["evidence"]["approval"]["reason"]


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
        assert body["source"] == "builder"
        assert body["source_id"] == t["id"]
        assert body["state"] == "pending"
        assert body["title"] == "Route test task"

    def test_missing_id_returns_404(self, client: TestClient):
        response = client.get("/work/builder:kb_nonexistent_0000")
        assert response.status_code == 404

    def test_unrecognised_prefix_returns_400(self, client: TestClient):
        response = client.get("/work/github:42")
        assert response.status_code == 400

    def test_source_and_source_id_in_response(self, client: TestClient, db_path: Path):
        t = _task(db_path=db_path)
        work_id = f"builder:{t['id']}"
        response = client.get(f"/work/{work_id}")
        body = response.json()
        assert body["source"] == "builder"
        assert body["source_id"] == t["id"]

    def test_detail_evidence_approval(self, client: TestClient, db_path: Path):
        """Detail evidence always contains approval with state=unavailable."""
        t = _task(db_path=db_path)
        work_id = f"builder:{t['id']}"
        response = client.get(f"/work/{work_id}")
        body = response.json()
        assert body["evidence"]["approval"]["state"] == "unavailable"
        assert "binding" in body["evidence"]["approval"]["reason"]


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
        assert len(body["events"]) >= 1
        assert body["events"][0]["type"] == "created"

    def test_events_in_builder_order(self, client: TestClient, db_path: Path):
        t = _task(db_path=db_path)
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)
        work_id = f"builder:{t['id']}"
        response = client.get(f"/work/{work_id}/events")
        events = response.json()["events"]
        assert len(events) >= 3
        for i in range(1, len(events)):
            assert events[i]["id"] > events[i - 1]["id"]

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
