"""Tests for the /builder/conversation HTTP surface (routing/validation only).

Delegation correctness (propose/approve/resume semantics, idempotency,
Builder authority) is covered by ``tests/test_conversation_handoff.py``
against the real functions. These tests only prove the route layer parses
requests correctly and calls straight through to ``gateway.conversation_handoff``.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import conversation_handoff
from gateway.routes import conversation_handoff as route


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(route.router)
    return TestClient(app)


def test_propose_route_defaults_and_delegates(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    received = {}

    def fake_propose(**kwargs):
        received.update(kwargs)
        return {"ok": True, "state": "prepared"}

    monkeypatch.setattr(conversation_handoff, "propose", fake_propose)

    response = client.post(
        "/builder/conversation/propose",
        json={
            "objective": "Fix the bug",
            "instructions": "Do the fix",
            "allowed_paths": ["gateway/"],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "state": "prepared"}
    assert received["objective"] == "Fix the bug"
    assert received["initiative_id"] is None
    assert received["acceptance_criteria"] is None


def test_approve_route_defaults_confirmed_false(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    received = {}

    def fake_approve(**kwargs):
        received.update(kwargs)
        return {"ok": False, "state": "needs_approval", "error_code": "approval_required"}

    monkeypatch.setattr(conversation_handoff, "approve", fake_approve)

    response = client.post(
        "/builder/conversation/approve",
        json={
            "prepared_manifest": {"initiative_id": "conv-1"},
            "expected_manifest_sha": "a" * 64,
            "expected_base_sha": "b" * 40,
            "approval_nonce": "c" * 64,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "approval_required"
    assert received["confirmed"] is False


def test_approve_route_passes_through_explicit_confirmation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    received = {}

    def fake_approve(**kwargs):
        received.update(kwargs)
        return {"ok": True, "state": "accepted", "mission_id": "conv-1"}

    monkeypatch.setattr(conversation_handoff, "approve", fake_approve)

    response = client.post(
        "/builder/conversation/approve",
        json={
            "prepared_manifest": {"initiative_id": "conv-1"},
            "expected_manifest_sha": "a" * 64,
            "expected_base_sha": "b" * 40,
            "approval_nonce": "c" * 64,
            "confirmed": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["mission_id"] == "conv-1"
    assert received["confirmed"] is True


def test_resume_route_accepts_query_params(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    received = {}

    def fake_resume(*, mission_id=None, task_id=None):
        received.update(mission_id=mission_id, task_id=task_id)
        return {"mission": {"id": mission_id}}

    monkeypatch.setattr(conversation_handoff, "resume", fake_resume)

    response = client.get("/builder/conversation/resume", params={"mission_id": "conv-1"})

    assert response.status_code == 200
    assert response.json() == {"mission": {"id": "conv-1"}}
    assert received == {"mission_id": "conv-1", "task_id": None}


def test_propose_route_rejects_empty_allowed_paths(client: TestClient) -> None:
    response = client.post(
        "/builder/conversation/propose",
        json={"objective": "x", "instructions": "y", "allowed_paths": []},
    )
    assert response.status_code == 422


def test_propose_route_translates_raw_planning_artifact_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A raw exception string from the repo/planning-artifact layer must never
    reach the chat UI -- only the stable error_code and a plain-language
    message. See DEFECTS-rc0.md's raw-error-copy class of finding."""

    def fake_propose(**kwargs):
        return {
            "ok": False,
            "state": "needs_decision",
            "error_code": "planning_artifact_failed",
            "error": "GitCommandError: git commit -m docs: save MCP design conv-x exited 1: "
            "ERROR: no Kitty agent session is established for this worktree; run kitty agent claim first",
            "next_action": "Resolve the planning-artifact error and propose again.",
        }

    monkeypatch.setattr(conversation_handoff, "propose", fake_propose)

    response = client.post(
        "/builder/conversation/propose",
        json={"objective": "Fix the bug", "instructions": "Do the fix", "allowed_paths": ["gateway/"]},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["error_code"] == "planning_artifact_failed"
    assert body["next_action"] == "Resolve the planning-artifact error and propose again."
    assert "GitCommandError" not in body["error"]
    assert "kitty agent claim" not in body["error"]


def test_propose_route_translates_unhandled_exception(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_propose(**kwargs):
        raise RuntimeError("sqlite3.OperationalError: database is locked at /private/tmp/x/kitty.db")

    monkeypatch.setattr(conversation_handoff, "propose", fake_propose)

    response = client.post(
        "/builder/conversation/propose",
        json={"objective": "Fix the bug", "instructions": "Do the fix", "allowed_paths": ["gateway/"]},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is False
    assert "sqlite3" not in body["error"]
    assert "/private/tmp" not in body["error"]


def test_compile_route_delegates_plain_language_request(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    received = {}

    def fake_compile(request: str):
        received["request"] = request
        return {"ok": True, "task": {"objective": "Add proof", "instructions": "Add it", "allowed_paths": ["proof.txt"]}}

    monkeypatch.setattr(conversation_handoff, "compile_request", fake_compile)
    response = client.post("/builder/conversation/compile", json={"request": "Add proof.txt"})

    assert response.status_code == 200
    assert response.json()["task"]["allowed_paths"] == ["proof.txt"]
    assert received == {"request": "Add proof.txt"}
