"""Tests for the /builder/supervisor HTTP endpoints (BUILDER-SUPERVISOR-API).

These endpoints wrap ``gateway.builder_supervisor`` (status/tick) so the UI
can see whether Builder's supervisor is running and start it. Every test
mocks ``gateway.builder_supervisor.status``/``tick`` — no real tick or
supervisor lock ever touches live Builder state.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import builder as builder_route


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(builder_route.router)
    return TestClient(app)


def _projection(*, initiatives, active_runs):
    return {
        "lock": {"path": "/data/kittybuilder/supervisor.lock"},
        "initiatives": initiatives,
        "active_runs": active_runs,
    }


def _initiative(initiative_id: str, stored_state: str, eligible_packet_ids: list[str]):
    return {
        "initiative_id": initiative_id,
        "stored_state": stored_state,
        "derived_state": stored_state,
        "eligible_packets": [
            {"packet_id": pid, "task_id": f"task-{pid}", "seq": i}
            for i, pid in enumerate(eligible_packet_ids)
        ],
    }


def _counts(monkeypatch, *, now: int, on_hold: int):
    monkeypatch.setattr(
        "gateway.builder_supervisor.dispatchable_counts",
        lambda *_args, **_kwargs: {"now": now, "on_hold": on_hold},
    )


class TestSupervisorStatusEndpoint:
    def test_returns_documented_shape(self, client, monkeypatch):
        projection = _projection(
            initiatives=[_initiative("init-a", "active", ["P1"])],
            active_runs=[],
        )
        monkeypatch.setattr(
            "gateway.builder_supervisor.status", lambda: projection
        )
        _counts(monkeypatch, now=1, on_hold=0)

        response = client.get("/builder/supervisor")

        assert response.status_code == 200
        body = response.json()
        assert body == {
            "schema_version": 1,
            "running": False,
            "active_runs": [],
            "eligible_now": 1,
            "on_hold": 0,
            "last_tick_at": None,
            "lock_path": "/data/kittybuilder/supervisor.lock",
        }

    def test_reports_the_counts_the_launcher_would_honour(self, client, monkeypatch):
        # The route must not recount eligibility from the projection: the
        # projection's notion is narrower than what a tick dispatches, and a
        # number the tick does not honour is worse than no number.
        projection = _projection(
            initiatives=[
                _initiative("init-active", "active", ["P1", "P2"]),
                _initiative("init-paused", "paused", ["P3"]),
                _initiative("init-completed", "completed", ["P4"]),
            ],
            active_runs=[],
        )
        monkeypatch.setattr(
            "gateway.builder_supervisor.status", lambda: projection
        )
        _counts(monkeypatch, now=3, on_hold=6)

        response = client.get("/builder/supervisor")

        assert response.status_code == 200
        body = response.json()
        assert body["eligible_now"] == 3
        assert body["on_hold"] == 6

    def test_status_failure_is_a_503_not_a_crash(self, client, monkeypatch):
        def boom():
            raise RuntimeError("queue unreadable")

        monkeypatch.setattr("gateway.builder_supervisor.status", boom)

        response = client.get("/builder/supervisor")

        assert response.status_code == 503
        assert "queue unreadable" in response.json()["detail"]

    def test_count_failure_is_a_503_not_a_crash(self, client, monkeypatch):
        projection = _projection(initiatives=[], active_runs=[])
        monkeypatch.setattr("gateway.builder_supervisor.status", lambda: projection)

        def boom(*_args, **_kwargs):
            raise RuntimeError("selection unreadable")

        monkeypatch.setattr("gateway.builder_supervisor.dispatchable_counts", boom)

        response = client.get("/builder/supervisor")

        assert response.status_code == 503
        assert "selection unreadable" in response.json()["detail"]

    def test_running_true_when_active_runs_present(self, client, monkeypatch):
        projection = _projection(
            initiatives=[],
            active_runs=[
                {"run_id": "run-1", "task_id": "task-1", "state": "running", "worker": "w"}
            ],
        )
        monkeypatch.setattr(
            "gateway.builder_supervisor.status", lambda: projection
        )

        response = client.get("/builder/supervisor")

        assert response.status_code == 200
        body = response.json()
        assert body["running"] is True
        assert body["active_runs"] == projection["active_runs"]

    def test_running_false_when_no_active_runs(self, client, monkeypatch):
        projection = _projection(initiatives=[], active_runs=[])
        monkeypatch.setattr(
            "gateway.builder_supervisor.status", lambda: projection
        )

        response = client.get("/builder/supervisor")

        assert response.status_code == 200
        assert response.json()["running"] is False

    def test_read_failure_does_not_return_a_fabricated_200(self, client, monkeypatch):
        def _raise():
            raise RuntimeError("queue db is locked")

        monkeypatch.setattr("gateway.builder_supervisor.status", _raise)

        response = client.get("/builder/supervisor")

        assert response.status_code == 503
        assert "queue db is locked" in response.json()["detail"]


class TestSupervisorTickEndpoint:
    def test_success_returns_ok_true_and_started_list(self, client, monkeypatch):
        receipt = {
            "status": "ok",
            "lock": {"acquired": True, "path": "/data/kittybuilder/supervisor.lock"},
            "max_runs": 2,
            "scanned_initiatives": [{"initiative_id": "init-a", "state": "active"}],
            "launched": [
                {
                    "initiative_id": "init-a",
                    "packet_id": "P1",
                    "task_id": "task-1",
                    "dispatch": {"status": "dispatched", "launcher_pid": 1234},
                }
            ],
            "skipped": [],
            "duplicate_tick": False,
        }
        monkeypatch.setattr(
            "gateway.builder_supervisor.tick", lambda: receipt
        )

        response = client.post("/builder/supervisor/tick")

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["started"] == receipt["launched"]
        assert body["error"] is None
        assert body["detail"] == receipt

    def test_locked_tick_is_reported_ok_with_no_launches(self, client, monkeypatch):
        receipt = {
            "status": "locked",
            "lock": {"acquired": False, "path": "/data/kittybuilder/supervisor.lock"},
            "max_runs": 2,
            "scanned_initiatives": [],
            "launched": [],
            "skipped": [],
            "duplicate_tick": True,
        }
        monkeypatch.setattr(
            "gateway.builder_supervisor.tick", lambda: receipt
        )

        response = client.post("/builder/supervisor/tick")

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["started"] == []

    def test_raised_exception_returns_ok_false_not_500(self, client, monkeypatch):
        def _raise():
            raise RuntimeError("canonical worker adapter missing: scripts/worker.sh")

        monkeypatch.setattr("gateway.builder_supervisor.tick", _raise)

        response = client.post("/builder/supervisor/tick")

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body["started"] == []
        assert "canonical worker adapter missing" in body["error"]

    def test_launch_error_entries_surface_as_ok_false(self, client, monkeypatch):
        receipt = {
            "status": "error",
            "lock": {"acquired": True, "path": "/data/kittybuilder/supervisor.lock"},
            "max_runs": 2,
            "scanned_initiatives": [{"initiative_id": "init-a", "state": "active"}],
            "launched": [
                {
                    "initiative_id": "init-a",
                    "packet_id": "P1",
                    "task_id": "task-1",
                    "dispatch": None,
                    "error": "SupervisorError: Kitty launcher missing",
                }
            ],
            "skipped": [],
            "duplicate_tick": False,
        }
        monkeypatch.setattr(
            "gateway.builder_supervisor.tick", lambda: receipt
        )

        response = client.post("/builder/supervisor/tick")

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert "Kitty launcher missing" in body["error"]
        assert body["detail"] == receipt
