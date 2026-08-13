from __future__ import annotations

import inspect

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import work as work_route
from gateway.routes.register import register_routes


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(work_route.router)
    return TestClient(app)


def test_get_work_returns_projected_snapshot(client, monkeypatch):
    monkeypatch.setattr(
        work_route,
        "build_status_snapshot",
        lambda: {
            "schema_version": 2,
            "integrity": {"state": "complete", "partial_packets": 0, "total_packets": 1},
            "queue": {
                "total": 1,
                "queued": 1,
                "claimed": 0,
                "running": 0,
                "blocked": 0,
                "pr_opened": 0,
                "awaiting_review": 0,
                "done": 0,
                "failed": 0,
                "cancelled": 0,
            },
            "initiatives": [
                {
                    "initiative_id": "init-1",
                    "title": "Builder initiative",
                    "state": "active",
                    "pause_reason": None,
                    "next_packet": "packet-1",
                    "updated_at": "2026-08-13T11:59:00Z",
                    "packets": [
                        {
                            "packet_id": "packet-1",
                            "title": "Packet one",
                            "objective": "Do work",
                            "task_id": "task-1",
                            "task_state": "queued",
                            "eligibility": {"state": "eligible", "blocked_by": []},
                            "run": None,
                            "failure_kind": None,
                            "blocked_reason": None,
                            "last_error": None,
                            "updated_at": "2026-08-13T11:59:00Z",
                            "projection": {"next_action": "claim"},
                            "attempt_history": [
                                {
                                    "validation": {"status": "passed"},
                                    "review": {"verdict": "approved"},
                                }
                            ],
                            "publication": None,
                            "data_quality": {"state": "complete", "issues": []},
                        }
                    ],
                }
            ],
        },
    )
    response = client.get("/work")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == 1
    assert body["counts"]["ready"] == 1
    assert body["items"][0]["state"] == "ready"
    assert body["items"][0]["evidence"]["approval"]["state"] == "unavailable"


def test_get_work_returns_503_with_concrete_reason_when_snapshot_fails(client, monkeypatch):

    def boom():
        raise RuntimeError("builder database is unavailable")

    monkeypatch.setattr(work_route, "build_status_snapshot", boom)
    response = client.get("/work")
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Work snapshot unavailable: RuntimeError: builder database is unavailable"
    }


def test_work_layer_depends_only_on_builder_snapshot_boundary():
    route_source = inspect.getsource(work_route)
    assert "build_status_snapshot" in route_source
    assert "builder_queue" not in route_source
    assert "sqlite3" not in route_source


def test_work_route_is_mounted_in_gateway_registry(monkeypatch):
    monkeypatch.setattr(
        work_route,
        "build_status_snapshot",
        lambda: {
            "schema_version": 2,
            "integrity": {"state": "complete", "partial_packets": 0, "total_packets": 0},
            "queue": {
                "total": 0,
                "queued": 0,
                "claimed": 0,
                "running": 0,
                "blocked": 0,
                "pr_opened": 0,
                "awaiting_review": 0,
                "done": 0,
                "failed": 0,
                "cancelled": 0,
            },
            "initiatives": [],
        },
    )
    app = FastAPI()
    register_routes(app)
    response = TestClient(app).get("/work")
    assert response.status_code == 200
    assert response.json()["schema_version"] == 1
