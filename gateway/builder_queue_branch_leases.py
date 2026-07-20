"""Builder queue branch leases \u2014 packet/worker/branch/worktree exclusive leases.

Extracted from :mod:`gateway.builder_queue` as the fourth cut of audit
\u00a72.2 (the order has been DB \u00a71, lease lifecycle \u00a72, run lifecycle \u00a73,
branch leases \u00a74, events/PRs \u00a75 \u2014 split earlier in builder_queue.py so
each cut owns a coherent lifecycle).

Owns the ``KB-S2 atomic claim_and_start_attempt`` support: an exclusive
lease keyed by ``(packet_id, worker_id, branch, worktree_path)`` with a
verification-only ``base_sha`` for shared-base pinning. ``claim_branch_lease``
inserts with a unique-index guarantee; ``verify_branch_lease`` reads
back; ``release_branch_lease`` does an owner-fenced delete. The two
``on_conn`` variants let sibling code (``gateway.builder_attempt`` and
``gateway.builder_identity``) participate in the caller's transaction
for atomic packet-launch plumbing.

Public symbols are re-exported from :mod:`gateway.builder_queue` via the
fa\u00e7ade so callers (``gateway.builder_attempt``, ``gateway.builder_identity``,
``gateway.builder_loop``, CLI, tests) work unchanged.

Active-mission note (:file:`.claude/STATE.md`): the chat-recovery work
``CR-02-thread-goals-ui`` is independent of this module.

Dependency resolution: this module imports from ``gateway.builder_queue_db``
only (no parent\u2194child cycle with ``gateway.builder_queue``). The branch-lease
lifecycle never calls ``append_event`` or ``_apply_transition`` \u2014 every
operation here is purely SQL on the ``branch_leases`` table \u2014 so the
simple top-level import of :mod:`gateway.builder_queue_db` is safe.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from gateway.builder_queue_db import BranchLeaseConflictError, connect, init_db

logger = logging.getLogger("kitty.builder_queue_branch_leases")


def _validate_branch_lease_fields(
    packet_id: str,
    worker_id: str,
    branch: str,
    worktree_path: str,
    base_sha: str,
) -> str:
    """Validate and canonicalize values shared by every lease claim path."""
    for name, value in (
        ("packet_id", packet_id),
        ("worker_id", worker_id),
        ("branch", branch),
        ("worktree_path", worktree_path),
        ("base_sha", base_sha),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} is required")
    if len(base_sha) != 40 or any(
        character not in "0123456789abcdef" for character in base_sha
    ):
        raise ValueError("base_sha must be a full lowercase 40-character Git SHA")
    return str(Path(worktree_path).expanduser().resolve())


def _claim_branch_lease_on_conn(
    conn: sqlite3.Connection,
    packet_id: str,
    worker_id: str,
    branch: str,
    worktree_path: str,
    base_sha: str,
) -> sqlite3.Row:
    """Insert a branch lease inside the caller's active transaction."""
    canonical_worktree = _validate_branch_lease_fields(
        packet_id, worker_id, branch, worktree_path, base_sha
    )
    try:
        conn.execute(
            """
            INSERT INTO branch_leases
                (packet_id, worker_id, branch, worktree_path, base_sha)
            VALUES (?, ?, ?, ?, ?)
            """,
            (packet_id, worker_id, branch, canonical_worktree, base_sha),
        )
    except sqlite3.IntegrityError as exc:
        existing = conn.execute(
            "SELECT packet_id, worker_id, branch, worktree_path "
            "FROM branch_leases "
            "WHERE packet_id = ? OR worker_id = ? "
            "   OR branch = ? OR worktree_path = ?",
            (packet_id, worker_id, branch, canonical_worktree),
        ).fetchone()
        if existing is None:
            raise BranchLeaseConflictError(
                f"branch lease conflict for packet {packet_id!r}"
            ) from exc
        conflicting_field = "unknown"
        if existing["packet_id"] == packet_id:
            conflicting_field = "packet_id"
        elif existing["worker_id"] == worker_id:
            conflicting_field = "worker_id"
        elif existing["branch"] == branch:
            conflicting_field = "branch"
        elif existing["worktree_path"] == canonical_worktree:
            conflicting_field = "worktree_path"
        raise BranchLeaseConflictError(
            f"branch lease conflict: {conflicting_field} is already claimed "
            f"by packet {existing['packet_id']!r}"
        ) from exc

    lease = conn.execute(
        "SELECT * FROM branch_leases WHERE packet_id = ?", (packet_id,)
    ).fetchone()
    if lease is None:
        raise RuntimeError(
            f"branch lease for packet {packet_id!r} was inserted but is not retrievable"
        )
    return lease


def claim_branch_lease(
    packet_id: str,
    worker_id: str,
    branch: str,
    worktree_path: str,
    base_sha: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Atomically claim an exclusive packet/worker/branch/worktree lease."""
    init_db(db_path)
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        lease = _claim_branch_lease_on_conn(
            conn, packet_id, worker_id, branch, worktree_path, base_sha
        )
        conn.commit()
        return dict(lease)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def verify_branch_lease(
    packet_id: str, *, db_path: Path | None = None
) -> dict[str, Any] | None:
    """Return the active lease for ``packet_id``, or ``None`` when absent."""
    init_db(db_path)
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM branch_leases WHERE packet_id = ?", (packet_id,)
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def get_branch_lease(
    lease_id: int, *, db_path: Path | None = None
) -> dict[str, Any] | None:
    """Return one active lease by ID, or ``None`` when absent."""
    init_db(db_path)
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM branch_leases WHERE lease_id = ?", (lease_id,)
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def _release_branch_lease_on_conn(
    conn: sqlite3.Connection,
    lease_id: int,
    *,
    packet_id: str,
    worker_id: str,
) -> None:
    """Delete exactly one owner-matched lease in the caller's transaction."""
    cursor = conn.execute(
        "DELETE FROM branch_leases "
        "WHERE lease_id = ? AND packet_id = ? AND worker_id = ?",
        (lease_id, packet_id, worker_id),
    )
    if cursor.rowcount != 1:
        raise BranchLeaseConflictError(
            f"branch lease {lease_id} not found for packet {packet_id!r}, "
            f"worker {worker_id!r}"
        )


def release_branch_lease(
    lease_id: int,
    *,
    packet_id: str,
    worker_id: str,
    db_path: Path | None = None,
) -> None:
    """Release one lease using an atomic owner-fenced delete.

    Missing leases and mismatched packet/worker identities are conflicts, not
    idempotent success: a caller must never silently release stale ownership.
    """
    init_db(db_path)
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        _release_branch_lease_on_conn(
            conn, lease_id, packet_id=packet_id, worker_id=worker_id
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


__all__ = [
    "claim_branch_lease",
    "get_branch_lease",
    "release_branch_lease",
    "verify_branch_lease",
]
