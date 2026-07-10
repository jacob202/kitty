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
import secrets
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

from gateway.paths import BUILDER_QUEUE_DB

logger = logging.getLogger("kitty.builder_queue")

# ---------------------------------------------------------------------------
# State constants (Section 4.3 — legal state machine)
# ---------------------------------------------------------------------------

QUEUED = "queued"
CLAIMED = "claimed"
RUNNING = "running"
PR_OPENED = "pr_opened"
AWAITING_REVIEW = "awaiting_review"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"
BLOCKED = "blocked"

TERMINAL_STATES = frozenset({DONE, FAILED, CANCELLED})

_VALID_STATES = frozenset({
    QUEUED,
    CLAIMED,
    RUNNING,
    PR_OPENED,
    AWAITING_REVIEW,
    DONE,
    FAILED,
    CANCELLED,
    BLOCKED,
})

LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    QUEUED: frozenset({CLAIMED, FAILED, CANCELLED}),
    CLAIMED: frozenset({RUNNING, FAILED, CANCELLED, QUEUED}),
    RUNNING: frozenset({BLOCKED, PR_OPENED, FAILED, CANCELLED}),
    PR_OPENED: frozenset({AWAITING_REVIEW, FAILED, CANCELLED}),
    AWAITING_REVIEW: frozenset({DONE, FAILED, CANCELLED}),
    # Operator publish (KB-S4) may advance shadow-blocked work to pr_opened.
    BLOCKED: frozenset({RUNNING, QUEUED, FAILED, CANCELLED, PR_OPENED}),
    DONE: frozenset(),
    FAILED: frozenset(),
    CANCELLED: frozenset(),
}

# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------


class TaskNotFoundError(ValueError):
    """Raised when a task ID does not exist."""


class IllegalTransitionError(ValueError):
    """Raised when a state transition is not legal or the task is archived."""


class LeaseConflictError(ValueError):
    """Raised when a task cannot be claimed or lease fencing rejects a stale worker."""


class DataCorruptionError(RuntimeError):
    """Raised when a DB column contains data that cannot be decoded."""


# ---------------------------------------------------------------------------
# Schema (Phase 1A — tasks + events only; runs/pr_links/artifacts are future)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    state TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER DEFAULT 0,
    lease_owner TEXT,
    lease_token TEXT,
    lease_expires_at TIMESTAMP,
    claim_version INTEGER DEFAULT 0,
    acceptance_criteria_json TEXT,
    bridge_source TEXT,
    bridge_issue TEXT,
    bridge_external_id TEXT,
    bridge_comment_url TEXT,
    workflow_ref TEXT,
    workflow_sha TEXT,
    repo_path TEXT,
    allowed_paths_json TEXT,
    blocked_reason TEXT,
    last_error TEXT,
    final_report_json TEXT,
    archived_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_claim
    ON tasks(state, priority DESC, id ASC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_bridge_external
    ON tasks(bridge_source, bridge_external_id)
    WHERE bridge_source IS NOT NULL AND bridge_external_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    run_id TEXT,
    type TEXT NOT NULL,
    payload_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- Append-only enforcement: block UPDATE and DELETE on the event log.
CREATE TRIGGER IF NOT EXISTS prevent_event_updates BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'Event log is append-only; UPDATE is not permitted');
END;
CREATE TRIGGER IF NOT EXISTS prevent_event_deletes BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'Event log is append-only; DELETE is not permitted');
END;

-- Phase 1B: PR metadata links. Advisory only — GitHub data never mutates
-- task state (Section 11.4). One row per (task, PR number), updated in
-- place as checks/review state are synced.
CREATE TABLE IF NOT EXISTS pr_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    pr_url TEXT,
    head_sha TEXT,
    checks_state TEXT,
    review_state TEXT,
    merged INTEGER NOT NULL DEFAULT 0,
    merged_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pr_links_task_pr
    ON pr_links(task_id, pr_number);

-- Phase 1C-alpha: worker run records. One row per execution attempt,
-- updated in place as the attempt progresses. History = multiple rows.
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'starting',
    command_json TEXT NOT NULL,
    claim_version INTEGER,
    worker TEXT,
    model TEXT,
    provider TEXT,
    pid INTEGER,
    process_identity TEXT,
    branch TEXT,
    worktree_path TEXT,
    start_sha TEXT,
    log_path TEXT,
    exit_code INTEGER,
    final_report_json TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    last_heartbeat_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id, id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_one_active_per_task
    ON runs(task_id)
    WHERE state IN ('starting', 'running', 'cancel_requested');
"""

# Run lifecycle states (runs table). Terminal: exited/failed/timeout/
# cancelled/interrupted.
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

_PRAGMAS = (
    "PRAGMA journal_mode=WAL;",
    "PRAGMA busy_timeout=5000;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA synchronous=NORMAL;",
)


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply the Phase 1A connection pragmas (Section 4.2)."""
    for pragma in _PRAGMAS:
        conn.execute(pragma)


def _apply_schema(conn: sqlite3.Connection) -> None:
    """Create tables, indexes, and triggers if absent. Idempotent."""
    conn.executescript(_SCHEMA_SQL)
    _ensure_run_columns(conn)
    _ensure_pr_link_columns(conn)


def _ensure_pr_link_columns(conn: sqlite3.Connection) -> None:
    """Add KB-S4 merge-tracking columns to databases created pre-migration."""
    existing = {
        str(row["name"] if isinstance(row, sqlite3.Row) else row[1])
        for row in conn.execute("PRAGMA table_info(pr_links)").fetchall()
    }
    additions = {
        "merged": "INTEGER NOT NULL DEFAULT 0",
        "merged_at": "TIMESTAMP",
    }
    for column, sql_type in additions.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE pr_links ADD COLUMN {column} {sql_type}")


def _ensure_run_columns(conn: sqlite3.Connection) -> None:
    """Add Phase 1C-alpha run columns to databases created by the draft."""
    existing = {
        str(row["name"] if isinstance(row, sqlite3.Row) else row[1])
        for row in conn.execute("PRAGMA table_info(runs)").fetchall()
    }
    additions = {
        "claim_version": "INTEGER",
        "process_identity": "TEXT",
        "start_sha": "TEXT",
        "final_report_json": "TEXT",
    }
    for column, sql_type in additions.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {column} {sql_type}")


# ---------------------------------------------------------------------------
# Connection / init helpers
# ---------------------------------------------------------------------------


def init_db(db_path: Path | None = None) -> None:
    """Initialize the Builder queue DB: create parent dir, schema, pragmas.

    Safe to call repeatedly. Does not drop existing tables or rows.
    """
    path = Path(db_path) if db_path is not None else BUILDER_QUEUE_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        _apply_pragmas(conn)
        _apply_schema(conn)
        conn.commit()
    finally:
        conn.close()
    logger.info("Initialized KittyBuilder queue DB at %s", path)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection to the Builder queue DB with pragmas + Row factory.

    The caller is responsible for committing/closing. ``init_db`` is NOT
    called here — callers that need a schema-fresh DB should call
    ``init_db`` first. Most library paths go through the helpers below,
    which call this internally.
    """
    path = Path(db_path) if db_path is not None else BUILDER_QUEUE_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


# ---------------------------------------------------------------------------
# Task ID helper (no-dependency, roughly time-sortable)
# ---------------------------------------------------------------------------


def generate_task_id() -> str:
    """Return ``kb_<base36_unix_ms>_<hex4>``.

    base36 of the millisecond timestamp keeps the ID compact and
    monotonically increasing on a single machine; ``hex4`` adds 16 bits of
    local disambiguation so two creates in the same millisecond do not
    collide in practice.
    """
    unix_ms = int(time.time() * 1000)
    base36 = _to_base36(unix_ms)
    hex4 = secrets.token_hex(2)  # 2 bytes -> 4 hex chars
    return f"kb_{base36}_{hex4}"


def _generate_lease_token() -> str:
    """Return a 64-character hex token for lease fencing."""
    return secrets.token_hex(32)


def _to_base36(n: int) -> str:
    """Encode a non-negative integer as lowercase base36 (no leading zeros)."""
    if n < 0:
        raise ValueError("base36 encoding requires a non-negative integer")
    if n == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = []
    while n > 0:
        n, rem = divmod(n, 36)
        out.append(digits[rem])
    return "".join(reversed(out))


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
        where_parts = []
        params: list[Any] = []
        if state is not None:
            where_parts.append("state = ?")
            params.append(state)
        if not include_archived:
            where_parts.append("archived_at IS NULL")
        where_clause = " AND ".join(where_parts) if where_parts else "1 = 1"
        rows = conn.execute(
            f"""
            SELECT * FROM tasks
            WHERE {where_clause}
            ORDER BY state ASC, priority DESC, id ASC
            """,
            params,
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


# ---------------------------------------------------------------------------
# Claiming / lease fencing
# ---------------------------------------------------------------------------


def _claim_impl(
    conn: sqlite3.Connection,
    task_id: str,
    worker_id: str,
    *,
    lease_seconds: int = 1800,
) -> tuple[str, int]:
    """Claim *task_id* on an open transaction and return token/version."""
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be greater than zero")

    row = conn.execute(
        "SELECT id, state, archived_at FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    if row is None:
        raise TaskNotFoundError(f"task not found: {task_id}")
    if row["archived_at"] is not None:
        raise IllegalTransitionError(
            f"task {task_id} is archived and cannot be claimed"
        )

    lease_token = _generate_lease_token()
    lease_modifier = f"+{lease_seconds} seconds"
    cursor = conn.execute(
        """
        UPDATE tasks
        SET state = ?,
            lease_owner = ?,
            lease_token = ?,
            claim_version = claim_version + 1,
            lease_expires_at = strftime('%Y-%m-%d %H:%M:%f', 'now', ?),
            updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
        WHERE id = ?
          AND state = ?
          AND archived_at IS NULL
          AND (
              lease_token IS NULL
              OR lease_expires_at IS NULL
              OR lease_expires_at <= strftime('%Y-%m-%d %H:%M:%f', 'now')
          )
        """,
        (
            CLAIMED,
            worker_id,
            lease_token,
            lease_modifier,
            task_id,
            QUEUED,
        ),
    )
    if cursor.rowcount != 1:
        raise LeaseConflictError(
            f"task {task_id} is not claimable; it is claimed, running, or leased"
        )

    claimed_row = conn.execute(
        "SELECT claim_version FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if claimed_row is None:
        raise RuntimeError(f"Task {task_id} was claimed but is not retrievable")

    claim_version = int(claimed_row["claim_version"])
    append_event(
        task_id,
        CLAIMED,
        payload={"worker": worker_id, "claim_version": claim_version},
        conn=conn,
    )
    return lease_token, claim_version


def claim_task(
    task_id: str,
    worker_id: str,
    *,
    lease_seconds: int = 1800,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Claim a queued task for *worker_id* and return the updated task."""
    conn = connect(db_path)
    result: dict[str, Any] | None = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        _claim_impl(
            conn,
            task_id,
            worker_id,
            lease_seconds=lease_seconds,
        )
        result = _get_task_on_conn(conn, task_id)
        if result is None:
            raise RuntimeError(
                f"Task {task_id} was claimed but is not retrievable"
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return result


def claim_next(
    worker_id: str,
    *,
    lease_seconds: int = 1800,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Claim the highest-priority eligible queued task, or ``None``."""
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be greater than zero")

    conn = connect(db_path)
    claimed_task_id: str | None = None
    result: dict[str, Any] | None = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT id FROM tasks
            WHERE state = ?
              AND archived_at IS NULL
              AND (
                  lease_token IS NULL
                  OR lease_expires_at IS NULL
                  OR lease_expires_at <= strftime('%Y-%m-%d %H:%M:%f', 'now')
              )
            ORDER BY priority DESC, id ASC
            LIMIT 1
            """,
            (QUEUED,),
        ).fetchone()
        if row is None:
            conn.commit()
            return None

        claimed_task_id = row["id"]
        try:
            _claim_impl(
                conn,
                claimed_task_id,
                worker_id,
                lease_seconds=lease_seconds,
            )
        except LeaseConflictError:
            conn.rollback()
            return None
        result = _get_task_on_conn(conn, claimed_task_id)
        if result is None:
            raise RuntimeError(
                f"Task {claimed_task_id} was claimed but is not retrievable"
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if claimed_task_id is None:
        raise RuntimeError("claim_next committed without selecting a task")
    return result


def _transition_subject(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
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
    return row


def worker_transition_task(
    task_id: str,
    new_state: str,
    lease_token: str,
    claim_version: int,
    *,
    payload: dict[str, Any] | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Transition a task using worker lease fencing."""
    conn = connect(db_path)
    result: dict[str, Any] | None = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _transition_subject(conn, task_id)
        _apply_transition(
            conn,
            task_id,
            row["state"],
            new_state,
            payload=payload,
            extra_where=(
                "AND lease_token = ? "
                "AND claim_version = ? "
                "AND lease_expires_at > strftime('%Y-%m-%d %H:%M:%f', 'now')"
            ),
            extra_params=(lease_token, claim_version),
        )
        result = _get_task_on_conn(conn, task_id)
        if result is None:
            raise RuntimeError(
                f"Task {task_id} was transitioned but is not retrievable"
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return result


def worker_release_task(
    task_id: str,
    lease_token: str,
    claim_version: int,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Release a worker-held task back to ``queued`` with lease fencing."""
    conn = connect(db_path)
    result: dict[str, Any] | None = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _transition_subject(conn, task_id)
        _apply_transition(
            conn,
            task_id,
            row["state"],
            QUEUED,
            event_type="released",
            extra_where=(
                "AND lease_token = ? "
                "AND claim_version = ? "
                "AND lease_expires_at > strftime('%Y-%m-%d %H:%M:%f', 'now')"
            ),
            extra_params=(lease_token, claim_version),
        )
        result = _get_task_on_conn(conn, task_id)
        if result is None:
            raise RuntimeError(
                f"Task {task_id} was released but is not retrievable"
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return result


def operator_release_task(
    task_id: str,
    *,
    reason: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Privileged release from ``claimed`` or ``blocked`` back to ``queued``."""
    conn = connect(db_path)
    result: dict[str, Any] | None = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _transition_subject(conn, task_id)
        if row["state"] == RUNNING:
            raise IllegalTransitionError(
                "running tasks must be blocked before operator release"
            )

        payload = {"reason": reason} if reason is not None else None
        _apply_transition(
            conn,
            task_id,
            row["state"],
            QUEUED,
            payload=payload,
            event_type="operator_released",
        )
        result = _get_task_on_conn(conn, task_id)
        if result is None:
            raise RuntimeError(
                f"Task {task_id} was released but is not retrievable"
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return result


def recover_expired_leases(*, db_path: Path | None = None) -> dict[str, int]:
    """Recover expired worker leases in one transaction."""
    conn = connect(db_path)
    claimed_requeued = 0
    running_blocked = 0
    try:
        conn.execute("BEGIN IMMEDIATE")
        expired_claimed = conn.execute(
            """
            SELECT id FROM tasks
            WHERE state = ?
              AND archived_at IS NULL
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at <= strftime('%Y-%m-%d %H:%M:%f', 'now')
            ORDER BY id ASC
            """,
            (CLAIMED,),
        ).fetchall()
        for row in expired_claimed:
            cursor = conn.execute(
                """
                UPDATE tasks
                SET state = ?,
                    lease_owner = NULL,
                    lease_token = NULL,
                    lease_expires_at = NULL,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = ?
                  AND state = ?
                  AND archived_at IS NULL
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at <= strftime('%Y-%m-%d %H:%M:%f', 'now')
                """,
                (QUEUED, row["id"], CLAIMED),
            )
            if cursor.rowcount == 1:
                claimed_requeued += 1
                append_event(
                    row["id"],
                    "released",
                    payload={"reason": "lease_expired"},
                    conn=conn,
                )

        expired_running = conn.execute(
            """
            SELECT id FROM tasks
            WHERE state = ?
              AND archived_at IS NULL
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at <= strftime('%Y-%m-%d %H:%M:%f', 'now')
            ORDER BY id ASC
            """,
            (RUNNING,),
        ).fetchall()
        for row in expired_running:
            cursor = conn.execute(
                """
                UPDATE tasks
                SET state = ?,
                    blocked_reason = ?,
                    lease_owner = NULL,
                    lease_token = NULL,
                    lease_expires_at = NULL,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = ?
                  AND state = ?
                  AND archived_at IS NULL
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at <= strftime('%Y-%m-%d %H:%M:%f', 'now')
                """,
                (BLOCKED, "stale_heartbeat", row["id"], RUNNING),
            )
            if cursor.rowcount == 1:
                running_blocked += 1
                append_event(
                    row["id"],
                    BLOCKED,
                    payload={"reason": "stale_heartbeat"},
                    conn=conn,
                )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    total = claimed_requeued + running_blocked
    return {
        "claimed_requeued": claimed_requeued,
        "running_blocked": running_blocked,
        "total": total,
    }


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
                "merged,url,headRefOid,statusCheckRollup,reviews,reviewDecision",
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
        "merged": bool(data.get("merged")),
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


def renew_lease(
    task_id: str,
    lease_token: str,
    claim_version: int,
    *,
    lease_seconds: int = 60,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Extend a live lease by *lease_seconds* from now (heartbeat).

    Fenced: requires the current token + version AND an unexpired lease —
    a worker whose lease already lapsed must not resurrect it (the recovery
    scan owns that task now). Appends no event by design: renewals are not
    state changes and would flood the log at 10s cadence.

    Raises LeaseConflictError when fencing fails or the lease is expired.
    """
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """
            UPDATE tasks
            SET lease_expires_at = strftime('%Y-%m-%d %H:%M:%f', 'now', ?),
                updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
            WHERE id = ?
              AND lease_token = ?
              AND claim_version = ?
              AND lease_expires_at > strftime('%Y-%m-%d %H:%M:%f', 'now')
            """,
            (f"+{lease_seconds} seconds", task_id, lease_token, claim_version),
        )
        if cursor.rowcount != 1:
            raise LeaseConflictError(
                f"cannot renew lease for task {task_id}: stale token/version "
                "or lease already expired"
            )
        result = _get_task_on_conn(conn, task_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if result is None:
        raise RuntimeError(f"Task {task_id} lease renewed but not retrievable")
    return result


# ---------------------------------------------------------------------------
# Phase 1C-alpha — run records
# ---------------------------------------------------------------------------


def generate_run_id() -> str:
    """Return ``run_<base36_unix_ms>_<hex4>`` (same shape as task IDs)."""
    unix_ms = int(time.time() * 1000)
    return f"run_{_to_base36(unix_ms)}_{secrets.token_hex(2)}"


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
    """Create a run record in state ``starting`` for an existing task."""
    if not command:
        raise ValueError("command must be a non-empty list")

    run_id = generate_run_id()
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        task_row = conn.execute(
            "SELECT id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if task_row is None:
            raise TaskNotFoundError(f"task not found: {task_id}")
        fenced_task = conn.execute(
            """
            SELECT id FROM tasks
            WHERE id = ?
              AND state = ?
              AND lease_token = ?
              AND claim_version = ?
              AND lease_expires_at > strftime('%Y-%m-%d %H:%M:%f', 'now')
            """,
            (task_id, CLAIMED, lease_token, claim_version),
        ).fetchone()
        if fenced_task is None:
            raise LeaseConflictError(
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


def get_run(run_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    conn = connect(db_path)
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
    """List runs, optionally filtered by task and/or run state. Oldest first."""
    query = "SELECT * FROM runs"
    clauses: list[str] = []
    params: list[Any] = []
    if task_id is not None:
        clauses.append("task_id = ?")
        params.append(task_id)
    if state is not None:
        clauses.append("state = ?")
        params.append(state)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY id ASC"

    conn = connect(db_path)
    try:
        rows = conn.execute(query, params).fetchall()
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
    """Update a run record in place.

    ``expected_states`` makes the update conditional on the current state
    (used for cancel_requested handoff); a mismatch raises ValueError so
    callers cannot silently clobber a concurrent cancellation.
    """
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

    where = "id = ?"
    where_params: list[Any] = [run_id]
    if expected_states is not None:
        placeholders = ",".join("?" for _ in expected_states)
        where += f" AND state IN ({placeholders})"
        where_params.extend(sorted(expected_states))

    conn = connect(db_path)
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
            f"UPDATE runs SET {', '.join(set_parts)} WHERE {where}",
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

    If ownership changed after the runner's last heartbeat, the durable
    outcome is upgraded to ``lease_lost`` and the task row is left untouched.
    The per-run report is always retained on the run row.
    """
    if outcome not in RUN_TERMINAL_STATES:
        raise ValueError(f"run outcome must be terminal, got {outcome!r}")
    if not isinstance(report, dict) or not report:
        raise ValueError("run report must be a non-empty object")

    conn = connect(db_path)
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
            raise TaskNotFoundError(f"task not found for run {run_id}: {task_id}")

        task_state = str(task_row["state"])
        same_claim = int(task_row["claim_version"]) == claim_version
        lease_matches = bool(task_row["lease_matches"])
        runner_owns_running_task = task_state == RUNNING and lease_matches
        runner_owns_claimed_task = (
            task_state == CLAIMED
            and lease_matches
            and run_row["state"] in {RUN_STARTING, RUN_CANCEL_REQUESTED}
        )
        worker_advanced_task = (
            same_claim
            and task_state
            in {BLOCKED, PR_OPENED, AWAITING_REVIEW, DONE, FAILED, CANCELLED}
            and not (
                task_state == BLOCKED
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
        append_event(
            task_id,
            f"run_{effective_outcome}",
            payload={"run_id": run_id, "exit_code": exit_code},
            run_id=run_id,
            conn=conn,
        )

        if runner_owns_running_task:
            conn.execute(
                """
                UPDATE tasks
                SET final_report_json = ?,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = ?
                """,
                (json.dumps(final_report), task_id),
            )
            append_event(
                task_id,
                "report_attached",
                payload={"report": final_report},
                run_id=run_id,
                conn=conn,
            )
            _apply_transition(
                conn,
                task_id,
                RUNNING,
                BLOCKED,
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
        elif runner_owns_claimed_task:
            _apply_transition(
                conn,
                task_id,
                CLAIMED,
                QUEUED,
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
        elif worker_advanced_task:
            append_event(
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
    """Return the OS-reported process start time for PID-reuse fencing."""
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
    """Atomically mark dead active attempts as ``interrupted``.

    A newly inserted ``starting`` row has a short grace window so a recovery
    command cannot race the launcher before it records the child PID. For a
    live PID, the stored process start time must match before the attempt is
    treated as still running. Older rows without identity metadata are left
    untouched and reported as unverified rather than risking a reused PID.
    """
    import os as _os

    if starting_grace_seconds < 0:
        raise ValueError("starting_grace_seconds must be non-negative")

    interrupted: list[str] = []
    deferred: list[str] = []
    unverified: list[dict[str, str]] = []
    running_tasks_blocked = 0
    claimed_tasks_requeued = 0
    conflicts = 0
    conn = connect(db_path)
    try:
        # The write lock keeps launch activation from changing a row between
        # our liveness decision and the terminal update.
        conn.execute("BEGIN IMMEDIATE")
        placeholders = ",".join("?" for _ in RUN_ACTIVE_STATES)
        rows = conn.execute(
            f"SELECT * FROM runs WHERE state IN ({placeholders}) ORDER BY id ASC",
            tuple(sorted(RUN_ACTIVE_STATES)),
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
                    # Corrupt timestamp: skip this row and let the next
                    # recovery pass retry it rather than aborting the whole
                    # scan over one bad row.
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
                    # Corrupt pid: skip rather than abort the scan.
                    unverified.append(
                        {"run_id": run_id, "reason": "invalid_pid"}
                    )
                    continue

                try:
                    _os.kill(numeric_pid, 0)
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
                    # Capture identity immediately after the liveness check
                    # to minimize (but not eliminate) the PID-reuse TOCTOU
                    # window.  On macOS there is no O_CLOEXEC-equivalent for
                    # the process table, so a sufficiently fast reuse can
                    # still occur between kill(0) and ps(1).  We accept this
                    # residual risk and fail-safe to "unverifiable" when the
                    # identity cannot be proven.
                    current_identity = capture_process_identity(numeric_pid)
                    if current_identity is None:
                        # ps failed; re-check liveness before marking
                        # unverifiable — the process may have exited.
                        try:
                            _os.kill(numeric_pid, 0)
                        except ProcessLookupError:
                            reason = "pid_not_running"
                        else:
                            unverified.append(
                                {
                                    "run_id": run_id,
                                    "reason": "process_identity_unavailable",
                                }
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
                # Run changed between the SELECT and this UPDATE.  Under
                # normal SQLite write-lock semantics this is unreachable
                # (BEGIN IMMEDIATE prevents concurrent writes), but
                # exotic filesystem/NFS configurations may allow it.
                # The run is still active and will be retried on a
                # subsequent recovery pass.
                conflicts += 1
                continue
            append_event(
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
                    if task_row["state"] == RUNNING:
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
                                BLOCKED,
                                "run_interrupted",
                                task_id,
                                RUNNING,
                                run_claim_version,
                            ),
                        )
                        if task_cursor.rowcount != 1:
                            # Task row changed concurrently (exotic
                            # filesystem).  The run is already marked
                            # INTERRUPTED above; the task remains in
                            # its prior state and will be reconciled
                            # by the next recovery pass.
                            conflicts += 1
                            continue
                        append_event(
                            task_id,
                            BLOCKED,
                            payload={
                                "reason": "run_interrupted",
                                "run_id": run_id,
                            },
                            run_id=run_id,
                            conn=conn,
                        )
                        running_tasks_blocked += 1
                    elif (
                        task_row["state"] == CLAIMED
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
                            (QUEUED, task_id, CLAIMED, run_claim_version),
                        )
                        if task_cursor.rowcount != 1:
                            # Task row changed concurrently (exotic
                            # filesystem).  The run is already marked
                            # INTERRUPTED above; the task remains in
                            # its prior state and will be reconciled
                            # by the next recovery pass.
                            conflicts += 1
                            continue
                        append_event(
                            task_id,
                            "released",
                            payload={
                                "reason": "run_interrupted_before_start",
                                "run_id": run_id,
                            },
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
