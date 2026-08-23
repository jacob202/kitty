"""Automation run evidence and cron execution semantics for issue #550."""

from __future__ import annotations

import sqlite3

import pytest


@pytest.fixture
def automation_db(tmp_path, monkeypatch):
    from gateway import automation_runs, cron
    from gateway import db as kitty_db

    db_file = tmp_path / "kitty.db"
    kitty_db.migrate(db_file=db_file)
    monkeypatch.setattr(automation_runs, "DB_FILE", db_file)
    monkeypatch.setattr(cron, "KITTY_DB_FILE", db_file)
    cron._actions.clear()
    cron._runner_task = None
    yield db_file
    cron._actions.clear()
    cron._runner_task = None


def _set_last_run(db_file, sid: str, value: float) -> None:
    with sqlite3.connect(db_file) as conn:
        conn.execute("UPDATE cron_schedules SET last_run = ? WHERE id = ?", (value, sid))
        conn.commit()


@pytest.mark.asyncio
async def test_due_cron_action_records_completed_run_before_advancing(automation_db):
    from gateway import automation_runs, cron

    fired: list[str] = []

    async def action() -> None:
        fired.append("yes")

    cron.register_action("test.complete", action)
    sid = cron.schedule("complete", "test.complete", "interval", "1")
    now = 10_000.0
    _set_last_run(automation_db, sid, now - 61)

    await cron._run_due_once(now=now)

    assert fired == ["yes"]
    runs = automation_runs.list_runs(automation_id=sid)
    assert len(runs) == 1
    assert runs[0]["action"] == "test.complete"
    assert runs[0]["trigger_kind"] == "time"
    assert runs[0]["schedule_id"] == sid
    assert runs[0]["status"] == "completed"
    assert runs[0]["started_at"] == now
    assert runs[0]["completed_at"] is not None
    with sqlite3.connect(automation_db) as conn:
        last_run = conn.execute(
            "SELECT last_run FROM cron_schedules WHERE id = ?", (sid,)
        ).fetchone()[0]
    assert last_run == now


@pytest.mark.asyncio
async def test_failed_cron_action_has_evidence_and_is_not_immediately_retried(automation_db):
    from gateway import automation_runs, cron

    attempts: list[str] = []

    async def action() -> None:
        attempts.append("attempt")
        raise RuntimeError("boom")

    cron.register_action("test.fail", action)
    sid = cron.schedule("failure", "test.fail", "interval", "1")
    now = 20_000.0
    _set_last_run(automation_db, sid, now - 61)

    await cron._run_due_once(now=now)
    await cron._run_due_once(now=now + 1)

    assert attempts == ["attempt"]
    runs = automation_runs.list_runs(automation_id=sid)
    assert len(runs) == 1
    assert runs[0]["status"] == "failed"
    assert "RuntimeError: boom" in (runs[0]["error"] or "")


def test_due_occurrence_can_only_be_claimed_once(automation_db):
    from gateway import automation_runs, cron

    sid = cron.schedule("claim-once", "test.claim", "interval", "1")
    now = 15_000.0
    _set_last_run(automation_db, sid, now - 61)
    snapshot = next(row for row in cron.list_schedules() if row["id"] == sid)

    first = automation_runs.claim_scheduled_run(snapshot, due_at=now, claim_at=now, cursor_at=now)
    second = automation_runs.claim_scheduled_run(snapshot, due_at=now, claim_at=now, cursor_at=now)

    assert first is not None
    assert second is None
    assert len(automation_runs.list_runs(automation_id=sid)) == 1


@pytest.mark.asyncio
async def test_missing_registered_action_is_durable_not_silent(automation_db):
    from gateway import automation_runs, cron

    sid = cron.schedule("missing", "test.missing", "interval", "1")
    now = 30_000.0
    _set_last_run(automation_db, sid, now - 61)

    await cron._run_due_once(now=now)

    run = automation_runs.list_runs(automation_id=sid)[0]
    assert run["status"] == "action_unavailable"
    assert "not registered" in (run["error"] or "")


def test_reconcile_marks_orphaned_running_run_interrupted(automation_db):
    from gateway import automation_runs

    run = automation_runs.begin_run(
        automation_id="sched-1",
        action="test.action",
        trigger_kind="time",
        due_at=90.0,
        started_at=100.0,
    )

    assert automation_runs.reconcile_interrupted_runs(now=125.0) == 1
    current = automation_runs.get_run(run["id"])
    assert current is not None
    assert current["status"] == "interrupted"
    assert current["completed_at"] == 125.0
    assert current["duration_ms"] == 25_000


def test_reconcile_does_not_interrupt_a_current_process_run(automation_db, monkeypatch):
    from gateway import automation_runs

    monkeypatch.setattr(automation_runs, "PROCESS_STARTED_AT", 50.0)
    run = automation_runs.begin_run(
        automation_id="manual-1", action="test.action", trigger_kind="manual", started_at=100.0
    )

    assert automation_runs.reconcile_interrupted_runs(now=125.0) == 0
    current = automation_runs.get_run(run["id"])
    assert current is not None
    assert current["status"] == "running"


@pytest.mark.parametrize("status", ["source_unavailable", "condition_false", "policy_refused"])
def test_run_ledger_preserves_non_execution_outcomes(automation_db, status):
    from gateway import automation_runs

    run = automation_runs.begin_run(
        automation_id="auto-1", action="test.action", trigger_kind="manual", started_at=1.0
    )
    automation_runs.finish_run(
        run["id"],
        status=status,
        completed_at=2.0,
        error="x" * 5000,
        policy={"outcome": "deny", "basis": "standing_grant"},
        result_pointer="signal:123",
    )

    current = automation_runs.get_run(run["id"])
    assert current is not None
    assert current["status"] == status
    assert current["result_pointer"] == "signal:123"
    assert len(current["error"] or "") <= automation_runs.MAX_ERROR_CHARS
    assert current["policy"] == {"outcome": "deny", "basis": "standing_grant"}


def test_disabled_and_not_due_are_explainable_without_fake_run_rows(automation_db):
    from gateway import automation_runs, cron

    disabled = cron.schedule("disabled", "test.none", "interval", "60")
    cron.toggle(disabled)
    disabled_row = next(row for row in cron.list_schedules() if row["id"] == disabled)
    assert cron.explain_schedule(disabled_row, now=100.0)["state"] == "disabled"
    assert automation_runs.list_runs(automation_id=disabled) == []

    waiting = cron.schedule("waiting", "test.waiting", "interval", "60")
    _set_last_run(automation_db, waiting, 99.0)
    waiting_row = next(row for row in cron.list_schedules() if row["id"] == waiting)
    assert cron.explain_schedule(waiting_row, now=100.0)["state"] == "not_due"
    assert automation_runs.list_runs(automation_id=waiting) == []
