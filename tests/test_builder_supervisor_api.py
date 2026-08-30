"""Tests for the /builder/supervisor HTTP endpoints (BUILDER-SUPERVISOR-API).

These endpoints wrap ``gateway.builder_supervisor`` (status/tick) so the UI
can see whether Builder's supervisor is running and start it. Every test
mocks ``gateway.builder_supervisor.status``/``tick`` — no real tick or
supervisor lock ever touches live Builder state.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import builder as builder_route


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(builder_route.router)
    return TestClient(app)


def _projection(*, initiatives, active_runs, scheduler_enabled=True):
    return {
        "lock": {"path": "/data/kittybuilder/supervisor.lock"},
        "initiatives": initiatives,
        "active_runs": active_runs,
        "scheduler_enabled": scheduler_enabled,
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


class TestSupervisorControlPlaneSummary:
    def test_route_does_not_block_event_loop_while_collecting_system_status(self, monkeypatch):
        def slow_summary():
            time.sleep(0.2)
            return {
                "active_runs": [], "eligible_now": 0, "on_hold": 0,
                "lock_path": "/tmp/supervisor.lock", "scheduler_enabled": True,
                "budget": {},
            }

        monkeypatch.setattr("gateway.builder_supervisor.control_plane_summary", slow_summary)

        async def exercise():
            started = time.monotonic()
            heartbeat_at = None
            async def heartbeat():
                nonlocal heartbeat_at
                await asyncio.sleep(0.02)
                heartbeat_at = time.monotonic() - started
            heartbeat_task = asyncio.create_task(heartbeat())
            await builder_route.builder_supervisor_status()
            await heartbeat_task
            return heartbeat_at

        assert asyncio.run(exercise()) < 0.1

    def test_route_avoids_the_full_per_initiative_status_scan(self, client, monkeypatch):
        def expensive_status_must_not_run():
            raise AssertionError("full supervisor status scan must not run on the Work poll path")

        monkeypatch.setattr("gateway.builder_supervisor.status", expensive_status_must_not_run)
        monkeypatch.setattr(
            "gateway.builder_supervisor.control_plane_summary",
            lambda: {
                "active_runs": [],
                "eligible_now": 2,
                "on_hold": 6,
                "lock_path": "/data/kittybuilder/supervisor.lock",
                "scheduler_enabled": True,
                "budget": {
                    "weekly_budget_cad": 6.0,
                    "estimated_spend_cad": 0.25,
                    "remaining_cad": 5.75,
                    "runs": 4,
                    "retries": 1,
                    "basis": "local estimate",
                },
            },
            raising=False,
        )

        response = client.get("/builder/supervisor")

        assert response.status_code == 200
        body = response.json()
        assert body["eligible_now"] == 2
        assert body["budget"]["estimated_spend_cad"] == 0.25
        assert body["budget"]["remaining_cad"] == 5.75


class TestSupervisorStatusEndpoint:
    def _summary(self, *, active_runs=None, now=1, on_hold=0):
        return {
            "active_runs": active_runs or [],
            "eligible_now": now,
            "on_hold": on_hold,
            "lock_path": "/data/kittybuilder/supervisor.lock",
            "scheduler_enabled": True,
            "budget": {
                "weekly_budget_cad": 6.0,
                "estimated_spend_cad": 0.25,
                "remaining_cad": 5.75,
                "runs": 4,
                "retries": 1,
                "basis": "local estimate",
            },
        }

    def test_returns_documented_shape(self, client, monkeypatch):
        monkeypatch.setattr(
            "gateway.builder_supervisor.control_plane_summary",
            lambda: self._summary(),
        )

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
            "scheduler_enabled": True,
            "budget": {
                "weekly_budget_cad": 6.0,
                "estimated_spend_cad": 0.25,
                "remaining_cad": 5.75,
                "runs": 4,
                "retries": 1,
                "basis": "local estimate",
            },
        }

    def test_reports_the_counts_the_launcher_would_honour(self, client, monkeypatch):
        monkeypatch.setattr(
            "gateway.builder_supervisor.control_plane_summary",
            lambda: self._summary(now=3, on_hold=6),
        )

        response = client.get("/builder/supervisor")

        assert response.status_code == 200
        body = response.json()
        assert body["eligible_now"] == 3
        assert body["on_hold"] == 6

    def test_summary_failure_is_a_503_not_a_crash(self, client, monkeypatch):
        def boom():
            raise RuntimeError("queue unreadable")

        monkeypatch.setattr("gateway.builder_supervisor.control_plane_summary", boom)

        response = client.get("/builder/supervisor")

        assert response.status_code == 503
        assert "queue unreadable" in response.json()["detail"]

    def test_running_true_when_active_runs_present(self, client, monkeypatch):
        active_runs = [
            {"run_id": "run-1", "task_id": "task-1", "state": "running", "worker": "w"}
        ]
        monkeypatch.setattr(
            "gateway.builder_supervisor.control_plane_summary",
            lambda: self._summary(active_runs=active_runs),
        )

        response = client.get("/builder/supervisor")

        assert response.status_code == 200
        body = response.json()
        assert body["running"] is True
        assert body["active_runs"] == active_runs

    def test_running_false_when_no_active_runs(self, client, monkeypatch):
        monkeypatch.setattr(
            "gateway.builder_supervisor.control_plane_summary",
            lambda: self._summary(active_runs=[]),
        )

        response = client.get("/builder/supervisor")

        assert response.status_code == 200
        assert response.json()["running"] is False

    def test_read_failure_does_not_return_a_fabricated_200(self, client, monkeypatch):
        def _raise():
            raise RuntimeError("queue db is locked")

        monkeypatch.setattr("gateway.builder_supervisor.control_plane_summary", _raise)

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
        assert "worker script is missing" in body["error"]

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
        assert "Kitty launcher is missing" in body["error"]
        assert body["detail"] == receipt
