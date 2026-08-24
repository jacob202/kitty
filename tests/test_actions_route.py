"""Tests for the /actions routes (P3) — lifecycle + tier enforcement over HTTP."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import action_grants, action_queue, calendar_integration, todo_store
from gateway.routes import actions as actions_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(action_queue, "ACTIONS_DB_FILE", db_file, raising=False)
    # The grant store binds its own path at import, so it needs redirecting too
    # or the policy layer reads real data while the queue reads the temp DB.
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(action_queue, "DRAFTS_DIR", tmp_path / "drafts", raising=False)
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(calendar_integration, "create", lambda *a, **k: True)
    action_queue.reload_registry()
    app = FastAPI()
    app.include_router(actions_route.router)
    yield TestClient(app)
    action_queue.reload_registry()


def _propose(client, kind, payload):
    return client.post(
        "/actions/propose",
        json={
            "source_kind": "manual",
            "kind": kind,
            "title": f"{kind} action",
            "preview": f"will run {kind}",
            "payload": payload,
        },
    )


def test_propose_returns_proposed_action(client):
    r = _propose(client, "todo.create", {"content": "ship it"})

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "proposed"
    assert body["risk_tier"] == "T0"


def test_t0_execute_from_proposed_over_http(client):
    action_id = _propose(client, "todo.create", {"content": "ship it"}).json()["id"]

    r = client.post(f"/actions/{action_id}/execute")

    assert r.status_code == 200
    assert r.json()["status"] == "executed"


def test_t2_execute_without_approval_returns_403(client):
    action_id = _propose(client, "calendar.event.create", {"title": "Dentist"}).json()["id"]

    r = client.post(f"/actions/{action_id}/execute")

    assert r.status_code == 403


def test_t2_approve_then_execute_over_http(client):
    action_id = _propose(client, "calendar.event.create", {"title": "Dentist"}).json()["id"]

    assert client.post(f"/actions/{action_id}/approve").status_code == 200
    r = client.post(f"/actions/{action_id}/execute")

    assert r.status_code == 200
    assert r.json()["status"] == "executed"


def test_action_changed_after_approval_returns_409_not_500(client):
    """A stale approval is a conflict the user can act on, not a server crash."""
    import json

    action_id = _propose(client, "calendar.event.create", {"title": "Dentist"}).json()["id"]
    assert client.post(f"/actions/{action_id}/approve").status_code == 200

    with action_queue.kitty_db.connect(action_queue.ACTIONS_DB_FILE) as conn:
        conn.execute(
            "UPDATE actions SET payload = ? WHERE id = ?",
            (json.dumps({"title": "Wire $5000"}), action_id),
        )
        conn.commit()

    r = client.post(f"/actions/{action_id}/execute")

    assert r.status_code == 409
    assert "fresh approval required" in r.json()["detail"]


def test_disabled_kind_returns_400(client):
    r = _propose(client, "email.send", {"content": "hi"})

    assert r.status_code == 400


def test_missing_payload_field_returns_400(client):
    r = _propose(client, "todo.create", {})

    assert r.status_code == 400


def test_execute_missing_action_returns_404(client):
    r = client.post("/actions/999999/execute")

    assert r.status_code == 404


def test_list_actions_filters_by_status(client):
    _propose(client, "todo.create", {"content": "one"})

    r = client.get("/actions", params={"status": "proposed"})

    assert r.status_code == 200
    actions = r.json()["actions"]
    assert len(actions) == 1
    assert actions[0]["kind"] == "todo.create"


# --- grants (issue #554) ---------------------------------------------------


def _grant(client, capability, decision, **kw):
    body = {
        "capability": capability,
        "decision": decision,
        "granted_tier": kw.pop("granted_tier", "T2"),
        "reason": kw.pop("reason", "chosen in the approval dialog"),
    }
    body.update(kw)
    return client.post("/actions/grants", json=body)


def test_grant_route_records_restrictions_with_gateway_provenance(client):
    created = _grant(client, "calendar.event.create", "deny", scope_type="project", scope_id="kitty")

    assert created.status_code == 200
    assert created.json()["decision"] == "deny"
    assert created.json()["created_by"] == "gateway_client"

    listed = client.get("/actions/grants")
    assert listed.status_code == 200
    assert [g["id"] for g in listed.json()["grants"]] == [created.json()["id"]]


def test_grant_route_cannot_mint_standing_allow(client):
    created = _grant(client, "calendar.event.create", "allow", scope_type="project", scope_id="kitty")
    assert created.status_code == 400
    assert "user-confirmed" in created.json()["detail"]


def test_grant_route_rejects_an_invalid_scope(client):
    r = _grant(client, "calendar.event.create", "allow", scope_type="galaxy", scope_id="x")

    assert r.status_code == 400


def test_granted_action_executes_over_http_without_per_action_approval(client):
    action_grants.create_grant(
        capability="calendar.event.create", decision="allow", granted_tier="T2",
        reason="confirmed by user", scope_type="project", scope_id="kitty",
        created_by="user", user_confirmed=True,
    )
    proposed = client.post(
        "/actions/propose",
        json={
            "source_kind": "manual",
            "kind": "calendar.event.create",
            "title": "standup",
            "preview": "will create a calendar event",
            "payload": {"title": "standup"},
            "scope_type": "project",
            "scope_id": "kitty",
        },
    ).json()

    r = client.post(f"/actions/{proposed['id']}/execute")

    assert r.status_code == 200
    assert r.json()["status"] == "executed"


def test_denied_action_returns_403_over_http(client):
    _grant(client, "todo.create", "deny", granted_tier="T0")
    proposed = _propose(client, "todo.create", {"content": "nope"}).json()

    r = client.post(f"/actions/{proposed['id']}/execute")

    assert r.status_code == 403


def test_revoking_a_grant_restores_the_approval_requirement(client):
    grant = action_grants.create_grant(
        capability="calendar.event.create", decision="allow", granted_tier="T2",
        reason="confirmed by user", scope_type="project", scope_id="kitty",
        created_by="user", user_confirmed=True,
    )
    client.delete(f"/actions/grants/{grant['id']}")

    proposed = client.post(
        "/actions/propose",
        json={
            "source_kind": "manual",
            "kind": "calendar.event.create",
            "title": "standup",
            "preview": "will create a calendar event",
            "payload": {"title": "standup"},
            "scope_type": "project",
            "scope_id": "kitty",
        },
    ).json()

    r = client.post(f"/actions/{proposed['id']}/execute")

    assert r.status_code == 403


def test_revoking_a_missing_grant_returns_404(client):
    r = client.delete("/actions/grants/999999")

    assert r.status_code == 404


# --- "always allow here" over HTTP (issue #554 finding 1) -------------------


def _propose_scoped(client, kind, payload, **scope):
    body = {
        "source_kind": "manual",
        "kind": kind,
        "title": f"{kind} action",
        "preview": f"will run {kind}",
        "payload": payload,
    }
    body.update(scope)
    return client.post("/actions/propose", json=body).json()


def test_approve_without_a_body_still_works(client):
    # Backward compatibility: the body is optional, so existing callers that
    # send none must keep behaving exactly as before.
    proposed = _propose(client, "calendar.event.create", {"title": "x"}).json()

    r = client.post(f"/actions/{proposed['id']}/approve")

    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert "grant" not in r.json()


def test_approve_with_remember_records_the_standing_grant(client):
    proposed = _propose_scoped(
        client, "calendar.event.create", {"title": "standup"},
        scope_type="project", scope_id="kitty",
    )

    r = client.post(f"/actions/{proposed['id']}/approve", json={"remember": {}})

    assert r.status_code == 200
    grant = r.json()["grant"]
    assert grant["decision"] == "allow"
    assert grant["capability"] == "calendar.event.create"
    assert grant["scope_type"] == "project"
    assert grant["scope_id"] == "kitty"
    assert grant["created_by"] == "user"

    # And the next one of the same kind no longer needs approving.
    nxt = _propose_scoped(
        client, "calendar.event.create", {"title": "retro"},
        scope_type="project", scope_id="kitty",
    )
    assert client.post(f"/actions/{nxt['id']}/execute").json()["status"] == "executed"


def test_the_grant_route_still_cannot_mint_an_allow(client):
    # The reported hole: a Gateway client minting its own standing permission.
    # Bearer auth proves possession of the shared secret, not the user's intent.
    r = _grant(client, "calendar.event.create", "allow", scope_type="project", scope_id="kitty")

    assert r.status_code == 400
    assert "user-confirmed" in r.json()["detail"]


def test_the_grant_route_can_still_record_a_restriction(client):
    # deny/ask only ever narrow what is permitted, so they stay available.
    r = _grant(client, "calendar.event.create", "deny", scope_type="project", scope_id="kitty")

    assert r.status_code == 200
    assert r.json()["decision"] == "deny"


def test_remember_on_a_missing_action_is_a_404_and_grants_nothing(client):
    r = client.post("/actions/999999/approve", json={"remember": {}})

    assert r.status_code == 404
    assert client.get("/actions/grants").json()["grants"] == []


def test_remember_on_an_already_decided_action_grants_nothing(client):
    proposed = _propose(client, "calendar.event.create", {"title": "x"}).json()
    client.post(f"/actions/{proposed['id']}/reject")

    r = client.post(f"/actions/{proposed['id']}/approve", json={"remember": {}})

    assert r.status_code == 409
    assert client.get("/actions/grants").json()["grants"] == []


# --- COR-002: a bad "remember" must not hide a durably committed approval --


def test_invalid_remember_still_reports_the_approval_that_already_committed(client):
    """A bad remember request used to raise 400 and discard the approved body.

    The action's proposed -> approved transition is committed the moment
    action_queue.approve() returns; nothing about the later grant step can
    undo it. The response must say so, not look like the whole request
    failed.
    """
    proposed = _propose(client, "calendar.event.create", {"title": "x"}).json()
    assert proposed["session_id"] is None

    r = client.post(
        f"/actions/{proposed['id']}/approve",
        json={"remember": {"session_only": True}},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "approved"
    assert "grant" not in body
    assert "no session" in body["grant_error"]
    assert client.get("/actions/grants").json()["grants"] == []

    # The approval really did commit — a bare re-approve now correctly 409s,
    # never a silent duplicate.
    again = client.post(f"/actions/{proposed['id']}/approve")
    assert again.status_code == 409


def test_invalid_remember_expiry_still_reports_the_approval_that_already_committed(client):
    proposed = _propose(client, "calendar.event.create", {"title": "x"}).json()

    r = client.post(
        f"/actions/{proposed['id']}/approve",
        json={"remember": {"expires_at": 1.0}},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "approved"
    assert "grant" not in body
    assert "future" in body["grant_error"]
    assert client.get("/actions/grants").json()["grants"] == []
