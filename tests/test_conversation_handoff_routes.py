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
