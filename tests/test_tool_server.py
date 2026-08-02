"""The tool surface Open WebUI is given."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.routes import tool_server

client = TestClient(app)


def test_the_spec_lists_only_kitty_tools():
    """Open WebUI turns every operation in this spec into a tool the model sees.

    The Gateway's own /openapi.json describes the whole application; handing that
    over would bury the useful operations and cost a fortune in prompt.
    """
    spec = tool_server.tool_server_openapi()

    assert set(spec["paths"]) == {
        "/tools/v1/memory/search",
        "/tools/v1/memory/remember",
        "/tools/v1/notes/search",
        "/tools/v1/projects",
        "/tools/v1/projects/{project_id}/next-step",
        "/tools/v1/calendar/today",
        "/tools/v1/tutor/ask",
        "/tools/v1/builder/status",
    }


def test_every_operation_tells_the_model_what_it_is_for():
    """A tool with no summary is a tool the model calls by accident."""
    spec = tool_server.tool_server_openapi()

    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            assert operation.get("summary"), f"{method.upper()} {path}"


def test_the_spec_names_a_reachable_server():
    spec = tool_server.tool_server_openapi()

    assert spec["servers"] == [{"url": "http://127.0.0.1:8000"}]


def test_builder_status_never_returns_the_initiative_corpus():
    """The raw snapshot is 425KB here. A tool result goes into the model's
    context verbatim, so this one reports counts and what needs a human."""
    snapshot = {
        "queue": {"total": 3, "queued": 1},
        "initiatives": [
            {
                "title": "an initiative",
                "packets": [
                    {"title": "fine", "task_state": "done", "body": "x" * 10_000},
                    {
                        "title": "stuck",
                        "task_state": "blocked",
                        "blocked_reason": "needs a decision",
                        "body": "x" * 10_000,
                    },
                ],
            }
        ],
    }

    with patch.object(tool_server, "_ATTENTION_STATES", {"blocked", "failed"}), patch(
        "gateway.builder_status.build_status_snapshot", return_value=snapshot
    ):
        result = tool_server.builder_status()

    assert result["queue"] == {"total": 3, "queued": 1}
    assert result["initiative_count"] == 1
    assert [item["packet"] for item in result["needs_attention"]] == ["stuck"]
    assert "body" not in str(result)


def test_a_backend_failure_is_reported_not_swallowed():
    with patch("gateway.project_store.list_projects", side_effect=RuntimeError("db gone")):
        with pytest.raises(Exception) as excinfo:
            tool_server.list_projects()

    assert "db gone" in str(excinfo.value)


def test_the_tools_are_behind_the_gateway_secret(monkeypatch):
    """These read Jacob's memory and notes. Unauthenticated access is a leak."""
    monkeypatch.setenv("GATEWAY_SECRET", "the-secret")
    monkeypatch.delenv("KITTY_ENV", raising=False)

    assert client.get("/tools/v1/projects").status_code == 401


def test_the_model_gets_readable_tool_names():
    """FastAPI derives operationId from the function name plus the path, so the
    model would be choosing between names like
    "builder_status_tools_v1_builder_status_get"."""
    spec = tool_server.tool_server_openapi()

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
    }


def test_an_empty_tutor_library_is_an_answer_not_a_failure():
    """"I have nothing ingested on this" is a fact about the library. Raising
    would make the model retry or report a crash instead of relaying the one
    instruction that fixes it."""
    from gateway import tutor

    with patch.object(
        tutor, "ask", side_effect=tutor.TutorError("no docs on X. Run: kitty tutor learn <path>")
    ):
        result = asyncio.run(tool_server.ask_tutor("X"))

    assert result["grounded"] is False
    assert "kitty tutor learn" in result["reason"]
