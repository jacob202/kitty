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


class LeaseConflictError(ValueError):
    """Raised when a task cannot be claimed or lease fencing rejects a stale worker."""


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
            task["allowed_paths"] = json.loads(ap)
        except (json.JSONDecodeError, TypeError):
            task["allowed_paths"] = None
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
    if terminal or new_state == QUEUED:
        set_clause += (
            ", lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL"
        )

    sql = (
        f"UPDATE tasks SET {set_clause}"
        " WHERE id = ? AND state = ? AND archived_at IS NULL"
        f" {extra_where}"
    )

    cursor = conn.execute(sql, (new_state, task_id, current_state, *extra_params))

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
