"""Builder queue runs \u2014 Phase 1C-alpha run-record lifecycle.

Extracted from :mod:`gateway.builder_queue` as the third cut of audit \u00a72.2
(the DB-layer cut was \u00a72.2 first cut, into :mod:`gateway.builder_queue_db`; the
lease lifecycle cut was \u00a72.2 second cut, into :mod:`gateway.builder_queue_leases`).

Owns the lifecycle of execution attempts against claimed tasks: create run,
heartbeat / progress updates, finalize with fence-aware report attachment,
PID-reuse fencing via ``capture_process_identity`` (ps -o lstart), and the
``recover_interrupted_runs`` operator-side crash-recovery scan. Also owns
the run-state machine constants and lifecycle exception classes.

Public symbols are re-exported from :mod:`gateway.builder_queue` via the
fa\u00e7ade so callers (``gateway.builder_runner``, ``gateway.builder_attempt``,
``gateway.builder_initiative``, CLI, tests) work unchanged.

Active-mission note (:file:`.claude/STATE.md`): the chat-recovery work
``CR-02-thread-goals-ui`` is independent of this module.

Dependency resolution: imports from ``gateway.builder_queue`` are
performed lazily inside functions to break the parent-imports-child /
child-imports-parent cycle at module-import time (the parent loads this
module, and any cross-module call from a run function picks up the
parent's fully-loaded namespace at call time).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from gateway._id_helpers import generate_id_with_base36
from gateway.query_builder import WhereClause, build_where

logger = logging.getLogger("kitty.builder_queue_runs")

# ---------------------------------------------------------------------------
# Run-state machine constants
# ---------------------------------------------------------------------------

RUN_STARTING = "starting"
RUN_RUNNING = "running"
RUN_CANCEL_REQUESTED = "cancel_requested"
RUN_EXITED = "exited"
RUN_FAILED = "failed"
RUN_TIMEOUT = "timeout"
RUN_CANCELLED = "cancelled"
RUN_INTERRUPTED = "interrupted"
RUN_LEASE_LOST = "lease_lost"
RUN_SCOPE_VIOLATION = "scope_violation"

RUN_ACTIVE_STATES = frozenset({RUN_STARTING, RUN_RUNNING, RUN_CANCEL_REQUESTED})
RUN_TERMINAL_STATES = frozenset(
    {
        RUN_EXITED,
        RUN_FAILED,
        RUN_TIMEOUT,
        RUN_CANCELLED,
        RUN_INTERRUPTED,
        RUN_LEASE_LOST,
        RUN_SCOPE_VIOLATION,
    }
)

RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    RUN_STARTING: frozenset(
        {
            RUN_RUNNING,
            RUN_CANCEL_REQUESTED,
            RUN_EXITED,
            RUN_FAILED,
            RUN_CANCELLED,
            RUN_INTERRUPTED,
            RUN_LEASE_LOST,
        }
    ),
    RUN_RUNNING: frozenset(
        {
            RUN_CANCEL_REQUESTED,
            RUN_EXITED,
            RUN_FAILED,
            RUN_TIMEOUT,
            RUN_CANCELLED,
            RUN_INTERRUPTED,
            RUN_LEASE_LOST,
            RUN_SCOPE_VIOLATION,
        }
    ),
    RUN_CANCEL_REQUESTED: frozenset(
        {
            RUN_CANCEL_REQUESTED,
            RUN_CANCELLED,
            RUN_INTERRUPTED,
            RUN_LEASE_LOST,
            RUN_SCOPE_VIOLATION,
        }
    ),
    **{state: frozenset() for state in RUN_TERMINAL_STATES},
}


def generate_run_id() -> str:
    return generate_id_with_base36("run")


def _row_to_run(row: sqlite3.Row) -> dict[str, Any]:
    run = dict(row)
    try:
        run["command"] = json.loads(run.get("command_json") or "null")
    except (json.JSONDecodeError, TypeError):
        run["command"] = None
    try:
        run["final_report"] = json.loads(run.get("final_report_json") or "null")
    except (json.JSONDecodeError, TypeError):
        run["final_report"] = None
    return run


class RunNotFoundError(ValueError):
    """Raised when a run ID does not exist."""


class ActiveRunConflictError(ValueError):
    """Raised when a task already has an active execution attempt."""


class RunStateConflictError(ValueError):
    """Raised when a run lifecycle transition is illegal or stale."""


def _validate_run_transition(current_state: str, new_state: str) -> None:
    if current_state not in RUN_TRANSITIONS:
        raise RunStateConflictError(
            f"run has unknown current state {current_state!r}"
        )
    if new_state not in RUN_TRANSITIONS:
        raise ValueError(
            f"unknown run state: {new_state!r}; valid: {sorted(RUN_TRANSITIONS)}"
        )
    if new_state not in RUN_TRANSITIONS[current_state]:
        raise RunStateConflictError(
            f"illegal run transition: {current_state} -> {new_state}"
        )


def create_run(
    task_id: str,
    command: list[str],
    *,
    lease_token: str,
    claim_version: int,
    worker: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    branch: str | None = None,
    worktree_path: str | None = None,
    start_sha: str | None = None,
    log_path: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    import gateway.builder_queue_db as _db

    if not command:
        raise ValueError("command must be a non-empty list")

    run_id = generate_run_id()
    conn = _db.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        task_row = conn.execute(
            "SELECT id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if task_row is None:
            raise _db.TaskNotFoundError(f"task not found: {task_id}")
        fenced_task = conn.execute(
            """
            SELECT id FROM tasks
            WHERE id = ?
              AND state = ?
              AND lease_token = ?
              AND claim_version = ?
              AND lease_expires_at > strftime('%Y-%m-%d %H:%M:%f', 'now')
            """,
            (task_id, _db.CLAIMED, lease_token, claim_version),
        ).fetchone()
        if fenced_task is None:
            raise _db.LeaseConflictError(
                f"cannot create run for task {task_id}: a current claimed task "
                "with matching lease token and claim version is required"
            )
        active = conn.execute(
            """
            SELECT id FROM runs
            WHERE task_id = ?
              AND state IN ('starting', 'running', 'cancel_requested')
            """,
            (task_id,),
        ).fetchone()
        if active is not None:
            raise ActiveRunConflictError(
                f"task {task_id} already has active run {active['id']}"
            )
        conn.execute(
            """
            INSERT INTO runs
                (id, task_id, command_json, claim_version, worker, model, provider,
                 branch, worktree_path, start_sha, log_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                task_id,
                json.dumps(list(command)),
                claim_version,
                worker,
                model,
                provider,
                branch,
                worktree_path,
                start_sha,
                log_path,
            ),
        )
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _row_to_run(row)


def get_run(run_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    import gateway.builder_queue_db as _db
    conn = _db.connect(db_path)
    try:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _row_to_run(row) if row is not None else None
    finally:
        conn.close()


def list_runs(
    task_id: str | None = None,
    state: str | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    import gateway.builder_queue_db as _db
    clauses: list[WhereClause] = []
    if task_id is not None:
        clauses.append(WhereClause("task_id", "=", task_id))
    if state is not None:
        clauses.append(WhereClause("state", "=", state))
    where_sql, params = build_where(clauses)
    conn = _db.connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT * FROM runs WHERE {where_sql or '1 = 1'} ORDER BY id ASC",
            params if where_sql else (),
        ).fetchall()
        return [_row_to_run(r) for r in rows]
    finally:
        conn.close()


def update_run(
    run_id: str,
    *,
    state: str | None = None,
    pid: int | None = None,
    process_identity: str | None = None,
    exit_code: int | None = None,
    log_path: str | None = None,
    mark_started: bool = False,
    mark_ended: bool = False,
    mark_heartbeat: bool = False,
    expected_states: frozenset[str] | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    import gateway.builder_queue_db as _db
    set_parts = ["updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')"]
    params: list[Any] = []
    if state is not None:
        set_parts.append("state = ?")
        params.append(state)
    if pid is not None:
        set_parts.append("pid = ?")
        params.append(pid)
    if process_identity is not None:
        set_parts.append("process_identity = ?")
        params.append(process_identity)
    if exit_code is not None:
        set_parts.append("exit_code = ?")
        params.append(exit_code)
    if log_path is not None:
        set_parts.append("log_path = ?")
        params.append(log_path)
    if mark_started:
        set_parts.append("started_at = strftime('%Y-%m-%d %H:%M:%f', 'now')")
    if mark_ended:
        set_parts.append("ended_at = strftime('%Y-%m-%d %H:%M:%f', 'now')")
    if mark_heartbeat:
        set_parts.append("last_heartbeat_at = strftime('%Y-%m-%d %H:%M:%f', 'now')")

    # Audit \u00a72.3: typed where-clause helper. Parameter order is deterministic:
    # id-equality first, then `state IN (...)` binds sorted(expected_states).
    clauses = [WhereClause("id", "=", run_id)]
    if expected_states is not None:
        clauses.append(WhereClause("state", "IN", sorted(expected_states)))
    where_sql, where_params = build_where(clauses)

    conn = _db.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute(
            "SELECT state FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        if current is None:
            raise RunNotFoundError(f"run not found: {run_id}")
        current_state = str(current["state"])
        if state is not None:
            _validate_run_transition(current_state, state)
        cursor = conn.execute(
            f"UPDATE runs SET {', '.join(set_parts)} WHERE {where_sql}",
            (*params, *where_params),
        )
        if cursor.rowcount != 1:
            raise RunStateConflictError(
                f"run {run_id} not in expected state for this update"
            )
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _row_to_run(row)


def finalize_run(
    run_id: str,
    outcome: str,
    *,
    exit_code: int | None,
    report: dict[str, Any],
    lease_token: str,
    claim_version: int,
    block_reason: str | None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Atomically finish a run and, while still fenced, block its task.

    Lease-clear sequencing (audit \u00a71.3 reliability): the BLOCKED transition
    needs lease_token + claim_version to STILL be present on the task row
    so the fence clause in `_apply_transition` can verify them. So the
    lease-clear UPDATE happens AFTER the transition in the same
    transaction, not before (a previous attempt that combined the
    final_report + lease-clear into one UPDATE wiped lease_token and tripped
    the fence). The transition's `extra_where` checks the fence.
    """
    import gateway.builder_queue as _bq
    import gateway.builder_queue_db as _db

    if outcome not in RUN_TERMINAL_STATES:
        raise ValueError(f"run outcome must be terminal, got {outcome!r}")
    if not isinstance(report, dict) or not report:
        raise ValueError("run report must be a non-empty object")

    conn = _db.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        run_row = conn.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        if run_row is None:
            raise RunNotFoundError(f"run not found: {run_id}")

        task_id = str(run_row["task_id"])
        task_row = conn.execute(
            """
            SELECT state, blocked_reason, claim_version,
                   CASE
                       WHEN lease_token = ?
                        AND claim_version = ?
                        AND lease_expires_at > strftime('%Y-%m-%d %H:%M:%f', 'now')
                       THEN 1 ELSE 0
                   END AS lease_matches
            FROM tasks
            WHERE id = ?
            """,
            (lease_token, claim_version, task_id),
        ).fetchone()
        if task_row is None:
            raise _db.TaskNotFoundError(
                f"task not found for run {run_id}: {task_id}"
            )

        task_state = str(task_row["state"])
        same_claim = int(task_row["claim_version"]) == claim_version
        lease_matches = bool(task_row["lease_matches"])
        runner_owns_running_task = task_state == _db.RUNNING and lease_matches
        runner_owns_claimed_task = (
            task_state == _db.CLAIMED
            and lease_matches
            and run_row["state"] in {RUN_STARTING, RUN_CANCEL_REQUESTED}
        )
        worker_advanced_task = (
            same_claim
            and task_state
            in {_db.BLOCKED, _db.PR_OPENED, _db.AWAITING_REVIEW, _db.DONE, _db.FAILED, _db.CANCELLED}
            and not (
                task_state == _db.BLOCKED
                and task_row["blocked_reason"] == "stale_heartbeat"
            )
        )

        effective_outcome = outcome
        if (
            not runner_owns_running_task
            and not runner_owns_claimed_task
            and not worker_advanced_task
        ):
            effective_outcome = RUN_LEASE_LOST

        _validate_run_transition(str(run_row["state"]), effective_outcome)
        final_report = dict(report)
        final_report["outcome"] = effective_outcome
        final_report["task_state_at_finalize"] = task_state
        if runner_owns_running_task:
            final_report["task_update"] = "blocked_by_runner"
        elif runner_owns_claimed_task:
            final_report["task_update"] = "released_after_setup_failure"
        elif worker_advanced_task:
            final_report["task_update"] = "preserved_worker_state"
        else:
            final_report["task_update"] = "skipped_lease_lost"

        if runner_owns_running_task:
            # (1) Attach the final report while the lease still fences
            # the row (the path-non-fence path is taken in the OTHER branches).
            conn.execute(
                """
                UPDATE tasks
                SET final_report_json = ?,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = ?
                """,
                (json.dumps(final_report), task_id),
            )
            _bq.append_event(
                task_id,
                "report_attached",
                payload={"report": final_report},
                run_id=run_id,
                conn=conn,
            )
            # (2) BLOCKED transition with the lease-fenced WHERE. MUST come
            # BEFORE the lease-clear so the fence clause can verify
            # lease_token + claim_version on the task row.
            _bq._apply_transition(
                conn,
                task_id,
                _db.RUNNING,
                _db.BLOCKED,
                payload={
                    "reason": block_reason,
                    "run_id": run_id,
                    "exit_code": exit_code,
                },
                extra_where=(
                    "AND lease_token = ? AND claim_version = ? "
                    "AND lease_expires_at > strftime('%Y-%m-%d %H:%M:%f', 'now')"
                ),
                extra_params=(lease_token, claim_version),
            )
            # (3) Lease-clear AFTER the transition so the task stops
            # holding a phantom-but-unrenewed lease (audit \u00a71.3).
            conn.execute(
                """
                UPDATE tasks
                SET lease_owner = NULL,
                    lease_token = NULL,
                    lease_expires_at = NULL,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = ?
                """,
                (task_id,),
            )
            # Audit-trail event so list_events(task_id) shows the lease-clear explicitly.
            _bq.append_event(
                task_id,
                "lease_cleared",
                payload={
                    "run_id": run_id,
                    "phase": "finalize",
                    "via": "explicit_after_BLOCKED_transition",
                },
                run_id=run_id,
                conn=conn,
            )
        elif runner_owns_claimed_task:
            # Attach the final report before the transition.
            conn.execute(
                """
                UPDATE tasks
                SET final_report_json = ?,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = ?
                """,
                (json.dumps(final_report), task_id),
            )
            _bq.append_event(
                task_id,
                "report_attached",
                payload={"report": final_report},
                run_id=run_id,
                conn=conn,
            )
            # CLAIMED → QUEUED via `_apply_transition` already clears the
            # lease via the QUEUED-handling branch of the transition's
            # set_clause (new_state in TERMINAL_STATES or new_state == QUEUED).
            # No explicit lease-clear UPDATE needed.
            _bq._apply_transition(
                conn,
                task_id,
                _db.CLAIMED,
                _db.QUEUED,
                payload={
                    "reason": "run_cancelled_before_start"
                    if effective_outcome == RUN_CANCELLED
                    else "runner_setup_failed",
                    "run_id": run_id,
                },
                event_type="released",
                extra_where=(
                    "AND lease_token = ? AND claim_version = ? "
                    "AND lease_expires_at > strftime('%Y-%m-%d %H:%M:%f', 'now')"
                ),
                extra_params=(lease_token, claim_version),
            )
            _bq.append_event(
                task_id,
                "lease_cleared",
                payload={
                    "run_id": run_id,
                    "phase": "finalize",
                    "via": "_apply_transition QUEUED branch",
                },
                run_id=run_id,
                conn=conn,
            )
        elif worker_advanced_task:
            conn.execute(
                """
                UPDATE tasks
                SET final_report_json = ?,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = ?
                """,
                (json.dumps(final_report), task_id),
            )
            _bq.append_event(
                task_id,
                "report_attached",
                payload={"report": final_report},
                run_id=run_id,
                conn=conn,
            )
            _bq.append_event(
                task_id,
                "runner_note",
                payload={
                    "run_id": run_id,
                    "note": "task state already advanced; runner preserved it",
                    "task_state": task_state,
                },
                run_id=run_id,
                conn=conn,
            )
        else:
            conn.execute(
                """
                UPDATE tasks
                SET final_report_json = ?,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = ?
                """,
                (json.dumps(final_report), task_id),
            )
            _bq.append_event(
                task_id,
                "report_attached",
                payload={"report": final_report},
                run_id=run_id,
                conn=conn,
            )

        _bq.append_event(
            task_id,
            f"run_{effective_outcome}",
            payload={"run_id": run_id, "exit_code": exit_code},
            run_id=run_id,
            conn=conn,
        )

        conn.execute(
            """
            UPDATE runs
            SET state = ?, exit_code = ?, final_report_json = ?,
                ended_at = strftime('%Y-%m-%d %H:%M:%f', 'now'),
                updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
            WHERE id = ?
            """,
            (effective_outcome, exit_code, json.dumps(final_report), run_id),
        )

        final_row = conn.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _row_to_run(final_row)


def capture_process_identity(pid: int) -> str | None:
    result = subprocess.run(
        ["ps", "-o", "lstart=", "-p", str(pid)],
        capture_output=True,
        text=True,
    )
    identity = " ".join(result.stdout.split())
    if result.returncode != 0 or not identity:
        return None
    return identity


def recover_interrupted_runs(
    db_path: Path | None = None,
    *,
    starting_grace_seconds: int = 30,
) -> dict[str, Any]:
    import gateway.builder_queue as _bq
    import gateway.builder_queue_db as _db

    if starting_grace_seconds < 0:
        raise ValueError("starting_grace_seconds must be non-negative")

    interrupted: list[str] = []
    deferred: list[str] = []
    unverified: list[dict[str, str]] = []
    running_tasks_blocked = 0
    claimed_tasks_requeued = 0
    conflicts = 0
    conn = _db.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        active_clauses = [WhereClause("state", "IN", sorted(RUN_ACTIVE_STATES))]
        active_where, active_params = build_where(active_clauses)
        rows = conn.execute(
            f"SELECT * FROM runs WHERE {active_where} ORDER BY id ASC",
            tuple(active_params),
        ).fetchall()

        for row in rows:
            run = _row_to_run(row)
            run_id = str(run["id"])
            pid = run.get("pid")
            reason: str | None = None

            if run["state"] == RUN_STARTING and pid is None:
                age_row = conn.execute(
                    """
                    SELECT (julianday('now') - julianday(created_at)) * 86400.0
                    AS age_seconds
                    FROM runs WHERE id = ?
                    """,
                    (run_id,),
                ).fetchone()
                if age_row is None or age_row["age_seconds"] is None:
                    unverified.append(
                        {"run_id": run_id, "reason": "invalid_created_at"}
                    )
                    continue
                age_seconds = float(age_row["age_seconds"])
                if age_seconds < starting_grace_seconds:
                    deferred.append(run_id)
                    continue
                reason = "starting_without_pid"
            elif pid is None:
                reason = "active_run_missing_pid"
            else:
                try:
                    numeric_pid = int(pid)
                except (TypeError, ValueError):
                    unverified.append(
                        {"run_id": run_id, "reason": "invalid_pid"}
                    )
                    continue

                try:
                    os.kill(numeric_pid, 0)
                except ProcessLookupError:
                    reason = "pid_not_running"
                except PermissionError:
                    unverified.append(
                        {"run_id": run_id, "reason": "pid_permission_denied"}
                    )
                    continue
                else:
                    expected_identity = run.get("process_identity")
                    if not expected_identity:
                        unverified.append(
                            {"run_id": run_id, "reason": "process_identity_missing"}
                        )
                        continue
                    current_identity = capture_process_identity(numeric_pid)
                    if current_identity is None:
                        try:
                            os.kill(numeric_pid, 0)
                        except ProcessLookupError:
                            reason = "pid_not_running"
                        else:
                            unverified.append(
                                {"run_id": run_id, "reason": "process_identity_unavailable"}
                            )
                            continue
                    elif current_identity == expected_identity:
                        continue
                    else:
                        reason = "process_identity_mismatch"

            cursor = conn.execute(
                """
                UPDATE runs
                SET state = ?,
                    ended_at = strftime('%Y-%m-%d %H:%M:%f', 'now'),
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = ? AND state = ?
                """,
                (RUN_INTERRUPTED, run_id, run["state"]),
            )
            if cursor.rowcount != 1:
                conflicts += 1
                continue
            _bq.append_event(
                str(run["task_id"]),
                "run_interrupted",
                payload={"run_id": run_id, "pid": pid, "reason": reason},
                run_id=run_id,
                conn=conn,
            )

            run_claim_version = run.get("claim_version")
            if run_claim_version is not None:
                task_id = str(run["task_id"])
                task_row = conn.execute(
                    "SELECT state, claim_version FROM tasks WHERE id = ?",
                    (task_id,),
                ).fetchone()
                if (
                    task_row is not None
                    and int(task_row["claim_version"]) == int(run_claim_version)
                ):
                    if task_row["state"] == _db.RUNNING:
                        task_cursor = conn.execute(
                            """
                            UPDATE tasks
                            SET state = ?, blocked_reason = ?,
                                lease_owner = NULL, lease_token = NULL,
                                lease_expires_at = NULL,
                                updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                            WHERE id = ? AND state = ? AND claim_version = ?
                            """,
                            (
                                _db.BLOCKED,
                                "run_interrupted",
                                task_id,
                                _db.RUNNING,
                                run_claim_version,
                            ),
                        )
                        if task_cursor.rowcount != 1:
                            conflicts += 1
                            continue
                        _bq.append_event(
                            task_id,
                            _db.BLOCKED,
                            payload={"reason": "run_interrupted", "run_id": run_id},
                            run_id=run_id,
                            conn=conn,
                        )
                        running_tasks_blocked += 1
                    elif (
                        task_row["state"] == _db.CLAIMED
                        and run["state"] in {RUN_STARTING, RUN_CANCEL_REQUESTED}
                    ):
                        task_cursor = conn.execute(
                            """
                            UPDATE tasks
                            SET state = ?, blocked_reason = NULL,
                                lease_owner = NULL, lease_token = NULL,
                                lease_expires_at = NULL,
                                updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                            WHERE id = ? AND state = ? AND claim_version = ?
                            """,
                            (_db.QUEUED, task_id, _db.CLAIMED, run_claim_version),
                        )
                        if task_cursor.rowcount != 1:
                            conflicts += 1
                            continue
                        _bq.append_event(
                            task_id,
                            "released",
                            payload={"reason": "run_interrupted_before_start", "run_id": run_id},
                            run_id=run_id,
                            conn=conn,
                        )
                        claimed_tasks_requeued += 1
            interrupted.append(run_id)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "runs_interrupted": len(interrupted),
        "run_ids": interrupted,
        "starting_runs_deferred": len(deferred),
        "starting_run_ids": deferred,
        "runs_unverified": len(unverified),
        "unverified_runs": unverified,
        "running_tasks_blocked": running_tasks_blocked,
        "claimed_tasks_requeued": claimed_tasks_requeued,
        "conflicts": conflicts,
    }


__all__ = [
    "RUN_ACTIVE_STATES",
    "RUN_CANCEL_REQUESTED",
    "RUN_CANCELLED",
    "RUN_EXITED",
    "RUN_FAILED",
    "RUN_INTERRUPTED",
    "RUN_LEASE_LOST",
    "RUN_RUNNING",
    "RUN_SCOPE_VIOLATION",
    "RUN_STARTING",
    "RUN_TERMINAL_STATES",
    "RUN_TIMEOUT",
    "RUN_TRANSITIONS",
    "ActiveRunConflictError",
    "RunNotFoundError",
    "RunStateConflictError",
    "capture_process_identity",
    "create_run",
    "finalize_run",
    "generate_run_id",
    "get_run",
    "list_runs",
    "recover_interrupted_runs",
    "update_run",
]
