"""The bounded tool surface Open WebUI is given."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.models.builder import Mission
from gateway.routes import tool_server

client = TestClient(app)


def _spec(server_url: str = "http://127.0.0.1:8123") -> dict:
    return tool_server._tool_server_spec(server_url)


def test_the_spec_lists_only_kitty_tools():
    """The model must not receive the Gateway's hundreds of internal routes."""
    spec = _spec()

    assert set(spec["paths"]) == {
        "/tools/v1/memory/search",
        "/tools/v1/memory/remember",
        "/tools/v1/notes/search",
        "/tools/v1/projects",
        "/tools/v1/projects/{project_id}/next-step",
        "/tools/v1/calendar/today",
        "/tools/v1/tutor/ask",
        "/tools/v1/builder/status",
        "/tools/v1/builder/mission",
        "/tools/v1/builder/mission/{mission_id}",
    }


def test_every_operation_tells_the_model_what_it_is_for():
    spec = _spec()

    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            assert operation.get("summary"), f"{method.upper()} {path}"


def test_the_spec_uses_the_actual_gateway_origin():
    spec = _spec("http://127.0.0.1:8765/")

    assert spec["servers"] == [{"url": "http://127.0.0.1:8765"}]


def test_result_limits_are_small_positive_openapi_parameters():
    spec = _spec()

    for path in ("/tools/v1/memory/search", "/tools/v1/notes/search"):
        parameters = {
            parameter["name"]: parameter["schema"]
            for parameter in spec["paths"][path]["get"]["parameters"]
        }
        assert parameters["limit"]["minimum"] == 1
        assert parameters["limit"]["maximum"] == 10


def test_memory_search_uses_the_unified_graph_and_bounds_rendered_items():
    context = "## Journal\n- one\n- two\n\n## Inbox\n- three"

    with patch("gateway.memory_graph.unified_context", return_value=context) as search:
        result = asyncio.run(tool_server.search_memory("remember", limit=2))

    search.assert_awaited_once_with("remember", _record=False)
    assert result["context"] == "## Journal\n- one\n- two"
    assert result["result_limit"] == 2


def test_projects_are_life_first_not_creation_order():
    projects = [
        {"id": 1, "name": "kitty", "kind": "code"},
        {"id": 2, "name": "benefits-admin", "kind": "admin"},
    ]

    with patch("gateway.project_store.list_projects", return_value=projects):
        result = tool_server.list_projects()

    assert [project["name"] for project in result["projects"]] == [
        "benefits-admin",
        "kitty",
    ]


def test_missing_next_step_is_a_normal_nullable_result():
    with patch("gateway.next_step.get", return_value=None):
        result = tool_server.project_next_step(7)

    assert result == {"project_id": 7, "available": False, "next_step": None}


def test_builder_status_uses_the_read_only_control_plane_projection():
    snapshot = {
        "queue": {"total": 3, "queued": 1},
        "initiatives": [
            {
                "title": "fine",
                "state": "running",
                "pause_reason": None,
                "packet_count": 20,
            },
            {
                "title": "stuck",
                "state": "blocked",
                "pause_reason": "needs a decision",
                "packet_count": 40,
            },
        ],
    }

    with patch(
        "gateway.builder_status.build_control_plane_summary", return_value=snapshot
    ) as build:
        result = tool_server.builder_status()

    build.assert_called_once()
    assert result["queue"] == {"total": 3, "queued": 1}
    assert result["initiative_count"] == 2
    assert result["needs_attention"] == [
        {
            "initiative": "stuck",
            "state": "blocked",
            "reason": "needs a decision",
        }
    ]
    assert "packets" not in str(result)


def test_absent_builder_database_is_unavailable_not_empty_success():
    with patch(
        "gateway.builder_status.build_control_plane_summary",
        side_effect=FileNotFoundError("missing queue"),
    ):
        with pytest.raises(Exception) as excinfo:
            tool_server.builder_status()

    assert "builder unavailable" in str(excinfo.value)


def test_a_backend_failure_is_reported_not_swallowed():
    with patch("gateway.project_store.list_projects", side_effect=RuntimeError("db gone")):
        with pytest.raises(Exception) as excinfo:
            tool_server.list_projects()

    assert "db gone" in str(excinfo.value)


def test_the_tools_are_behind_the_gateway_secret(monkeypatch):
    monkeypatch.setenv("GATEWAY_SECRET", "the-secret")
    monkeypatch.delenv("KITTY_ENV", raising=False)

    assert client.get("/tools/v1/projects").status_code == 401


def test_the_model_gets_readable_tool_names():
    spec = _spec()

    names = {
        operation["operationId"]
        for operations in spec["paths"].values()
        for operation in operations.values()
    }

    assert names == {
        "search_memory",
        "remember",
        "search_notes",
        "list_projects",
        "project_next_step",
        "calendar_today",
        "ask_tutor",
        "builder_status",
        "submit_builder_mission",
        "builder_mission_result",
    }


def test_submit_builder_mission_delegates_to_durable_builder_boundary(monkeypatch):
    mission = Mission(mission_id="tool-mission", objective="Ship the bounded change")
    expected = {"status": "created", "initiative_id": mission.mission_id}

    from gateway import builder_initiative

    monkeypatch.setattr(builder_initiative, "submit_mission", lambda *args, **kwargs: expected)

    assert tool_server.submit_builder_mission(mission) == expected


def test_builder_mission_result_uses_read_only_projection(monkeypatch):
    snapshot = {
        "initiatives": [
            {
                "initiative_id": "tool-mission",
                "state": "completed",
                "packets": [{"packet_id": "P1", "attempt_history": []}],
            }
        ]
    }
    from gateway import builder_status_readonly

    monkeypatch.setattr(
        builder_status_readonly,
        "build_status_snapshot_readonly",
        lambda **kwargs: snapshot,
    )

    result = tool_server.builder_mission_result("tool-mission")

    assert result == {"mission_id": "tool-mission", "result": snapshot["initiatives"][0]}


def test_builder_mission_result_reports_missing_mission(monkeypatch):
    from gateway import builder_status_readonly

    monkeypatch.setattr(
        builder_status_readonly,
        "build_status_snapshot_readonly",
        lambda **kwargs: {"initiatives": []},
    )

    with pytest.raises(Exception) as excinfo:
        tool_server.builder_mission_result("missing-mission")

    assert "was not found" in str(excinfo.value)


def test_an_empty_tutor_library_is_an_answer_not_a_failure():
    from gateway import tutor

    with patch.object(
        tutor,
        "ask",
        side_effect=tutor.TutorError("no docs on X. Run: kitty tutor learn <path>"),
    ):
        result = asyncio.run(tool_server.ask_tutor("X"))

    assert result["grounded"] is False
    assert "kitty tutor learn" in result["reason"]
