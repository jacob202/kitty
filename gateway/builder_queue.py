"""KittyBuilder Phase 1A — durable local Builder queue store & state machine.

Library-mode SQLite storage for the KittyBuilder orchestrator. Scope so far:
schema, connection helpers, task creation/retrieval/listing, append-only event
log, and state machine transitions. This module does not implement claim/
fencing, CLI commands, daemon/API, worker execution, worktrees, or PR
automation yet.

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
import secrets
import sqlite3
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
    BLOCKED: frozenset({RUNNING, QUEUED, FAILED, CANCELLED}),
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
"""

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
) -> dict[str, Any]:
    """Create a task in state ``queued`` and append a ``created`` event.

    Bridge idempotency: the unique index on
    ``(bridge_source, bridge_external_id)`` (where both are non-null) prevents
    duplicate inserts for the same bridge tuple. On a duplicate, IntegrityError
    is raised and NO ``created`` event is appended.

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

    conn = connect(db_path)
    try:
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
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    created = get_task(task_id, db_path=db_path)
    if created is None:
        # Should be impossible given the commit above; fail loud per AGENTS.md.
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
            INSERT INTO events (task_id, type, payload_json)
            VALUES (?, ?, ?)
            """,
            (task_id, event_type, payload_json),
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
) -> None:
    """Apply a state transition on *conn* (inside an open transaction).

    Validates states, checks legality, updates the row, and appends an
    event. Does **not** commit — the caller owns the transaction.

    Raises:
        IllegalTransitionError — illegal, stale, or archived.
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
    if terminal:
        set_clause += (
            ", lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL"
        )

    sql = (
        f"UPDATE tasks SET {set_clause}"
        " WHERE id = ? AND state = ? AND archived_at IS NULL"
        f" {extra_where}"
    )

    cursor = conn.execute(sql, (new_state, task_id, current_state, *extra_params))

    if cursor.rowcount != 1:
        raise IllegalTransitionError(
            "transition failed; task changed, archived, or lease guard failed"
        )

    append_event(task_id, new_state, payload=payload, conn=conn)


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
