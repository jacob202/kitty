"""Unit tests for Magic Kitty cross-project connection discovery."""

import json
from unittest.mock import MagicMock

import pytest

from gateway import magic_kitty


@pytest.fixture(autouse=True)
def clean_cache(monkeypatch):
    monkeypatch.setattr(
        magic_kitty,
        "_LAST_CONNECTIONS_CACHE",
        {
            "connections": [],
            "generated_at": 0.0,
            "projects_used": 0,
        },
    )


def test_discover_connections_less_than_two_projects_caches_empty_result(monkeypatch):
    mock_list_projects = MagicMock(return_value=[{"id": 1, "name": "Project A"}])
    monkeypatch.setattr(magic_kitty.project_store, "list_projects", mock_list_projects)
    monkeypatch.setattr(
        magic_kitty,
        "project_resume",
        MagicMock(
            return_value={
                "name": "Project A",
                "kind": "code",
                "summary": "A",
                "open_questions": [],
            }
        ),
    )

    first = magic_kitty.discover_connections()
    second = magic_kitty.discover_connections()

    assert first["connections"] == []
    assert first["projects_used"] == 1
    assert second["generated_at"] == first["generated_at"]
    assert mock_list_projects.call_count == 1


def test_discover_connections_with_connections(monkeypatch):
    monkeypatch.setattr(
        magic_kitty.project_store,
        "list_projects",
        MagicMock(
            return_value=[
                {"id": 1, "name": "Project A"},
                {"id": 2, "name": "Project B"},
            ]
        ),
    )
    monkeypatch.setattr(
        magic_kitty,
        "project_resume",
        MagicMock(
            side_effect=[
                {
                    "name": "Project A",
                    "kind": "code",
                    "summary": "A",
                    "open_questions": [],
                },
                {
                    "name": "Project B",
                    "kind": "code",
                    "summary": "B",
                    "open_questions": [],
                },
            ]
        ),
    )

    fake_insight = {
        "insight_id": "test1",
        "kind": "pattern",
        "title": "Connected!",
        "detail": "Project A and B are connected.",
        "source": "Project A, Project B",
        "confidence": 0.9,
    }
    mock_call_llm = MagicMock(return_value=json.dumps([fake_insight]))
    monkeypatch.setattr(magic_kitty.llm_client, "call_llm", mock_call_llm)

    result = magic_kitty.discover_connections()

    assert len(result["connections"]) == 1
    assert result["connections"][0]["insight_id"] == "test1"
    assert result["connections"][0]["title"] == "Connected!"
    assert result["projects_used"] == 2
    assert mock_call_llm.call_count == 1


def test_discover_connections_caches_valid_empty_result(monkeypatch):
    monkeypatch.setattr(
        magic_kitty.project_store,
        "list_projects",
        MagicMock(
            return_value=[
                {"id": 1, "name": "Project A"},
                {"id": 2, "name": "Project B"},
            ]
        ),
    )
    monkeypatch.setattr(
        magic_kitty,
        "project_resume",
        MagicMock(
            side_effect=lambda pid: {
                "name": f"Project {pid}",
                "kind": "code",
                "summary": "x",
                "open_questions": [],
            }
        ),
    )

    mock_call_llm = MagicMock(return_value=json.dumps([]))
    monkeypatch.setattr(magic_kitty.llm_client, "call_llm", mock_call_llm)

    first = magic_kitty.discover_connections()
    second = magic_kitty.discover_connections()
    third = magic_kitty.discover_connections(force=True)

    assert mock_call_llm.call_count == 2
    assert second["generated_at"] == first["generated_at"]
    assert third["generated_at"] >= first["generated_at"]


def test_discover_connections_uses_local_privacy_tier_for_synthesis(monkeypatch):
    """D10: cross-project synthesis must stay local-tier, never cloud.

    Magic Kitty aggregates every active project, including benefits-admin
    (health_admin content). Assert the captured call_llm kwargs prove a cloud
    leak is structurally impossible for this route — mirrors 016's privacy
    acceptance criterion.
    """
    monkeypatch.setattr(
        magic_kitty.project_store,
        "list_projects",
        MagicMock(
            return_value=[
                {"id": 1, "name": "kitty"},
                {"id": 2, "name": "benefits-admin"},
            ]
        ),
    )
    monkeypatch.setattr(
        magic_kitty,
        "project_resume",
        MagicMock(
            side_effect=lambda pid: {
                "name": f"project-{pid}",
                "kind": "admin" if pid == 2 else "code",
                "summary": "x",
                "open_questions": [],
            }
        ),
    )

    mock_call_llm = MagicMock(return_value=json.dumps([]))
    monkeypatch.setattr(magic_kitty.llm_client, "call_llm", mock_call_llm)

    magic_kitty.discover_connections()

    _, kwargs = mock_call_llm.call_args
    assert kwargs.get("privacy_tier") == "local", kwargs
    assert kwargs.get("content_class") == "health_admin", kwargs
    assert kwargs.get("model") == "kitty-default", kwargs


def test_discover_connections_does_not_cache_llm_failure(monkeypatch):
    monkeypatch.setattr(
        magic_kitty.project_store,
        "list_projects",
        MagicMock(
            return_value=[
                {"id": 1, "name": "Project A"},
                {"id": 2, "name": "Project B"},
            ]
        ),
    )
    monkeypatch.setattr(
        magic_kitty,
        "project_resume",
        MagicMock(
            side_effect=lambda pid: {
                "name": f"Project {pid}",
                "kind": "code",
                "summary": "x",
                "open_questions": [],
            }
        ),
    )
    mock_call_llm = MagicMock(side_effect=[RuntimeError("upstream boom"), json.dumps([])])
    monkeypatch.setattr(magic_kitty.llm_client, "call_llm", mock_call_llm)

    with pytest.raises(RuntimeError, match="magic_kitty LLM call failed"):
        magic_kitty.discover_connections()

    result = magic_kitty.discover_connections()

    assert result["connections"] == []
    assert mock_call_llm.call_count == 2


def test_discover_connections_raises_on_resume_failure(monkeypatch):
    monkeypatch.setattr(
        magic_kitty.project_store,
        "list_projects",
        MagicMock(return_value=[{"id": 7, "name": "Project Broken"}]),
    )
    monkeypatch.setattr(
        magic_kitty,
        "project_resume",
        MagicMock(side_effect=ValueError("missing state")),
    )

    with pytest.raises(
        RuntimeError,
        match="magic_kitty failed to build resume for project 7",
    ):
        magic_kitty.discover_connections()
