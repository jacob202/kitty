"""Durable Automation Run evidence for scheduled and event-triggered actions.

The run ledger records execution truth only. Schedule, monitor, signal, and
other domain state remain owned by their existing stores.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

DB_FILE = KITTY_DB_FILE
PROCESS_STARTED_AT = time.time()
MAX_ERROR_CHARS = 1000
MAX_RESULT_POINTER_CHARS = 500

TERMINAL_STATUSES = frozenset(
    {
        "completed",
        "failed",
        "interrupted",
        "action_unavailable",
        "source_unavailable",
        "condition_false",
        "policy_refused",
        "watch_disabled",
    }
)


class AutomationRunError(RuntimeError):
    """Base error for malformed or invalid run transitions."""


class AutomationRunNotFound(AutomationRunError):
    """No durable run exists with the supplied id."""


class AutomationRunStateError(AutomationRunError):
    """The requested run transition is not valid from its current state."""


def init_db() -> None:
    """Apply pending Kitty migrations to the configured database."""
    kitty_db.migrate(db_file=DB_FILE)


def _bounded(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value[:limit]


def _row_to_run(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    raw_policy = result.pop("policy_json", None)
    result["policy"] = json.loads(raw_policy) if raw_policy else None
    raw_payload = result.pop("payload_json", None)
    result["payload"] = json.loads(raw_payload) if raw_payload else None
    return result


def begin_run(
    *,
    automation_id: str,
    action: str,
    trigger_kind: str,
    trigger_ref: str | None = None,
    schedule_id: str | None = None,
    due_at: float | None = None,
    started_at: float | None = None,
    policy: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one durable running record before an action is dispatched."""
    init_db()
    started = time.time() if started_at is None else float(started_at)
    run_id = f"arun_{uuid.uuid4().hex}"
    policy_json = json.dumps(policy, sort_keys=True) if policy is not None else None
    payload_json = json.dumps(payload, sort_keys=True) if payload is not None else None
    with kitty_db.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO automation_runs "
            "(id, automation_id, action, trigger_kind, trigger_ref, schedule_id, due_at, "
            "started_at, status, policy_json, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?)",
            (
                run_id,
                automation_id,
                action,
                trigger_kind,
                trigger_ref,
                schedule_id,
                due_at,
                started,
                policy_json,
                payload_json,
                started,
            ),
        )
        conn.commit()
    current = get_run(run_id)
    if current is None:
        raise AutomationRunError("run insert did not persist")
    return current


def claim_scheduled_run(
    schedule: dict[str, Any],
    *,
    due_at: float,
    claim_at: float,
    cursor_at: float,
) -> dict[str, Any] | None:
    """Atomically claim a due cron occurrence and create its running evidence.

    The schedule snapshot must still match the durable row. If another runner or
    a concurrent edit already changed it, return ``None`` and dispatch nothing.
    """
    init_db()
    run_id = f"arun_{uuid.uuid4().hex}"
    expected_last_run = float(schedule.get("last_run") or 0.0)
    expected_metadata = schedule.get("metadata") or "{}"
    with kitty_db.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE cron_schedules SET last_run = ? "
            "WHERE id = ? AND enabled = 1 AND COALESCE(last_run, 0) = ? "
            "AND action = ? AND schedule_type = ? AND schedule_value = ? AND metadata = ?",
            (
                cursor_at,
                schedule["id"],
                expected_last_run,
                schedule.get("action", ""),
                schedule.get("schedule_type", ""),
                schedule.get("schedule_value", ""),
                expected_metadata,
            ),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return None
        conn.execute(
            "INSERT INTO automation_runs "
            "(id, automation_id, action, trigger_kind, trigger_ref, schedule_id, due_at, "
            "started_at, status, created_at) "
            "VALUES (?, ?, ?, 'time', ?, ?, ?, ?, 'running', ?)",
            (
                run_id,
                schedule["id"],
                schedule.get("action", ""),
                schedule["id"],
                schedule["id"],
                due_at,
                claim_at,
                claim_at,
            ),
        )
        conn.commit()
    return get_run(run_id)


def finish_run(
    run_id: str,
    *,
    status: str,
    completed_at: float | None = None,
    result_pointer: str | None = None,
    error: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Finish a running record with one explicit terminal outcome."""
    if status not in TERMINAL_STATUSES:
        raise AutomationRunStateError(f"invalid terminal automation status {status!r}")
    init_db()
    completed = time.time() if completed_at is None else float(completed_at)
    policy_json = json.dumps(policy, sort_keys=True) if policy is not None else None
    with kitty_db.connect(DB_FILE) as conn:
        row = conn.execute(
            "SELECT started_at FROM automation_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise AutomationRunNotFound(run_id)
        duration_ms = max(0, int(round((completed - float(row[0])) * 1000)))
        cursor = conn.execute(
            "UPDATE automation_runs SET status = ?, completed_at = ?, duration_ms = ?, "
            "result_pointer = ?, error = ?, policy_json = COALESCE(?, policy_json) "
            "WHERE id = ? AND status = 'running'",
            (
                status,
                completed,
                duration_ms,
                _bounded(result_pointer, MAX_RESULT_POINTER_CHARS),
                _bounded(error, MAX_ERROR_CHARS),
                policy_json,
                run_id,
            ),
        )
        conn.commit()
        if cursor.rowcount != 1:
            raise AutomationRunStateError(f"run {run_id} is not running")
    current = get_run(run_id)
    if current is None:
        raise AutomationRunError("finished run disappeared")
    return current


def retry_run(run_id: str, *, started_at: float | None = None) -> dict[str, Any]:
    """Mint a new running record reusing the original execution intent.

    The retried run receives a fresh identity and timestamps but preserves the
    original automation identity, action, trigger context, schedule reference,
    due-at, and parameters. Authorization is intentionally NOT copied; the
    dispatcher must re-evaluate it before re-invoking the action.
    """
    original = get_run(run_id)
    if original is None:
        raise AutomationRunNotFound(run_id)
    if original["status"] == "running":
        raise AutomationRunStateError(f"run {run_id} is still running")
    return begin_run(
        automation_id=original["automation_id"],
        action=original["action"],
        trigger_kind=original["trigger_kind"],
        trigger_ref=original.get("trigger_ref"),
        schedule_id=original.get("schedule_id"),
        due_at=original.get("due_at"),
        started_at=started_at,
        payload=original.get("payload"),
    )


def reconcile_interrupted_runs(*, now: float | None = None) -> int:
    """Mark only runs that predate this Gateway process as interrupted."""
    init_db()
    completed = time.time() if now is None else float(now)
    with kitty_db.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE automation_runs "
            "SET status = 'interrupted', completed_at = ?, "
            "duration_ms = CAST(MAX(0, (? - started_at) * 1000) AS INTEGER), "
            "error = COALESCE(error, 'Gateway restarted before this run completed') "
            "WHERE status = 'running' AND started_at < ?",
            (completed, completed, PROCESS_STARTED_AT),
        )
        conn.commit()
        return cursor.rowcount


def get_run(run_id: str) -> dict[str, Any] | None:
    init_db()
    with kitty_db.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM automation_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    return _row_to_run(row)


def list_runs(
    *,
    automation_id: str | None = None,
    action: str | None = None,
    statuses: set[str] | frozenset[str] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return bounded recent run evidence, newest first."""
    init_db()
    bounded_limit = max(1, min(int(limit), 200))
    clauses: list[str] = []
    params: list[Any] = []
    if automation_id is not None:
        clauses.append("automation_id = ?")
        params.append(automation_id)
    if action is not None:
        clauses.append("action = ?")
        params.append(action)
    if statuses:
        ordered_statuses = sorted(statuses)
        clauses.append("status IN (" + ",".join("?" for _ in ordered_statuses) + ")")
        params.extend(ordered_statuses)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with kitty_db.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM automation_runs{where} ORDER BY started_at DESC, id DESC LIMIT ?",
            (*params, bounded_limit),
        ).fetchall()
    return [run for row in rows if (run := _row_to_run(row)) is not None]
