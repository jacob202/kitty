"""KittyBuilder Phase 1A — durable local Builder queue store & state machine.

Library-mode SQLite storage for the KittyBuilder orchestrator. Scope so far:
schema, connection helpers, task creation/retrieval/listing, append-only event
log, state machine transitions, claims, lease fencing, worker transitions,
releases, and expired lease recovery. This module does not implement CLI
commands, daemon/API, worker execution, worktrees, or PR automation yet.

Important scope notes (see docs/KITTYBUILDER_ORCHESTRATOR_PHASE1A.md):

- This module must not modify gateway/builder.py (autonomous pipeline) or
  gateway/task_runner.py (generic tasks). It is a separate store backed by
  BUILDER_QUEUE_DB, not the legacy TASK_DB.
- GitHub bridge metadata is advisory after Phase 1A. The only bridge field
  that affects idempotency is bridge_external_id; re-adding the same
  (bridge_source, bridge_external_id) must fail. GitHub comments never
  mutate local task state (Section 11.4).
- The events table is append-only. UPDATE and DELETE are blocked by
  triggers; there is intentionally no public update/delete helper here.
- Task IDs follow the no-dependency format from Section 11.1:
  ``kb_<base36_unix_ms>_<hex4>`` — locally unique, roughly time-sortable,
  short enough to appear in future branch names and PR titles.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from gateway.paths import BUILDER_QUEUE_DB

from .query_builder import WhereClause, build_where

logger = logging.getLogger("kitty.builder_queue")

__all__ = [
    # Re-exports from gateway.builder_queue_db (DB layer; audit §2.2 first cut).
    "AWAITING_REVIEW",
    "BLOCKED",
    "BranchLeaseConflictError",
    "CANCELLED",
    "CLAIMED",
    "connect",
    "DataCorruptionError",
    "DONE",
    "FAILED",
    "IllegalTransitionError",
    "init_db",
    "LeaseConflictError",
    "LEGAL_TRANSITIONS",
    "PR_OPENED",
    "QUEUED",
    "RUNNING",
    "TaskNotFoundError",
    "TERMINAL_STATES",
    # Re-exports from gateway.builder_queue_leases (lease lifecycle; audit §2.2 second cut).
    "claim_next",
    "claim_task",
    "operator_release_task",
    "recover_expired_leases",
    "renew_lease",
    "worker_release_task",
    "worker_transition_task",
    # Run-state machine constants and transitions.
    "RUN_ACTIVE_STATES",
    "RUN_CANCELLED",
    "RUN_CANCEL_REQUESTED",
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
    # Library functions (defined in this module; select non-underscore surface).
    "ActiveRunConflictError",
    "append_event",
    "archive_tasks",
    "attach_final_report",
    "attach_pr",
    "capture_process_identity",
    "claim_branch_lease",
    "create_run",
    "create_task",
    "detect_merged_prs",
    "edit_task",
    "finalize_run",
    "generate_run_id",
    "generate_task_id",
    "get_branch_lease",
    "get_pr_links",
    "get_run",
    "get_task",
    "list_events",
    "list_runs",
    "list_tasks",
    "queue_status",
    "recover_interrupted_runs",
    "release_branch_lease",
    "RunNotFoundError",
    "RunStateConflictError",
    "sync_pr_status",
    "transition_task",
    "update_run",
    "verify_branch_lease",
]

# ---------------------------------------------------------------------------
# Re-exports from gateway.builder_queue_db (audit §2.2 first cut).
# Keep ``from gateway.builder_queue import X`` and
# ``import gateway.builder_queue as bq`` working for tests and
# sibling modules (gateway.builder_attempt, gateway.builder_runner,
# gateway.builder_initiative, gateway.builder_cli, tests/...).
from . import builder_queue_db as _queue_db  # noqa: E402 — façade re-exports below logger.
from ._id_helpers import generate_id_with_base36  # noqa: E402
from .builder_queue_branch_leases import (  # noqa: E402,F401
    _claim_branch_lease_on_conn,
    _release_branch_lease_on_conn,
    _validate_branch_lease_fields,
    claim_branch_lease,
    get_branch_lease,
    release_branch_lease,
    verify_branch_lease,
)
from .builder_queue_db import (  # noqa: E402,F401
    _VALID_STATES,
    AWAITING_REVIEW,
    BLOCKED,
    CANCELLED,
    CLAIMED,
    DONE,
    FAILED,
    LEGAL_TRANSITIONS,
    PR_OPENED,
    QUEUED,
    RUNNING,
    TERMINAL_STATES,
    BranchLeaseConflictError,
    DataCorruptionError,
    IllegalTransitionError,
    LeaseConflictError,
    TaskNotFoundError,
)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open the queue DB, preserving the legacy façade path override."""
    return _queue_db.connect(BUILDER_QUEUE_DB if db_path is None else db_path)


def init_db(db_path: Path | None = None) -> None:
    """Initialize the queue DB, preserving the legacy façade path override."""
    _queue_db.init_db(BUILDER_QUEUE_DB if db_path is None else db_path)

# ---------------------------------------------------------------------------
# Re-exports from gateway.builder_queue_leases (audit §2.2 second cut).
# Keep ``from gateway.builder_queue import X`` working for
# ``gateway.builder_runner`` (renew_lease heartbeat), ``builder_attempt``
# (claim / release worker paths), the CLI, and tests.
# ---------------------------------------------------------------------------
from .builder_queue_leases import (  # noqa: E402,F401 — façade re-exports; placed after logger by design.
    claim_next,
    claim_task,
    operator_release_task,
    recover_expired_leases,
    renew_lease,
    worker_release_task,
    worker_transition_task,
)

# ---------------------------------------------------------------------------
# Re-exports from gateway.builder_queue_runs (audit §2.2 third cut).
# Keep ``from gateway.builder_queue import X`` working for
# ``gateway.builder_runner`` (run_worker finalize + heartbeat), the CLI,
# and tests.
# Cycle break: builder_queue_runs.py lazy-imports
# ``gateway.builder_queue`` inside functions that need ``append_event`` or
# ``_apply_transition``; this top-level re-export is safe because
# builder_queue is fully loaded before builder_queue_runs is reached.
# ---------------------------------------------------------------------------
from .builder_queue_runs import (  # noqa: E402,F401 — façade re-exports; placed after logger by design.
    RUN_ACTIVE_STATES,
    RUN_CANCEL_REQUESTED,
    RUN_CANCELLED,
    RUN_EXITED,
    RUN_FAILED,
    RUN_INTERRUPTED,
    RUN_LEASE_LOST,
    RUN_RUNNING,
    RUN_SCOPE_VIOLATION,
    RUN_STARTING,
    RUN_TERMINAL_STATES,
    RUN_TIMEOUT,
    RUN_TRANSITIONS,
    ActiveRunConflictError,
    RunNotFoundError,
    RunStateConflictError,
    capture_process_identity,
    create_run,
    finalize_run,
    generate_run_id,
    get_run,
    list_runs,
    recover_interrupted_runs,
    update_run,
)

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# SQLite schema (Phase 1A — tasks + events; runs/pr_links/artifacts future).
# The DDL has moved to gateway.builder_queue_db._SCHEMA_SQL (audit §2.2).
# This banner stays so the surrounding run-state section remains visually
# grouped with the schema location.
# Run-state machine constants live in :mod:`gateway.builder_queue_runs`
# (audit §2.2 third cut) and are re-exported via the façade so
# ``from gateway.builder_queue import RUN_ACTIVE_STATES`` /
# ``bq.RUN_INTERRUPTED`` continue to work.

# ---------------------------------------------------------------------------
# Task ID helper (no-dependency, roughly time-sortable)
# ---------------------------------------------------------------------------


def generate_task_id() -> str:
    """Return ``kb_<base36_unix_ms>_<hex4>``.

    Delegates to :func:`gateway._id_helpers.generate_id_with_base36` so the
    time-sortable + disambiguation pattern is shared with the runs module.
    """
    return generate_id_with_base36("kb")






# ---------------------------------------------------------------------------
# Row marshalling
# ---------------------------------------------------------------------------


def _row_to_task(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a tasks row to a dict, JSON-decoding the fields that are stored
    as JSON text."""
    task = dict(row)
    ac = task.get("acceptance_criteria_json")
    if ac is not None:
        try:
            task["acceptance_criteria"] = json.loads(ac)
        except (json.JSONDecodeError, TypeError):
            task["acceptance_criteria"] = None
    else:
        task["acceptance_criteria"] = None

    ap = task.get("allowed_paths_json")
    if ap is not None:
        try:
            allowed = json.loads(ap)
        except (json.JSONDecodeError, TypeError) as exc:
            raise DataCorruptionError(
                f"corrupted allowed_paths_json for task {task.get('id', '?')}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        if not isinstance(allowed, list):
            raise DataCorruptionError(
                f"corrupted allowed_paths_json for task {task.get('id', '?')}: "
                f"expected a JSON array, got {type(allowed).__name__}"
            )
        task["allowed_paths"] = allowed
    else:
        task["allowed_paths"] = None

    return task


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    event = dict(row)
    payload = event.get("payload_json")
    if payload is not None:
        try:
            event["payload"] = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            event["payload"] = None
    else:
        event["payload"] = None
    return event


# ---------------------------------------------------------------------------
# Library functions
# ---------------------------------------------------------------------------


def create_task(
    title: str,
    *,
    description: str | None = None,
    acceptance_criteria: list[str] | None = None,
    priority: int = 0,
    bridge_source: str | None = None,
    bridge_issue: str | None = None,
    bridge_external_id: str | None = None,
    bridge_comment_url: str | None = None,
    workflow_ref: str | None = None,
    workflow_sha: str | None = None,
    repo_path: str | None = None,
    allowed_paths: list[str] | None = None,
    db_path: Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Create a task in state ``queued`` and append a ``created`` event.

    Bridge idempotency: the unique index on
    ``(bridge_source, bridge_external_id)`` (where both are non-null) prevents
    duplicate inserts for the same bridge tuple. On a duplicate, IntegrityError
    is raised and NO ``created`` event is appended.

    If ``conn`` is supplied (same pattern as ``append_event``), the insert
    happens on the caller's open transaction without committing — used by
    initiative apply to materialize packet tasks atomically with the
    initiative rows.

    Returns the created task dict (as from ``get_task``).
    """
    if not title or not title.strip():
        raise ValueError("title is required and must be non-empty")

    task_id = generate_task_id()
    acceptance_json = (
        json.dumps(list(acceptance_criteria)) if acceptance_criteria else None
    )
    allowed_paths_json = (
        json.dumps(list(allowed_paths)) if allowed_paths else None
    )

    own_conn = conn is None
    if own_conn:
        conn = connect(db_path)
    assert conn is not None
    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO tasks (
                id, title, description, state, priority,
                acceptance_criteria_json,
                bridge_source, bridge_issue, bridge_external_id,
                bridge_comment_url,
                workflow_ref, workflow_sha, repo_path,
                allowed_paths_json
            ) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                title,
                description,
                priority,
                acceptance_json,
                bridge_source,
                bridge_issue,
                bridge_external_id,
                bridge_comment_url,
                workflow_ref,
                workflow_sha,
                repo_path,
                allowed_paths_json,
            ),
        )
        append_event(
            task_id,
            "created",
            payload={"title": title, "priority": priority},
            db_path=db_path,
            conn=conn,
        )
        if own_conn:
            conn.commit()
        created = _get_task_on_conn(conn, task_id)
    except Exception:
        if own_conn:
            conn.rollback()
        raise
    finally:
        if own_conn:
            conn.close()

    if created is None:
        # Should be impossible given the insert above; fail loud per AGENTS.md.
        raise RuntimeError(
            f"Task {task_id} was committed but is not retrievable"
        )
    return created


def get_task(
    task_id: str, db_path: Path | None = None
) -> dict[str, Any] | None:
    """Return the task dict for ``task_id`` or ``None`` if absent."""
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return _row_to_task(row) if row is not None else None
    finally:
        conn.close()


def _get_task_on_conn(conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
    """Return a task using the caller's open transaction."""
    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    return _row_to_task(row) if row is not None else None


def list_tasks(
    state: str | None = None,
    include_archived: bool = False,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """List tasks, optionally filtered by state, excluding archived by default.

    Archived tasks (``archived_at IS NOT NULL``) are excluded unless
    ``include_archived=True``. Ordering follows the claim index
    (state, priority DESC, id ASC) so consumers see a stable, scan-friendly
    ordering.
    """
    conn = connect(db_path)
    try:
        clauses: list[WhereClause] = []
        if state is not None:
            clauses.append(WhereClause("state", "=", state))
        if not include_archived:
            clauses.append(WhereClause("archived_at", is_null=True))
        where_sql, params = build_where(clauses)
        rows = conn.execute(
            f"""
            SELECT * FROM tasks
            WHERE {where_sql or "1 = 1"}
            ORDER BY state ASC, priority DESC, id ASC
            """,
            params if where_sql else (),
        ).fetchall()
        return [_row_to_task(r) for r in rows]
    finally:
        conn.close()


def append_event(
    task_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    db_path: Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Append a row to the events log.

    If ``conn`` is supplied, the row is inserted on that connection without
    committing — used by ``create_task`` to atomically insert the task and
    its ``created`` event in one transaction. If no ``conn`` is supplied, a
    fresh connection is opened and the insert is committed immediately.

    The events table is append-only: UPDATE/DELETE are blocked by triggers.
    """
    if not event_type or not event_type.strip():
        raise ValueError("event_type is required and must be non-empty")
    payload_json = json.dumps(payload) if payload is not None else None

    own_conn = conn is None
    if own_conn:
        conn = connect(db_path)
    # mypy: conn is non-None here — either supplied by the caller or opened
    # just above. The assert documents the narrowing for both reader and type
    # checker.
    assert conn is not None
    try:
        cursor = conn.execute(
            """
            INSERT INTO events (task_id, run_id, type, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, run_id, event_type, payload_json),
        )
        event_id = cursor.lastrowid
        if own_conn:
            conn.commit()
        row = conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        return _row_to_event(row)
    except Exception:
        if own_conn:
            conn.rollback()
        raise
    finally:
        if own_conn:
            conn.close()


# ---------------------------------------------------------------------------
# State validation
# ---------------------------------------------------------------------------


def _validate_state(state: str) -> None:
    """Raise ``ValueError`` if *state* is not a known machine state."""
    if state not in _VALID_STATES:
        raise ValueError(
            f"unknown state: {state!r}; valid: {sorted(_VALID_STATES)}"
        )


# ---------------------------------------------------------------------------
# Transition engine (internal — caller owns the transaction)
# ---------------------------------------------------------------------------


def _apply_transition(
    conn: sqlite3.Connection,
    task_id: str,
    current_state: str,
    new_state: str,
    *,
    payload: dict[str, Any] | None = None,
    extra_where: str = "",
    extra_params: tuple[Any, ...] = (),
    event_type: str | None = None,
) -> None:
    """Apply a state transition on *conn* (inside an open transaction).

    Validates states, checks legality, updates the row, and appends an
    event. Does **not** commit — the caller owns the transaction.

    Raises:
        IllegalTransitionError — illegal, changed, or archived.
        LeaseConflictError — legal transition rejected by lease fencing.
        ValueError — unknown state.
    """
    _validate_state(current_state)
    _validate_state(new_state)

    if new_state not in LEGAL_TRANSITIONS[current_state]:
        raise IllegalTransitionError(
            f"illegal transition: {current_state} -> {new_state}"
        )

    terminal = new_state in TERMINAL_STATES

    set_clause = "state = ?, updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')"
    set_params: list[Any] = [new_state]
    if new_state == BLOCKED:
        reason = payload.get("reason") if payload is not None else None
        set_clause += ", blocked_reason = ?"
        set_params.append(reason if isinstance(reason, str) and reason else None)
    else:
        set_clause += ", blocked_reason = NULL"
    if terminal or new_state == QUEUED:
        set_clause += (
            ", lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL"
        )

    sql = (
        f"UPDATE tasks SET {set_clause}"
        " WHERE id = ? AND state = ? AND archived_at IS NULL"
        f" {extra_where}"
    )

    cursor = conn.execute(
        sql, (*set_params, task_id, current_state, *extra_params)
    )

    if cursor.rowcount != 1 and extra_where:
        raise LeaseConflictError(
            "lease conflict; task claim is stale, expired, or no longer valid"
        )

    if cursor.rowcount != 1:
        raise IllegalTransitionError(
            "transition failed; task changed, archived, or lease guard failed"
        )

    append_event(task_id, event_type or new_state, payload=payload, conn=conn)


# ---------------------------------------------------------------------------
# Public transition entry point (operator-level)
# ---------------------------------------------------------------------------


def transition_task(
    task_id: str,
    new_state: str,
    *,
    payload: dict[str, Any] | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Atomically transition a task to *new_state*.

    Opens its own connection, validates the task exists and is not archived,
    runs the transition in ``BEGIN IMMEDIATE``, commits, and returns the
    updated task dict.

    Raises:
        TaskNotFoundError — task ID does not exist.
        IllegalTransitionError — transition not legal, task archived, or
            concurrent state change.
        ValueError — unknown *new_state*.
    """
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id, state, archived_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if row is None:
            raise TaskNotFoundError(f"task not found: {task_id}")

        if row["archived_at"] is not None:
            raise IllegalTransitionError(
                f"task {task_id} is archived and cannot be transitioned"
            )

        _apply_transition(
            conn, task_id, row["state"], new_state, payload=payload
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    result = get_task(task_id, db_path=db_path)
    if result is None:
        raise RuntimeError(
            f"Task {task_id} was committed but is not retrievable"
        )
    return result


# Claiming / lease-fencing functions were extracted to :mod:`gateway.builder_queue_leases` (audit §2.2 #2).







# ---------------------------------------------------------------------------
# Edit task (queued-only editable fields)
# ---------------------------------------------------------------------------


def edit_task(
    task_id: str,
    *,
    title: str | None = None,
    description: str | None = None,
    priority: int | None = None,
    acceptance_criteria: list[str] | None = None,
    allowed_paths: list[str] | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Edit a queued task's editable fields.

    Only allowed when state is ``queued``. Editable fields: title, description,
    priority, acceptance_criteria, and allowed_paths. Bridge metadata is
    read-only after creation.

    Returns the updated task dict.

    Raises:
        TaskNotFoundError — task ID does not exist.
        IllegalTransitionError — task is not queued or is archived.
    """
    if title is not None and not title.strip():
        raise ValueError("title must be non-empty if provided")

    conn = connect(db_path)
    result: dict[str, Any] | None = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id, state, archived_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if row is None:
            raise TaskNotFoundError(f"task not found: {task_id}")
        if row["archived_at"] is not None:
            raise IllegalTransitionError(
                f"task {task_id} is archived and cannot be edited"
            )
        if row["state"] != QUEUED:
            raise IllegalTransitionError(
                f"task {task_id} is in state {row['state']!r}; "
                "only queued tasks can be edited"
            )

        set_parts: list[str] = []
        params: list[Any] = []

        if title is not None:
            set_parts.append("title = ?")
            params.append(title)
        if description is not None:
            set_parts.append("description = ?")
            params.append(description)
        if priority is not None:
            set_parts.append("priority = ?")
            params.append(priority)
        if acceptance_criteria is not None:
            set_parts.append("acceptance_criteria_json = ?")
            params.append(json.dumps(list(acceptance_criteria)))
        if allowed_paths is not None:
            set_parts.append("allowed_paths_json = ?")
            params.append(json.dumps(list(allowed_paths)))

        if not set_parts:
            raise ValueError("at least one editable field must be provided")

        set_parts.append("updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')")
        params.append(task_id)

        conn.execute(
            f"UPDATE tasks SET {', '.join(set_parts)} WHERE id = ? AND state = ?",
            (*params, QUEUED),
        )

        result = _get_task_on_conn(conn, task_id)
        if result is None:
            raise RuntimeError(
                f"Task {task_id} was edited but is not retrievable"
            )
        append_event(
            task_id,
            "edited",
            payload={
                k: v
                for k, v in [
                    ("title", title),
                    ("description", description),
                    ("priority", priority),
                    ("acceptance_criteria", acceptance_criteria),
                    ("allowed_paths", allowed_paths),
                ]
                if v is not None
            },
            conn=conn,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return result


# ---------------------------------------------------------------------------
# Event listing
# ---------------------------------------------------------------------------


def list_events(
    task_id: str,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return all events for a task in chronological order.

    Raises:
        TaskNotFoundError — task ID does not exist.
    """
    conn = connect(db_path)
    try:
        task_exists = conn.execute(
            "SELECT 1 FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if task_exists is None:
            raise TaskNotFoundError(f"task not found: {task_id}")

        rows = conn.execute(
            """
            SELECT * FROM events
            WHERE task_id = ?
            ORDER BY id ASC
            """,
            (task_id,),
        ).fetchall()
        return [_row_to_event(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Queue status (counts per state)
# ---------------------------------------------------------------------------


def queue_status(
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return a summary of queue counts per state and total."""
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT state, COUNT(*) as count
            FROM tasks
            WHERE archived_at IS NULL
            GROUP BY state
            ORDER BY state ASC
            """
        ).fetchall()
        per_state: dict[str, int] = {}
        total = 0
        for row in rows:
            per_state[row["state"]] = row["count"]
            total += row["count"]

        return {
            "per_state": per_state,
            "total": total,
            "queued": per_state.get(QUEUED, 0),
            "claimed": per_state.get(CLAIMED, 0),
            "running": per_state.get(RUNNING, 0),
            "blocked": per_state.get(BLOCKED, 0),
            "pr_opened": per_state.get(PR_OPENED, 0),
            "awaiting_review": per_state.get(AWAITING_REVIEW, 0),
            "done": per_state.get(DONE, 0),
            "failed": per_state.get(FAILED, 0),
            "cancelled": per_state.get(CANCELLED, 0),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Soft archive (terminal-state-only, age-filtered)
# ---------------------------------------------------------------------------


def archive_tasks(
    state: str,
    older_than_days: int,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Soft-archive terminal tasks in *state* older than *older_than_days*.

    Sets ``archived_at`` on matching tasks. Does **not** delete rows or
    events. Raises ``ValueError`` if *state* is not a terminal state.

    Returns a dict with ``tasks_archived`` count and ``task_ids`` list.
    """
    _validate_state(state)
    if state not in TERMINAL_STATES:
        raise ValueError(
            f"archive only supports terminal states ({sorted(TERMINAL_STATES)}); "
            f"got {state!r}"
        )
    if older_than_days < 0:
        raise ValueError("older_than_days must be non-negative")

    conn = connect(db_path)
    archived_ids: list[str] = []
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            """
            SELECT id FROM tasks
            WHERE state = ?
              AND archived_at IS NULL
              AND updated_at <= strftime('%Y-%m-%d %H:%M:%f', 'now', ?)
            ORDER BY id ASC
            """,
            (state, f"-{older_than_days} days"),
        ).fetchall()

        for row in rows:
            cursor = conn.execute(
                """
                UPDATE tasks
                SET archived_at = strftime('%Y-%m-%d %H:%M:%f', 'now'),
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = ?
                  AND state = ?
                  AND archived_at IS NULL
                """,
                (row["id"], state),
            )
            if cursor.rowcount == 1:
                archived_ids.append(row["id"])
                append_event(
                    row["id"],
                    "archived",
                    payload={"state": state},
                    conn=conn,
                )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "tasks_archived": len(archived_ids),
        "task_ids": archived_ids,
    }


# ---------------------------------------------------------------------------
# Phase 1B — Final reports
# ---------------------------------------------------------------------------


def attach_final_report(
    task_id: str,
    report: dict[str, Any],
    *,
    lease_token: str | None = None,
    claim_version: int | None = None,
    operator_reason: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Attach a structured final report to a task.

    Two calling modes:

    - **Worker (fenced):** pass ``lease_token`` + ``claim_version``. Rejected
      with ``LeaseConflictError`` if stale — the report of a superseded
      worker must not overwrite the current one.
    - **Operator (unfenced):** pass ``operator_reason`` instead. For
      post-mortems on dead/terminal tasks that no longer hold a lease.

    The report replaces ``final_report_json`` and appends a
    ``report_attached`` event carrying the report so history keeps every
    version even when the column is overwritten.

    Raises:
        TaskNotFoundError, IllegalTransitionError (archived),
        LeaseConflictError (stale fencing), ValueError (bad args).
    """
    if not isinstance(report, dict) or not report:
        raise ValueError("report must be a non-empty JSON object")

    fenced = lease_token is not None or claim_version is not None
    if fenced and (lease_token is None or claim_version is None):
        raise ValueError("fenced mode requires both lease_token and claim_version")
    if not fenced and operator_reason is None:
        raise ValueError(
            "attach_final_report requires either lease_token+claim_version "
            "(worker) or operator_reason (operator)"
        )

    conn = connect(db_path)
    result: dict[str, Any] | None = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id, state, archived_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            raise TaskNotFoundError(f"task not found: {task_id}")
        if row["archived_at"] is not None:
            raise IllegalTransitionError(
                f"task {task_id} is archived and cannot accept a report"
            )

        report_json = json.dumps(report)
        if fenced:
            cursor = conn.execute(
                """
                UPDATE tasks
                SET final_report_json = ?,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = ? AND lease_token = ? AND claim_version = ?
                """,
                (report_json, task_id, lease_token, claim_version),
            )
            if cursor.rowcount != 1:
                raise LeaseConflictError(
                    f"stale lease or claim version for task {task_id}; "
                    "report not attached"
                )
            event_payload: dict[str, Any] = {"report": report}
        else:
            conn.execute(
                """
                UPDATE tasks
                SET final_report_json = ?,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = ?
                """,
                (report_json, task_id),
            )
            event_payload = {
                "report": report,
                "operator": True,
                "reason": operator_reason,
            }

        append_event(task_id, "report_attached", payload=event_payload, conn=conn)
        result = _get_task_on_conn(conn, task_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if result is None:
        raise RuntimeError(f"Task {task_id} report attached but not retrievable")
    return result


# ---------------------------------------------------------------------------
# Phase 1B — PR metadata links (advisory; never mutate task state)
# ---------------------------------------------------------------------------


def attach_pr(
    task_id: str,
    pr_number: int,
    *,
    pr_url: str | None = None,
    head_sha: str | None = None,
    checks_state: str | None = None,
    review_state: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Attach or update PR metadata for a task.

    Upserts one ``pr_links`` row per (task, PR number) and appends a
    ``pr_attached`` (new) or ``pr_updated`` (refresh) event. Advisory only:
    task state is never changed here (Section 11.4) — moving a task to
    ``pr_opened`` remains an explicit fenced transition.

    Only fields passed as non-None are overwritten on refresh.
    """
    if pr_number <= 0:
        raise ValueError("pr_number must be a positive integer")

    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        task_row = conn.execute(
            "SELECT id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if task_row is None:
            raise TaskNotFoundError(f"task not found: {task_id}")

        existing = conn.execute(
            "SELECT id FROM pr_links WHERE task_id = ? AND pr_number = ?",
            (task_id, pr_number),
        ).fetchone()

        if existing is None:
            conn.execute(
                """
                INSERT INTO pr_links
                    (task_id, pr_number, pr_url, head_sha, checks_state, review_state)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, pr_number, pr_url, head_sha, checks_state, review_state),
            )
            event_type = "pr_attached"
        else:
            set_parts = ["updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')"]
            params: list[Any] = []
            for column, value in (
                ("pr_url", pr_url),
                ("head_sha", head_sha),
                ("checks_state", checks_state),
                ("review_state", review_state),
            ):
                if value is not None:
                    set_parts.append(f"{column} = ?")
                    params.append(value)
            params.append(existing["id"])
            conn.execute(
                f"UPDATE pr_links SET {', '.join(set_parts)} WHERE id = ?",
                params,
            )
            event_type = "pr_updated"

        append_event(
            task_id,
            event_type,
            payload={
                k: v
                for k, v in (
                    ("pr_number", pr_number),
                    ("pr_url", pr_url),
                    ("head_sha", head_sha),
                    ("checks_state", checks_state),
                    ("review_state", review_state),
                )
                if v is not None
            },
            conn=conn,
        )

        link_row = conn.execute(
            "SELECT * FROM pr_links WHERE task_id = ? AND pr_number = ?",
            (task_id, pr_number),
        ).fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return dict(link_row)


# ---------------------------------------------------------------------------
# KB-S4 — merge detection + CI/review reconciliation (advisory, operator-gated)
# ---------------------------------------------------------------------------


def _gh_pr_status(pr_number: int) -> dict[str, Any]:
    """Query GitHub for a PR's merge/checks/review state via the ``gh`` CLI.

    Returns ``{"merged", "url", "head_sha", "checks_state", "review_state"}``.
    Raises ``RuntimeError`` if ``gh`` is unavailable or the PR is not found, so
    the caller can decide whether to skip (advisory) or surface the error.
    """
    try:
        env = dict(os.environ)
        env.pop("GITHUB_TOKEN", None)
        env.pop("GH_TOKEN", None)
        proc = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--json",
                # "state" not "merged": gh >= 2.80 dropped the boolean
                # "merged" field from `pr view --json`.
                "state,url,headRefOid,statusCheckRollup,reviews,reviewDecision",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
            env=env,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError(
            f"gh query for PR #{pr_number} failed: {exc}"
        ) from exc

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"gh returned non-JSON for PR #{pr_number}: {proc.stdout!r}"
        ) from exc

    checks = data.get("statusCheckRollup") or []
    checks_state = _roll_up_check_state(checks)
    review_state = _roll_up_review_state(
        data.get("reviews") or [], decision=data.get("reviewDecision")
    )
    return {
        "merged": data.get("state") == "MERGED",
        "url": data.get("url"),
        "head_sha": data.get("headRefOid"),
        "checks_state": checks_state,
        "review_state": review_state,
    }


def _roll_up_check_state(checks: list[dict[str, Any]]) -> str | None:
    """Map a GitHub statusCheckRollup list to a single aggregate state."""
    if not checks:
        return None
    terminal = [c for c in checks if c.get("status") == "COMPLETED"]
    if any(c.get("conclusion") not in {"SUCCESS", "NEUTRAL", "SKIPPED"} for c in terminal):
        return "failed"
    if any(c.get("status") in ("QUEUED", "IN_PROGRESS", "PENDING") for c in checks):
        return "pending"
    if len(terminal) == len(checks) and all(
        c.get("conclusion") in {"SUCCESS", "NEUTRAL", "SKIPPED"}
        for c in terminal
    ):
        return "passed"
    return "unknown"


def _roll_up_review_state(
    reviews: list[dict[str, Any]], *, decision: str | None = None
) -> str | None:
    """Map GitHub reviews to an aggregate: approved / changes_requested / pending."""
    if decision == "APPROVED":
        return "approved"
    if decision == "CHANGES_REQUESTED":
        return "changes_requested"
    if decision == "REVIEW_REQUIRED":
        return "pending"
    if not reviews:
        return None
    latest: dict[str, dict[str, Any]] = {}
    for review in reviews:
        author = (review.get("author") or {}).get("login") or review.get("user", {}).get("login") or "?"
        current = latest.get(author)
        if current is None or str(review.get("submittedAt", "")) >= str(current.get("submittedAt", "")):
            latest[author] = review
    states = [r.get("state") for r in latest.values()]
    if any(s == "CHANGES_REQUESTED" for s in states):
        return "changes_requested"
    if any(s == "APPROVED" for s in states):
        return "approved"
    return "pending"


def sync_pr_status(
    db_path: Path | None = None,
    *,
    pr_status: Any = None,
) -> dict[str, Any]:
    """Advisory CI/review reconciliation into ``pr_links``.

    For every attached PR, refresh ``checks_state`` / ``review_state`` /
    ``head_sha`` / ``pr_url`` (and ``merged``), but never mutate task state —
    promotion happens only in ``detect_merged_prs``. ``pr_status`` is injectable
    for testing; defaults to ``_gh_pr_status`` (network + ``gh``).

    A single PR query failure is recorded under ``errors`` and skipped so one
    bad lookup does not abort the whole reconciliation pass.
    """
    fetcher = pr_status or _gh_pr_status
    init_db(db_path)
    conn = connect(db_path)
    try:
        links = conn.execute(
            "SELECT task_id, pr_number FROM pr_links"
        ).fetchall()
    finally:
        conn.close()

    synced: list[int] = []
    errors: list[dict[str, str]] = []
    for link in links:
        pr_number = int(link["pr_number"])
        task_id = str(link["task_id"])
        try:
            status = fetcher(pr_number)
        except Exception as exc:  # advisory: skip, record, continue
            errors.append({"pr_number": str(pr_number), "error": str(exc)})
            continue
        attach_pr(
            task_id,
            pr_number,
            pr_url=status.get("url"),
            head_sha=status.get("head_sha"),
            checks_state=status.get("checks_state"),
            review_state=status.get("review_state"),
            db_path=db_path,
        )
        if status.get("merged"):
            conn = connect(db_path)
            try:
                conn.execute(
                    "UPDATE pr_links SET merged = 1, "
                    "merged_at = strftime('%Y-%m-%d %H:%M:%f', 'now'), "
                    "updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') "
                    "WHERE task_id = ? AND pr_number = ?",
                    (task_id, pr_number),
                )
                conn.commit()
            finally:
                conn.close()
        synced.append(pr_number)

    return {"synced": synced, "errors": errors}


def detect_merged_prs(
    db_path: Path | None = None,
    *,
    pr_merged: Any = None,
) -> dict[str, Any]:
    """Promote tasks whose linked PR has merged to ``done``.

    Scans tasks currently in ``awaiting_review`` (or ``pr_opened``) that have a
    ``pr_links`` row flagged merged, or whose merge status is resolved live via
    ``pr_merged(pr_number)`` (injectable; defaults to ``_gh_pr_status``). On
    merge, the task is driven to ``done`` through the legal state machine and
    the ``pr_links`` row is marked merged — which unlocks dependent packets via
    the existing KB-S1B eligibility rollup.

    Merge detection is read-only against GitHub and never pushes or merges; the
    builder remains operator-controlled per the architecture.
    """
    resolver = pr_merged or _gh_pr_status
    init_db(db_path)
    conn = connect(db_path)
    try:
        candidate_rows = conn.execute(
            """
            SELECT t.id AS task_id, t.state AS task_state, p.pr_number AS pr_number,
                   p.merged AS already_merged
            FROM tasks t
            JOIN pr_links p ON p.task_id = t.id
            WHERE t.state IN (?, ?, ?)
            """,
            (BLOCKED, PR_OPENED, AWAITING_REVIEW),
        ).fetchall()
    finally:
        conn.close()

    promoted: list[str] = []
    already_done: list[str] = []
    errors: list[dict[str, str]] = []
    for row in candidate_rows:
        task_id = str(row["task_id"])
        pr_number = int(row["pr_number"])
        try:
            if row["already_merged"]:
                is_merged = True
            else:
                status = resolver(pr_number)
                is_merged = bool(status.get("merged"))
        except Exception as exc:
            errors.append({"task_id": task_id, "error": str(exc)})
            continue

        if not is_merged:
            continue

        try:
            _mark_pr_merged(task_id, pr_number, db_path)
            _promote_merged_task(task_id, db_path)
        except Exception as exc:
            errors.append({"task_id": task_id, "error": str(exc)})
            continue
        promoted.append(task_id)

    return {
        "promoted": promoted,
        # kept key for CLI compat; now lists none by design (promotion always
        # attempted when merged). Reserved for future "already done" reporting.
        "already_merged": already_done,
        "errors": errors,
    }


def _mark_pr_merged(
    task_id: str, pr_number: int, db_path: Path | None
) -> None:
    """Set pr_links.merged=1 once GitHub confirms merge (idempotent)."""
    conn = connect(db_path)
    try:
        conn.execute(
            """
            UPDATE pr_links
            SET merged = 1,
                merged_at = COALESCE(
                    merged_at, strftime('%Y-%m-%d %H:%M:%f', 'now')
                ),
                updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
            WHERE task_id = ? AND pr_number = ?
            """,
            (task_id, pr_number),
        )
        conn.commit()
    finally:
        conn.close()


def _promote_merged_task(task_id: str, db_path: Path | None) -> None:
    """Drive a merged PR's task to ``done`` through the legal state machine."""
    task = get_task(task_id, db_path=db_path)
    if task is None:
        raise TaskNotFoundError(f"task not found: {task_id}")
    state = task["state"]
    if state == DONE:
        return
    if state == BLOCKED:
        report = task.get("final_report")
        if not isinstance(report, dict):
            raise IllegalTransitionError(
                f"task {task_id} is blocked without a final shadow report"
            )
        if report.get("scope_violations") or report.get("outcome") in {
            RUN_FAILED,
            RUN_TIMEOUT,
            RUN_CANCELLED,
            RUN_SCOPE_VIOLATION,
            RUN_LEASE_LOST,
        }:
            raise IllegalTransitionError(
                f"task {task_id} has a failed or scope-violating shadow report"
            )
        transition_task(task_id, PR_OPENED, db_path=db_path)
        transition_task(task_id, AWAITING_REVIEW, db_path=db_path)
        transition_task(task_id, DONE, db_path=db_path)
    elif state == AWAITING_REVIEW:
        transition_task(task_id, DONE, db_path=db_path)
    elif state == PR_OPENED:
        transition_task(task_id, AWAITING_REVIEW, db_path=db_path)
        transition_task(task_id, DONE, db_path=db_path)
    else:
        raise IllegalTransitionError(
            f"task {task_id} in state {state!r} cannot be merged-promoted"
        )


def get_pr_links(
    task_id: str,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return all PR links for a task, newest PR number last.

    Raises TaskNotFoundError if the task does not exist.
    """
    conn = connect(db_path)
    try:
        task_row = conn.execute(
            "SELECT id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if task_row is None:
            raise TaskNotFoundError(f"task not found: {task_id}")
        rows = conn.execute(
            "SELECT * FROM pr_links WHERE task_id = ? ORDER BY pr_number ASC",
            (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Phase 1C-alpha — lease renewal (heartbeat)
# ---------------------------------------------------------------------------




# Run lifecycle functions (``generate_run_id``, ``create_run``,
# ``get_run``, ``list_runs``, ``update_run``, ``finalize_run``,
# ``capture_process_identity``, ``recover_interrupted_runs``, plus
# ``RunNotFoundError`` / ``ActiveRunConflictError`` /
# ``RunStateConflictError`` / ``_validate_run_transition``) live in
# :mod:`gateway.builder_queue_runs` (audit §2.2 third cut) and are
# re-exported via the façade below so callers keep working.
# ---------------------------------------------------------------------------
# Branch-lease lifecycle (``claim_branch_lease``,
# ``verify_branch_lease``, ``get_branch_lease``,
# ``release_branch_lease``, plus the ``_claim_branch_lease_on_conn``
# / ``_release_branch_lease_on_conn`` / ``_validate_branch_lease_fields``
# helpers) lives in :mod:`gateway.builder_queue_branch_leases`
# (audit §2.2 fourth cut) and is re-exported via the façade below.
