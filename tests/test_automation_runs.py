"""Automation run evidence and cron execution semantics for issue #550."""

from __future__ import annotations

import asyncio
import sqlite3

import pytest


@pytest.fixture
def automation_db(tmp_path, monkeypatch):
    from gateway import action_grants, automation_actions, automation_runs, cron
    from gateway import db as kitty_db

    db_file = tmp_path / "kitty.db"
    kitty_db.migrate(db_file=db_file)
    monkeypatch.setattr(automation_runs, "DB_FILE", db_file)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_file)
    monkeypatch.setattr(cron, "KITTY_DB_FILE", db_file)
    automation_actions.clear_registry()
    cron._runner_task = None
    yield db_file
    automation_actions.clear_registry()
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


def test_reconcile_interrupted_retry_releases_parent_claim(automation_db, monkeypatch):
    from gateway import automation_runs

    original = automation_runs.begin_run(
        automation_id="auto-reconcile", action="test.action", trigger_kind="manual", started_at=1.0
    )
    automation_runs.finish_run(original["id"], status="failed", completed_at=2.0)
    child = automation_runs.retry_run(original["id"], started_at=3.0)

    monkeypatch.setattr(automation_runs, "PROCESS_STARTED_AT", 10.0)
    assert automation_runs.reconcile_interrupted_runs(now=20.0) == 1
    assert automation_runs.get_run(child["id"])["status"] == "interrupted"

    again = automation_runs.retry_run(original["id"], started_at=21.0)
    assert again["id"] != child["id"]
    automation_runs.finish_run(again["id"], status="interrupted", completed_at=22.0)


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

def test_claim_running_run_is_exact_and_single_flight(automation_db):
    from concurrent.futures import ThreadPoolExecutor

    from gateway import automation_runs

    kwargs = {
        "automation_id": "mission-plan-review:mission-1",
        "action": "mission.review_pending",
        "trigger_kind": "signal",
        "trigger_ref": "digest-current",
    }

    def claim():
        return automation_runs.claim_running_run(**kwargs)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(claim)
        second_future = pool.submit(claim)
        first = first_future.result(timeout=5)
        second = second_future.result(timeout=5)

    rows = automation_runs.list_runs(
        automation_id=kwargs["automation_id"], statuses=frozenset({"running"})
    )
    assert len(rows) == 1
    assert {first[1], second[1]} == {True, False}
    assert first[0]["id"] == second[0]["id"] == rows[0]["id"]

    different, created = automation_runs.claim_running_run(
        **{**kwargs, "trigger_ref": "digest-new"}
    )
    assert created is True
    assert different["id"] != rows[0]["id"]


def test_concurrent_retry_of_the_same_completed_run_has_exactly_one_winner(automation_db):
    # Reproduces: retry_run() re-checked status='running' on the original run
    # but never mutated it, so two concurrent retries of the same completed
    # run both read 'completed' and both minted a new run -- dispatching the
    # underlying action twice.
    from concurrent.futures import ThreadPoolExecutor

    from gateway import automation_runs

    original = automation_runs.begin_run(
        automation_id="auto-retry", action="test.action", trigger_kind="manual", started_at=1.0
    )
    automation_runs.finish_run(original["id"], status="completed", completed_at=2.0)

    def retry():
        return automation_runs.retry_run(original["id"], started_at=3.0)

    results = []
    errors = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(retry) for _ in range(2)]
        for future in futures:
            try:
                results.append(future.result(timeout=5))
            except automation_runs.AutomationRunStateError as exc:
                errors.append(exc)

    assert len(results) == 1, "expected exactly one winning retry"
    assert len(errors) == 1

    automation_runs.finish_run(results[0]["id"], status="interrupted", completed_at=3.5)
    again = automation_runs.retry_run(original["id"], started_at=4.0)
    assert again["id"] != results[0]["id"]
    automation_runs.finish_run(again["id"], status="interrupted", completed_at=4.5)


def test_stale_retry_claim_is_recoverable(automation_db):
    from gateway import automation_runs

    original = automation_runs.begin_run(
        automation_id="auto-stale", action="test.action", trigger_kind="manual", started_at=1.0
    )
    automation_runs.finish_run(original["id"], status="failed", completed_at=2.0)
    stale = 10.0
    with sqlite3.connect(automation_db) as conn:
        conn.execute(
            "UPDATE automation_runs SET retry_claimed_at = ? WHERE id = ?",
            (stale, original["id"]),
        )
        conn.commit()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(automation_runs.time, "time", lambda: stale + automation_runs.RETRY_CLAIM_STALE_S + 1)
        retried = automation_runs.retry_run(original["id"], started_at=3.0)

    assert retried["id"] != original["id"]
    automation_runs.finish_run(retried["id"], status="interrupted", completed_at=4.0)


def test_stale_retry_claim_does_not_override_a_running_child(automation_db):
    from gateway import automation_runs

    original = automation_runs.begin_run(
        automation_id="auto-long",
        action="test.action",
        trigger_kind="manual",
        trigger_ref="trigger-1",
        started_at=1.0,
    )
    automation_runs.finish_run(original["id"], status="failed", completed_at=2.0)
    stale = 10.0
    with sqlite3.connect(automation_db) as conn:
        conn.execute(
            "UPDATE automation_runs SET retry_claimed_at = ? WHERE id = ?",
            (stale, original["id"]),
        )
        conn.commit()
    child = automation_runs.begin_run(
        automation_id="auto-long",
        action="test.action",
        trigger_kind="manual",
        trigger_ref="trigger-1",
        started_at=11.0,
        retry_of_run_id=original["id"],
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(automation_runs.time, "time", lambda: stale + automation_runs.RETRY_CLAIM_STALE_S + 1)
        with pytest.raises(automation_runs.AutomationRunStateError, match="already being retried"):
            automation_runs.retry_run(original["id"], started_at=12.0)

    automation_runs.finish_run(child["id"], status="interrupted", completed_at=13.0)


def test_cleared_marker_cannot_dispatch_a_second_child(automation_db):
    # Reproduces: the parent's retry marker was cleared by id alone, so a
    # delayed contender could free a replacement claim that a newer retry was
    # already running under. The running-child check only ran when a marker was
    # present, so the freed parent minted and dispatched a second retry child
    # while the first one was still running.
    from gateway import automation_runs

    original = automation_runs.begin_run(
        automation_id="auto-release", action="test.action", trigger_kind="manual", started_at=1.0
    )
    automation_runs.finish_run(original["id"], status="failed", completed_at=2.0)
    first = automation_runs.retry_run(original["id"], started_at=3.0)

    # Exactly the state a non-owner release left behind: marker gone, child live.
    with sqlite3.connect(automation_db) as conn:
        conn.execute(
            "UPDATE automation_runs SET retry_claimed_at = NULL WHERE id = ?",
            (original["id"],),
        )
        conn.commit()

    with pytest.raises(automation_runs.AutomationRunStateError, match="already being retried"):
        automation_runs.retry_run(original["id"], started_at=4.0)

    running = automation_runs.list_runs(
        automation_id="auto-release", statuses=frozenset({"running"})
    )
    assert [run["id"] for run in running] == [first["id"]]
    automation_runs.finish_run(first["id"], status="interrupted", completed_at=5.0)


def test_stalled_claimant_cannot_dispatch_a_second_child(automation_db, monkeypatch):
    # Reproduces: retry_run committed the parent's claim and only then inserted
    # the linked child, so a claimant delayed past RETRY_CLAIM_STALE_S could lose
    # the parent to a second contender and still mint its own running child.
    # Claim and child are written in one transaction now, so that pause cannot
    # exist; the single-child invariant is asserted either way.
    from gateway import automation_runs

    original = automation_runs.begin_run(
        automation_id="auto-stall", action="test.action", trigger_kind="manual", started_at=1.0
    )
    automation_runs.finish_run(original["id"], status="failed", completed_at=2.0)

    real_begin_run = automation_runs.begin_run

    def stalled_begin_run(**kwargs):
        # Whatever pauses here has already committed the parent claim. A second
        # contender takes the parent and inserts its child before this caller
        # resumes to insert one of its own.
        second = real_begin_run(
            automation_id="auto-stall",
            action="test.action",
            trigger_kind="manual",
            started_at=3.5,
            retry_of_run_id=original["id"],
        )
        assert second["id"] != original["id"]
        return real_begin_run(**kwargs)

    monkeypatch.setattr(automation_runs, "begin_run", stalled_begin_run)
    automation_runs.retry_run(original["id"], started_at=3.0)

    running = automation_runs.list_runs(automation_id="auto-stall", statuses=frozenset({"running"}))
    assert len(running) == 1, "a stalled claimant dispatched a second retry child"
    automation_runs.finish_run(running[0]["id"], status="interrupted", completed_at=4.0)


def test_parent_allows_only_one_running_retry_child(automation_db):
    # The single-flight invariant lives in the ledger, not only in retry_run: a
    # second running child for the same parent cannot be written at all.
    from gateway import automation_runs

    original = automation_runs.begin_run(
        automation_id="auto-index", action="test.action", trigger_kind="manual", started_at=1.0
    )
    automation_runs.finish_run(original["id"], status="failed", completed_at=2.0)
    child = automation_runs.retry_run(original["id"], started_at=3.0)

    with pytest.raises(sqlite3.IntegrityError):
        with sqlite3.connect(automation_db) as conn:
            conn.execute(
                "INSERT INTO automation_runs "
                "(id, automation_id, action, trigger_kind, started_at, status, "
                "retry_of_run_id, created_at) "
                "VALUES ('arun_overlap', 'auto-index', 'test.action', 'manual', 3.5, "
                "'running', ?, 3.5)",
                (original["id"],),
            )

    automation_runs.finish_run(child["id"], status="interrupted", completed_at=4.0)


@pytest.mark.asyncio
async def test_retry_route_does_not_dispatch_twice_while_first_retry_is_running(automation_db, monkeypatch):
    from gateway import automation_runs
    from gateway.routes import automations as automations_routes

    original = automation_runs.begin_run(
        automation_id="auto-route-race",
        action="retry.route-race",
        trigger_kind="manual",
        started_at=1.0,
    )
    automation_runs.finish_run(original["id"], status="failed", completed_at=2.0)

    entered = asyncio.Event()
    release = asyncio.Event()
    calls: list[str] = []

    async def slow_run_action(name: str, **kwargs):
        calls.append(kwargs["run_id"])
        entered.set()
        await release.wait()
        automation_runs.finish_run(kwargs["run_id"], status="completed", completed_at=4.0)
        return automation_runs.get_run(kwargs["run_id"])

    monkeypatch.setattr(automations_routes.automation_actions, "run_action", slow_run_action)

    first = asyncio.create_task(automations_routes.retry_automation_run(original["id"]))
    await asyncio.wait_for(entered.wait(), timeout=2)
    try:
        with pytest.raises(automation_runs.AutomationRunStateError, match="already being retried"):
            await automations_routes.retry_automation_run(original["id"])
        assert len(calls) == 1
    finally:
        release.set()
        await first

    # Terminal child completion released the parent claim.
    later = automation_runs.retry_run(original["id"], started_at=5.0)
    automation_runs.finish_run(later["id"], status="interrupted", completed_at=6.0)
