"""Tests for the /builder routes — operator command endpoint (KB-BRAIN-05)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.builder_commands import CommandResult
from gateway.routes import builder as builder_route


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(builder_route.router)
    return TestClient(app)


class TestOperatorCommandEndpoint:
    def test_dispatch_omits_fields_the_handler_does_not_accept(
        self, client, monkeypatch
    ):
        received = {}

        def resume(*, initiative_id, actor):
            received.update(initiative_id=initiative_id, actor=actor)
            return CommandResult(ok=True, action="resume", detail="resumed")

        monkeypatch.setitem(builder_route._COMMAND_HANDLERS, "resume", resume)

        response = client.post(
            "/builder/command",
            json={
                "action": "resume",
                "initiative_id": "initiative-1",
                "reason": "continue work",
                "expected_version": 5,
                "actor": "test",
            },
        )

        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert received == {"initiative_id": "initiative-1", "actor": "test"}

    def test_unknown_action_returns_error_with_available(self, client):
        response = client.post(
            "/builder/command", json={"action": "nonexistent_action"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert "unknown action" in body["error"]
        assert isinstance(body.get("available"), list)
        assert len(body["available"]) > 0

    def test_legacy_action_route_is_not_registered(self, client):
        response = client.post("/builder/action", json={"action": "resume"})
        assert response.status_code == 404

    def test_approved_mission_route_materializes_durable_work(self, client, monkeypatch, tmp_path):
        from gateway import builder_initiative

        db_path = tmp_path / "builder_queue.db"
        monkeypatch.setattr(builder_route, "BUILDER_QUEUE_DB", db_path)
        monkeypatch.setattr(builder_route, "PROJECT_ROOT", tmp_path)
        response = client.post(
            "/builder/initiative",
            json={
                "mission_id": "route-mission-v1",
                "objective": "Persist this approved mission",
                "approved_at": "2026-08-08T00:00:00Z",
                "state": "approved",
                "origin": {"base_sha": "a" * 40},
                "execution": {"allowed_paths": ["gateway/routes/builder.py"]},
                "evidence_plan": {
                    "acceptance_criteria": [{"description": "a task is durable"}]
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "created"
        assert body["initiative_id"] == "route-mission-v1"
        assert builder_initiative.get_initiative(
            "route-mission-v1", db_path=db_path
        )["manifest"]["packets"][0]["id"] == "P1"

    def test_requeue_missing_task_id_raises(self, client):
        response = client.post("/builder/command", json={"action": "requeue"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body.get("error") is not None

    def test_cancel_missing_task_id_returns_error(self, client):
        response = client.post("/builder/command", json={"action": "cancel"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body.get("error") is not None

    def test_pause_missing_initiative_id_returns_error(self, client):
        response = client.post("/builder/command", json={"action": "pause"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body.get("error") is not None

    def test_resume_missing_initiative_id_returns_error(self, client):
        response = client.post("/builder/command", json={"action": "resume"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body.get("error") is not None

    def test_recover_stale_succeeds(self, client):
        response = client.post(
            "/builder/command", json={"action": "recover_stale"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["action"] == "recover_stale"
        assert body.get("detail") is not None

    def test_run_validation_missing_task_id_returns_error(self, client):
        response = client.post(
            "/builder/command", json={"action": "run_validation"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body.get("error") is not None

    def test_publish_missing_task_id_returns_error(self, client):
        response = client.post("/builder/command", json={"action": "publish"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body.get("error") is not None

    def test_all_actions_return_structured_result(self, client):
        from gateway.routes.builder import _COMMAND_HANDLERS

        for action in sorted(_COMMAND_HANDLERS.keys()):
            response = client.post(
                "/builder/command",
                json={
                    "action": action,
                    "task_id": "nonexistent-12345",
                    "initiative_id": "nonexistent-12345",
                    "reason": "test",
                    "actor": "test",
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert "ok" in body
            assert "action" in body
            assert body["action"] == action

    def test_expected_version_passed_but_accepted(self, client):
        response = client.post(
            "/builder/command",
            json={
                "action": "recover_stale",
                "expected_version": 5,
                "actor": "test",
            },
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_actor_defaults_to_cockpit_operator_when_missing(self, client):
        response = client.post(
            "/builder/command",
            json={"action": "recover_stale"},
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True


class TestEventStreamRoute:
    @pytest.fixture(autouse=True)
    def _patch_events(self, monkeypatch):
        """Patch builder_events.subscribe to return a single message then stop."""

        async def _fake_subscribe(client_id, cursor=None, packet_id=None):
            yield "data: test\n\n"

        monkeypatch.setattr(
            "gateway.routes.builder.builder_events.subscribe",
            _fake_subscribe,
        )

    def test_get_events_stream_returns_200(self, client):
        response = client.get("/builder/events")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_events_with_packet_id(self, client):
        response = client.get(
            "/builder/events", params={"packet_id": "kb_test"}
        )
        assert response.status_code == 200

    def test_events_with_cursor(self, client):
        response = client.get(
            "/builder/events",
            params={"cursor": 0, "session_id": "test-session"},
        )
        assert response.status_code == 200
