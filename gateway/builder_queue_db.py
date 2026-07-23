"""Builder queue DB layer — Task 4.3 state machine + connection/init.

Extracted from :mod:`gateway.builder_queue` as the first cut of audit §2.2.
This module owns the lowest layer of the KittyBuilder persistence stack:

* Task-state machine constants & legal transition map
* Public exception classes for missing/unreachable/conflict conditions
* The full SQLite schema DDL (``_SCHEMA_SQL``)
* Connection pragmas, schema bootstrap, and column-add migrations
* :func:`init_db` and :func:`connect` — used by every higher layer

Public symbols are re-exported from :mod:`gateway.builder_queue` (which keeps
its existing ``bq.X`` / ``from gateway.builder_queue import X`` surface), so
sibling modules such as :mod:`gateway.builder_attempt`,
:mod:`gateway.builder_runner`, :mod:`gateway.builder_initiative`, and the
builder CLI/tests continue to work unchanged.

Scope guard: business logic (claims, leases, runs, branch leases, PR
reconciliation) stays in :mod:`gateway.builder_queue` and its subsequent
extractions. Subsequent cuts will lift those modules into
``builder_queue_leases`` / ``builder_queue_runs`` / ``builder_queue_events``
in the order recommended by the audit.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from gateway.paths import BUILDER_QUEUE_DB

logger = logging.getLogger("kitty.builder_queue_db")

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


class BranchLeaseConflictError(ValueError):
    """Raised when a branch lease is already held or a release is attempted by the wrong owner."""


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

-- Branch leases: exclusive per packet within an initiative, per worker
-- within an initiative, and unique per branch and worktree globally.
-- base_sha is verification metadata only; several packets may share it.
-- initiative_id scopes the packet_id and worker_id uniqueness so v1/v2
-- retries of the same packet from different initiatives can coexist.
CREATE TABLE IF NOT EXISTS branch_leases (
    lease_id INTEGER PRIMARY KEY AUTOINCREMENT,
    initiative_id TEXT NOT NULL CHECK (initiative_id != ''),
    packet_id TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    branch TEXT NOT NULL UNIQUE,
    worktree_path TEXT NOT NULL UNIQUE,
    base_sha TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (initiative_id, packet_id),
    UNIQUE (initiative_id, worker_id)
);
"""

# ---------------------------------------------------------------------------
# Connection / init helpers
# ---------------------------------------------------------------------------

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
    _ensure_branch_lease_columns(conn)
    # Run *after* _ensure_branch_lease_columns so lease_ts→created_at
    # migration completes first; this migration rebuilds the table.
    _ensure_branch_lease_initiative_id(conn)
    # Ensure initiative_id is required (no default '') and has CHECK constraint.
    _ensure_branch_lease_initiative_id_required(conn)


def _ensure_branch_lease_initiative_id(conn: sqlite3.Connection) -> None:
    """Migrate pre-initiative_id databases: add initiative_id + composite UNIQUE.

    The original schema used ``packet_id TEXT NOT NULL UNIQUE`` and a global
    ``idx_branch_leases_worker`` on ``worker_id`` — neither scoped by
    initiative, so a v2 retry of the same packet (e.g. ``-v2`` after
    ``-v1`` exhausted) could not create a lease without first deleting or
    conflicting with v1's row. SQLite cannot alter a UNIQUE constraint in
    place, so this rebuilds the table.

    Legacy rows get a placeholder initiative_id so the NOT NULL constraint passes.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(branch_leases)")}
    if "initiative_id" in cols:
        return
    # Table rebuild: create new schema, copy, swap.
    old_cols = [c for c in ("lease_id", "packet_id", "worker_id",
                             "branch", "worktree_path", "base_sha",
                             "created_at")
                if c in cols]
    old_list = ", ".join(old_cols)
    conn.executescript(f"""
        CREATE TABLE branch_leases_new (
            lease_id INTEGER PRIMARY KEY AUTOINCREMENT,
            initiative_id TEXT NOT NULL CHECK (initiative_id != ''),
            packet_id TEXT NOT NULL,
            worker_id TEXT NOT NULL,
            branch TEXT NOT NULL UNIQUE,
            worktree_path TEXT NOT NULL UNIQUE,
            base_sha TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (initiative_id, packet_id),
            UNIQUE (initiative_id, worker_id)
        );
        INSERT INTO branch_leases_new (lease_id, initiative_id, {old_list})
            SELECT lease_id, 'legacy-migrated', {old_list} FROM branch_leases;
        DROP TABLE branch_leases;
        ALTER TABLE branch_leases_new RENAME TO branch_leases;
    """)


def _ensure_branch_lease_initiative_id_required(conn: sqlite3.Connection) -> None:
    """Ensure initiative_id is required (no default '') and add CHECK constraint.

    SQLite cannot drop a DEFAULT or add a CHECK constraint in place, so this
    rebuilds the table if the schema still has the legacy DEFAULT '' or lacks
    the CHECK constraint.

    Legacy rows with empty initiative_id are updated to a placeholder so the
    CHECK constraint can be enforced going forward.
    """
    cols = {row[1]: row for row in conn.execute("PRAGMA table_info(branch_leases)")}
    if "initiative_id" not in cols:
        return
    col = cols["initiative_id"]
    # col[4] is the default value, col[5] is notnull (0 or 1)
    has_default_empty = col[4] == ''
    # Check for CHECK constraint on initiative_id
    table_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='branch_leases'"
    ).fetchone()
    has_check = table_sql and 'CHECK (initiative_id' in table_sql[0]

    if not has_default_empty and has_check:
        return

    # Check if there are legacy rows with empty initiative_id
    legacy_count = conn.execute(
        "SELECT COUNT(*) FROM branch_leases WHERE initiative_id = ''"
    ).fetchone()[0]

    # Rebuild table with required initiative_id and CHECK constraint
    # Use a placeholder for legacy rows so the CHECK constraint passes
    placeholder = "legacy-migrated" if legacy_count > 0 else None
    if legacy_count > 0:
        conn.execute(
            "UPDATE branch_leases SET initiative_id = ? WHERE initiative_id = ''",
            (placeholder,),
        )

    conn.executescript("""
        CREATE TABLE branch_leases_new (
            lease_id INTEGER PRIMARY KEY AUTOINCREMENT,
            initiative_id TEXT NOT NULL CHECK (initiative_id != ''),
            packet_id TEXT NOT NULL,
            worker_id TEXT NOT NULL,
            branch TEXT NOT NULL UNIQUE,
            worktree_path TEXT NOT NULL UNIQUE,
            base_sha TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (initiative_id, packet_id),
            UNIQUE (initiative_id, worker_id)
        );
        INSERT INTO branch_leases_new (lease_id, initiative_id, packet_id, worker_id,
                                       branch, worktree_path, base_sha, created_at)
            SELECT lease_id, initiative_id, packet_id, worker_id,
                   branch, worktree_path, base_sha, created_at
            FROM branch_leases;
        DROP TABLE branch_leases;
        ALTER TABLE branch_leases_new RENAME TO branch_leases;
    """)


def _ensure_branch_lease_columns(conn: sqlite3.Connection) -> None:
    """Migrate pre-rename databases where branch_leases used ``lease_ts``.

    The schema renamed the column to ``created_at`` without a migration, so
    live DBs created before the rename break every reader (builder_status's
    lease join being the visible one).
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(branch_leases)")}
    if "lease_ts" in cols and "created_at" not in cols:
        conn.execute("ALTER TABLE branch_leases RENAME COLUMN lease_ts TO created_at")


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


def _default_db_path() -> Path:
    """Resolve the default DB path through :mod:`gateway.builder_queue`.

    The historical monkeypatch seam is ``builder_queue.BUILDER_QUEUE_DB``
    (dozens of tests patch it). After the audit §2.2 split, sibling modules
    (`builder_queue_runs`, `builder_queue_leases`, …) default through this
    module — so the default MUST read the facade's global at call time, or a
    patched test writes tasks to one DB and reads them from another.
    """
    import sys

    facade = sys.modules.get("gateway.builder_queue")
    if facade is not None:
        patched = getattr(facade, "BUILDER_QUEUE_DB", None)
        if patched is not None:
            return Path(patched)
    return BUILDER_QUEUE_DB


def init_db(db_path: Path | None = None) -> None:
    """Initialize the Builder queue DB: create parent dir, schema, pragmas.

    Safe to call repeatedly. Does not drop existing tables or rows.
    """
    path = Path(db_path) if db_path is not None else _default_db_path()
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
    path = Path(db_path) if db_path is not None else _default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn
