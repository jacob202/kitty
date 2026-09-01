"""Truthful "why didn't this happen?" explanations (QoL Packet 03).

Every meaningful automation/action must be able to explain non-execution using
existing evidence only: cron schedule state, the #550 Automation Run ledger,
action grants, and the supervisor. No parallel explanation store, no fake run
records.
"""

from __future__ import annotations

import sqlite3
import time

import pytest


@pytest.fixture
def automation_db(tmp_path, monkeypatch):
    import gateway.automation_actions as actions
    from gateway import action_grants, automation_runs, cron
    from gateway import db as kitty_db

    db_file = tmp_path / "kitty.db"
    kitty_db.migrate(db_file=db_file)
    monkeypatch.setattr(automation_runs, "DB_FILE", db_file)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_file)
    monkeypatch.setattr(cron, "KITTY_DB_FILE", db_file)
    actions.clear_registry()
    cron._runner_task = None
    yield db_file
    actions.clear_registry()
    cron._runner_task = None


@pytest.fixture
def supervisor_control(monkeypatch):
    import gateway.why_not as why_not
    from gateway.automation_supervisor import AutomationSupervisor

    control = AutomationSupervisor()
    monkeypatch.setattr(why_not, "supervisor", control)
    return control


def _set_last_run(db_file, sid: str, value: float) -> None:
    with sqlite3.connect(db_file) as conn:
        conn.execute("UPDATE cron_schedules SET last_run = ? WHERE id = ?", (value, sid))
        conn.commit()


def test_not_yet_due_explains_without_fake_rows(automation_db):
    import gateway.why_not as why_not
    from gateway import automation_runs, cron

    sid = cron.schedule("pending", "test.wait", "interval", "1")
    _set_last_run(automation_db, sid, 99.0)

    explanation = why_not.explain_schedule(sid, now=100.0)

    assert explanation.status == "not_due"
    assert "not due yet" in explanation.reason
    assert explanation.action == "test.wait"
    assert explanation.automation == sid
    assert explanation.relevant_at == 159.0
    assert explanation.evidence["schedule_state"] == "not_due"
    assert automation_runs.list_runs(automation_id=sid) == []


def test_disabled_schedule_explains_disabled(automation_db):
    import gateway.why_not as why_not
    from gateway import cron

    sid = cron.schedule("paused", "test.pause", "interval", "1")
    assert cron.toggle(sid) is False

    explanation = why_not.explain_schedule(sid, now=100.0)

    assert explanation.status == "disabled"
    assert "disabled" in explanation.reason
    assert explanation.evidence["schedule_state"] == "disabled"
    assert explanation.next_step


def test_due_occurrence_already_claimed(automation_db):
    import gateway.why_not as why_not
    from gateway import automation_runs, cron

    sid = cron.schedule("claimed", "test.claim", "interval", "1")
    _set_last_run(automation_db, sid, 40.0)
    run = automation_runs.begin_run(
        automation_id=sid,
        action="test.claim",
        trigger_kind="time",
        schedule_id=sid,
        due_at=100.0,
        started_at=100.0,
    )

    explanation = why_not.explain_schedule(sid, now=100.0)

    assert explanation.status == "claimed"
    assert "claimed" in explanation.reason
    assert explanation.evidence["run_id"] == run["id"]
    assert explanation.evidence["run_status"] == "running"


@pytest.mark.parametrize(
    ("run_status", "reason_fragment"),
    [
        ("source_unavailable", "source was unavailable"),
        ("condition_false", "condition was false"),
        ("policy_refused", "policy refused"),
    ],
)
def test_terminal_non_execution_reasons_explained(automation_db, run_status, reason_fragment):
    import gateway.why_not as why_not
    from gateway import automation_runs, cron

    sid = cron.schedule("non-exec", f"test.{run_status}", "interval", "1")
    _set_last_run(automation_db, sid, 40.0)
    run = automation_runs.begin_run(
        automation_id=sid,
        action=f"test.{run_status}",
        trigger_kind="time",
        schedule_id=sid,
        due_at=100.0,
        started_at=99.0,
    )
    automation_runs.finish_run(
        run["id"],
        status=run_status,
        completed_at=100.0,
        error="integration went away",
        policy={"outcome": "deny", "basis": "scoped_deny"},
    )

    explanation = why_not.explain_schedule(sid, now=100.0)

    assert explanation.status == run_status
    assert reason_fragment in explanation.reason
    assert explanation.evidence["run_id"] == run["id"]
    assert explanation.evidence["run_status"] == run_status
    assert explanation.relevant_at == 100.0


def test_manual_action_approval_required(automation_db):
    import gateway.automation_actions as actions
    import gateway.why_not as why_not

    async def execute(_payload):
        return None

    actions.register_action(
        "demo.gated", execute, policy=actions.ActionPolicy(capability="demo.gated", tier="T2")
    )

    explanation = why_not.explain_action("demo.gated", now=100.0)

    assert explanation.status == "approval_required"
    assert "requires approval" in explanation.reason
    assert explanation.evidence["decision"] == "ask"
    assert "approve" in explanation.next_step


def test_expired_grant_explained(automation_db):
    import gateway.action_grants as grants
    import gateway.automation_actions as actions
    import gateway.why_not as why_not

    async def execute(_payload):
        return None

    actions.register_action(
        "demo.expired", execute, policy=actions.ActionPolicy(capability="demo.expired", tier="T2")
    )
    grant = grants.create_grant(
        capability="demo.expired",
        decision="allow",
        granted_tier="T2",
        reason="standby",
        created_by="user",
        user_confirmed=True,
    )
    with sqlite3.connect(automation_db) as conn:
        conn.execute(
            "UPDATE action_grants SET expires_at = ? WHERE id = ?", (99.0, grant["id"])
        )
        conn.commit()

    explanation = why_not.explain_action("demo.expired", now=100.0)

    assert explanation.status == "grant_expired"
    assert "expired" in explanation.reason
    assert explanation.relevant_at == 99.0
    assert explanation.evidence["grant_id"] == grant["id"]


def test_revoked_grant_explained(automation_db):
    import gateway.action_grants as grants
    import gateway.automation_actions as actions
    import gateway.why_not as why_not

    async def execute(_payload):
        return None

    actions.register_action(
        "demo.revoked", execute, policy=actions.ActionPolicy(capability="demo.revoked", tier="T2")
    )
    grant = grants.create_grant(
        capability="demo.revoked",
        decision="allow",
        granted_tier="T2",
        reason="standby",
        created_by="user",
        user_confirmed=True,
    )
    grants.revoke_grant(grant["id"])

    explanation = why_not.explain_action("demo.revoked", now=100.0)

    assert explanation.status == "grant_revoked"
    assert "revoked" in explanation.reason
    assert explanation.evidence["grant_id"] == grant["id"]


def test_unregistered_action_explained(automation_db):
    import gateway.why_not as why_not

    explanation = why_not.explain_action("ghost.action", now=100.0)

    assert explanation.status == "action_unavailable"
    assert "not registered" in explanation.reason
    assert explanation.evidence["registered"] is False


def test_failed_run_explained(automation_db):
    import gateway.automation_actions as actions
    import gateway.why_not as why_not
    from gateway import automation_runs

    async def execute(_payload):
        return None

    actions.register_action("demo.fail", execute)
    run = automation_runs.begin_run(
        automation_id="manual:fail", action="demo.fail", trigger_kind="manual", started_at=99.0
    )
    automation_runs.finish_run(run["id"], status="failed", completed_at=100.0, error="RuntimeError: boom")

    explanation = why_not.explain_action("demo.fail", now=100.0)

    assert explanation.status == "failed"
    assert "boom" in explanation.reason
    assert explanation.relevant_at == 100.0
    assert explanation.evidence["run_id"] == run["id"]


def test_interrupted_run_explained(automation_db, monkeypatch):
    import gateway.automation_actions as actions
    import gateway.why_not as why_not
    from gateway import automation_runs

    monkeypatch.setattr(automation_runs, "PROCESS_STARTED_AT", 50.0)

    async def execute(_payload):
        return None

    actions.register_action("demo.interrupt", execute)
    run = automation_runs.begin_run(
        automation_id="manual:int", action="demo.interrupt", trigger_kind="manual", started_at=40.0
    )
    assert automation_runs.reconcile_interrupted_runs(now=125.0) == 1

    explanation = why_not.explain_action("demo.interrupt", now=125.0)

    assert explanation.status == "interrupted"
    assert "restarted" in explanation.reason
    assert "retry it explicitly" in explanation.next_step
    assert "may already have completed" in explanation.next_step
    assert explanation.evidence["run_id"] == run["id"]


def test_completed_run_explained(automation_db):
    import gateway.automation_actions as actions
    import gateway.why_not as why_not
    from gateway import automation_runs

    async def execute(_payload):
        return None

    actions.register_action("demo.ok", execute)
    run = automation_runs.begin_run(
        automation_id="manual:ok", action="demo.ok", trigger_kind="manual", started_at=99.0
    )
    automation_runs.finish_run(run["id"], status="completed", completed_at=100.0)

    explanation = why_not.explain_action("demo.ok", now=100.0)

    assert explanation.status == "completed"
    assert "ran successfully" in explanation.reason
    assert explanation.evidence["run_id"] == run["id"]


def test_completed_last_occurrence_is_not_reported_as_failure(automation_db):
    import gateway.why_not as why_not
    from gateway import automation_runs, cron

    sid = cron.schedule("fine", "test.fine", "interval", "1")
    _set_last_run(automation_db, sid, 50.0)
    run = automation_runs.begin_run(
        automation_id=sid,
        action="test.fine",
        trigger_kind="time",
        schedule_id=sid,
        due_at=40.0,
        started_at=40.0,
    )
    automation_runs.finish_run(run["id"], status="completed", completed_at=41.0)

    explanation = why_not.explain_schedule(sid, now=100.0)

    assert explanation.status == "not_due"


def test_execution_gap_when_cron_supervisor_stale(automation_db, supervisor_control):
    import gateway.why_not as why_not
    from gateway import cron

    sid = cron.schedule("gap", "test.gap", "interval", "1")
    _set_last_run(automation_db, sid, 40.0)
    supervisor_control.mark("cron", "stale", reason="service heartbeat is stale")

    explanation = why_not.explain_schedule(sid, now=100.0)

    assert explanation.status == "execution_gap"
    assert "no automation run was recorded" in explanation.reason
    assert explanation.evidence["schedule_state"] == "due"
    assert explanation.evidence["due_at"] == 100.0
    assert explanation.evidence["supervisor"]["status"] == "stale"


def test_due_occurrence_pending_claim_when_cron_available(automation_db, supervisor_control):
    import gateway.why_not as why_not
    from gateway import cron

    sid = cron.schedule("pending-claim", "test.pc", "interval", "1")
    _set_last_run(automation_db, sid, 40.0)
    supervisor_control.mark("cron", "available", reason="task running")

    explanation = why_not.explain_schedule(sid, now=100.0)

    assert explanation.status == "pending_claim"
    assert "waiting" in explanation.reason
    assert explanation.evidence["supervisor"]["status"] == "available"


def test_no_fake_run_rows_for_never_due_or_disabled(automation_db):
    import gateway.why_not as why_not
    from gateway import automation_runs, cron

    waiting = cron.schedule("never-due", "test.none", "interval", "1")
    _set_last_run(automation_db, waiting, 99.0)
    disabled = cron.schedule("disabled", "test.none2", "interval", "1")
    cron.toggle(disabled)

    assert why_not.explain_schedule(waiting, now=100.0).status == "not_due"
    assert why_not.explain_schedule(disabled, now=100.0).status == "disabled"
    assert automation_runs.list_runs(automation_id=waiting) == []
    assert automation_runs.list_runs(automation_id=disabled) == []


@pytest.mark.asyncio
async def test_schedule_why_route_returns_full_explanation(automation_db, supervisor_control):
    from gateway import cron
    from gateway.routes import automations

    sid = cron.schedule("route", "test.route", "interval", "1")
    _set_last_run(automation_db, sid, time.time() - 5.0)
    supervisor_control.mark("cron", "available", reason="task running")

    payload = await automations.schedule_why(sid)

    explanation = payload["explanation"]
    assert explanation["status"] == "not_due"
    assert explanation["action"] == "test.route"
    assert explanation["automation"] == sid
    assert set(
        ("status", "reason", "relevant_at", "action", "automation", "evidence", "next_step")
    ) <= set(explanation)


@pytest.mark.asyncio
async def test_schedule_why_route_404s_for_unknown_schedule(automation_db, supervisor_control):
    from fastapi import HTTPException

    from gateway.routes import automations

    with pytest.raises(HTTPException) as exc:
        await automations.schedule_why("does-not-exist")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_action_why_route_returns_explanation(automation_db):
    from gateway.routes import automations

    payload = await automations.automation_why("ghost.action")

    explanation = payload["explanation"]
    assert explanation["status"] == "action_unavailable"
    assert explanation["action"] == "ghost.action"


def test_why_routes_are_mounted_on_gateway(automation_db, supervisor_control):
    from fastapi.testclient import TestClient

    from gateway import cron
    from gateway.app import app

    sid = cron.schedule("mounted", "test.mounted", "interval", "1")
    _set_last_run(automation_db, sid, time.time() - 5.0)
    supervisor_control.mark("cron", "available", reason="task running")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"/automations/schedules/{sid}/why")

    assert response.status_code == 200
    body = response.json()["explanation"]
    assert body["status"] == "not_due"
    assert body["automation"] == sid


# ---------------------------------------------------------------------------
# Work-item explanations: derive only from the existing Builder work projection
# ---------------------------------------------------------------------------


def _work_snapshot_for(items):
    """Build a minimal projected work snapshot for testing."""
    return {
        "schema_version": 1,
        "observed_at": "2026-08-13T12:00:00Z",
        "valid_until": "2026-08-13T12:00:30Z",
        "source": {"kind": "builder", "state": "available", "snapshot_schema_version": 2},
        "counts": {"total": len(items), "active": 0, "paused": 0, "failed": 0, "blocked": 0, "completed": 0, "ready": 0, "waiting": 0},
        "items": items,
    }


def _work_item(
    initiative_id,
    *,
    state="ready",
    blocker=None,
    next_action="claim",
    current_run=None,
    packet_id=None,
    failure_kind=None,
    updated_at="2026-08-13T12:00:00Z",
):
    """Build a minimal projected work item for testing."""
    packet = None
    if packet_id is not None:
        packet = {
            "id": packet_id,
            "title": f"title-{packet_id}",
            "objective": f"objective-{packet_id}",
            "task_id": f"task-{packet_id}",
            "task_state": "queued",
            "eligibility": {"state": "eligible", "blocked_by": []},
            "failure_kind": failure_kind,
            "next_action": next_action,
            "updated_at": updated_at,
        }
    return {
        "id": initiative_id,
        "title": f"initiative {initiative_id}",
        "state": state,
        "source": {"kind": "builder", "initiative_id": initiative_id, "packet_id": packet_id},
        "current_packet": packet,
        "current_run": current_run,
        "blocker": blocker,
        "next_action": next_action,
        "evidence": {
            "validation": None,
            "review": None,
            "publication": None,
            "approval": {"state": "unavailable", "reason": "no binding"},
        },
        "data_quality": {"state": "complete", "issues": []},
        "updated_at": updated_at,
    }


def test_explain_work_item_blocked():
    from gateway.why_not import explain_work_item

    item = _work_item(
        "blocked-1",
        state="blocked",
        blocker={"state": "blocked", "reason": "dependency: dep-1", "blocked_by": ["dep-1"]},
        next_action="wait for dep-1",
        packet_id="pkt-blocked",
    )

    explanation = explain_work_item(_work_snapshot_for([item]), "blocked-1")

    assert explanation.status == "blocked"
    assert "dependency: dep-1" in explanation.reason
    assert explanation.automation == "pkt-blocked"
    assert explanation.evidence["blocker"]["state"] == "blocked"
    assert explanation.next_step == "wait for dep-1"
    assert explanation.relevant_at is not None


def test_explain_work_item_failed_cites_validation():
    from gateway.why_not import explain_work_item

    item = _work_item(
        "failed-1",
        state="failed",
        packet_id="pkt-failed",
        failure_kind="validation",
    )
    item["evidence"]["validation"] = {
        "status": "failed",
        "command_count": 2,
        "failed_command_count": 1,
        "summary": "1 validation command failed (exit 1).",
    }

    explanation = explain_work_item(_work_snapshot_for([item]), "failed-1")

    assert explanation.status == "failed"
    assert "validation failed" in explanation.reason
    assert explanation.automation == "pkt-failed"
    assert explanation.evidence["validation"]["status"] == "failed"


def test_explain_work_item_failed_cites_review():
    from gateway.why_not import explain_work_item

    item = _work_item(
        "failed-review",
        state="failed",
        packet_id="pkt-review",
        failure_kind="review",
    )
    item["evidence"]["review"] = {
        "verdict": "reject",
        "summary": "Code quality insufficient.",
        "findings": [],
    }

    explanation = explain_work_item(_work_snapshot_for([item]), "failed-review")

    assert explanation.status == "failed"
    assert "review rejected" in explanation.reason


def test_explain_work_item_failed_insufficient_evidence():
    from gateway.why_not import explain_work_item

    item = _work_item(
        "failed-unknown",
        state="failed",
        packet_id="pkt-unknown",
    )

    explanation = explain_work_item(_work_snapshot_for([item]), "failed-unknown")

    assert explanation.status == "failed"
    assert "not recorded enough evidence" in explanation.reason


def test_explain_work_item_active_with_run():
    from gateway.why_not import explain_work_item

    run = {"id": 42, "state": "running", "started_at": "2026-08-13T11:58:00Z"}
    item = _work_item(
        "active-1",
        state="active",
        current_run=run,
        packet_id="pkt-active",
    )

    explanation = explain_work_item(_work_snapshot_for([item]), "active-1")

    assert explanation.status == "active"
    assert "run 42" in explanation.reason
    assert explanation.automation == "pkt-active"


def test_explain_work_item_ready():
    from gateway.why_not import explain_work_item

    item = _work_item(
        "ready-1",
        state="ready",
        next_action="claim",
        packet_id="pkt-ready",
    )

    explanation = explain_work_item(_work_snapshot_for([item]), "ready-1")

    assert explanation.status == "ready"
    assert "eligible" in explanation.reason
    assert "claim" in explanation.next_step


def test_explain_work_item_paused():
    from gateway.why_not import explain_work_item

    item = _work_item(
        "paused-1",
        state="paused",
        blocker={"state": "blocked", "reason": "operator paused the initiative"},
        next_action="resume the initiative",
        packet_id="pkt-paused",
    )

    explanation = explain_work_item(_work_snapshot_for([item]), "paused-1")

    assert explanation.status == "paused"
    assert "operator paused" in explanation.reason
    assert explanation.next_step == "resume the initiative"


def test_explain_work_item_waiting():
    from gateway.why_not import explain_work_item

    item = _work_item("waiting-1", state="waiting", packet_id="pkt-waiting")

    explanation = explain_work_item(_work_snapshot_for([item]), "waiting-1")

    assert explanation.status == "waiting"
    assert "waiting" in explanation.reason.lower()


def test_explain_work_item_completed():
    from gateway.why_not import explain_work_item

    item = _work_item("completed-1", state="completed", packet_id="pkt-done")

    explanation = explain_work_item(_work_snapshot_for([item]), "completed-1")

    assert explanation.status == "completed"
    assert "complete" in explanation.reason.lower()
    assert explanation.automation == "pkt-done"


def test_explain_work_item_unknown_initiative_raises_work_not_found():
    from gateway.why_not import WorkNotFound, explain_work_item

    with pytest.raises(WorkNotFound, match="not found"):
        explain_work_item(_work_snapshot_for([]), "does-not-exist")


def test_explain_work_item_unknown_state_returns_insufficient_evidence():
    from gateway.why_not import explain_work_item

    item = _work_item("mystery-1", state="bogus", packet_id="pkt-mystery")

    explanation = explain_work_item(_work_snapshot_for([item]), "mystery-1")

    assert explanation.status == "insufficient_evidence"
    assert "not recorded enough evidence" in explanation.reason


@pytest.mark.asyncio
async def test_work_why_route_returns_explanation(monkeypatch):
    from gateway.routes import work as work_route

    item = _work_item(
        "route-test",
        state="blocked",
        blocker={"state": "blocked", "reason": "blocked by dep-2"},
        packet_id="pkt-route",
    )
    monkeypatch.setattr(
        work_route,
        "build_status_snapshot",
        lambda: {
            "schema_version": 2,
            "integrity": {"state": "complete", "partial_packets": 0, "total_packets": 0},
            "queue": {},
            "initiatives": [],
        },
    )
    monkeypatch.setattr(
        work_route,
        "project_work_snapshot",
        lambda _snap: _work_snapshot_for([item]),
    )

    payload = await work_route.work_why("route-test")

    explanation = payload["explanation"]
    assert explanation["status"] == "blocked"
    assert "blocked by dep-2" in explanation["reason"]
    assert explanation["automation"] == "pkt-route"
    assert set(
        ("status", "reason", "relevant_at", "automation", "evidence", "next_step")
    ) <= set(explanation)


@pytest.mark.asyncio
async def test_work_why_route_404s_for_unknown_initiative(monkeypatch):
    from fastapi import HTTPException

    from gateway.routes import work as work_route

    monkeypatch.setattr(
        work_route,
        "build_status_snapshot",
        lambda: {
            "schema_version": 2,
            "integrity": {"state": "complete", "partial_packets": 0, "total_packets": 0},
            "queue": {},
            "initiatives": [],
        },
    )
    monkeypatch.setattr(
        work_route,
        "project_work_snapshot",
        lambda _snap: _work_snapshot_for([]),
    )

    with pytest.raises(HTTPException) as exc:
        await work_route.work_why("does-not-exist")
    assert exc.value.status_code == 404
