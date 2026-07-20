"""Builder queue leases — claim/release/heartbeat/fence for task workers.

Extracted from :mod:`gateway.builder_queue` as the second cut of audit §2.2
(the DB-layer cut was §2.2 first cut, into :mod:`gateway.builder_queue_db`).

Owns the lifecycle of worker claims on individual tasks: claim/next,
lease fencing via token + claim_version, lease heartbeat renewal
(:func:`renew_lease`), expired-lease recovery
(:func:`recover_expired_leases`), and operator-side release paths.

Public symbols are re-exported from :mod:`gateway.builder_queue` via the
façade so callers (``gateway.builder_attempt``,
``gateway.builder_runner``, ``gateway.builder_initiative``, CLI, tests)
work unchanged.

Active-mission note (:file:`.claude/STATE.md`): the chat-recovery work
``CR-02-thread-goals-ui`` is independent of this module. The runner's
heartbeat loop (:func:`gateway.builder_runner.run_worker`) calls
:func:`renew_lease` every N seconds; preserve fencing semantics
(``lease_token`` + ``claim_version`` match) when changing this module.

Dependency resolution: imports from ``gateway.builder_queue`` are
performed lazily inside functions to break the parent-imports-child /
child-imports-parent cycle at module-import time. The parent
(``gateway.builder_queue``) loads this module first, and any cross
module call from a lease function picks up the parent's fully-loaded
namespace at call time.
"""

from __future__ import annotations

import logging
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from gateway.builder_queue_db import (
    BLOCKED,
    CLAIMED,
    QUEUED,
    RUNNING,
    IllegalTransitionError,
    LeaseConflictError,
    TaskNotFoundError,
    connect,
)

logger = logging.getLogger("kitty.builder_queue_leases")


def _generate_lease_token() -> str:
    """Return a 64-character hex token for lease fencing."""
    return secrets.token_hex(32)


def _claim_impl(
    conn: sqlite3.Connection,
    task_id: str,
    worker_id: str,
    *,
    lease_seconds: int = 1800,
) -> tuple[str, int]:
    """Claim *task_id* on an open transaction and return token/version."""
    # Lazy import to avoid the parent↔child cycle at module-import time;
    # ``gateway.builder_queue.append_event`` uses the caller's open txn
    # so it must be resolved per-call rather than at module load.
    import gateway.builder_queue as _bq

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
    _bq.append_event(
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
    import gateway.builder_queue as _bq

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
        result = _bq._get_task_on_conn(conn, task_id)
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
    import gateway.builder_queue as _bq

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
        result = _bq._get_task_on_conn(conn, claimed_task_id)
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
    """Read the task row and verify it can be transitioned."""
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
    import gateway.builder_queue as _bq

    conn = connect(db_path)
    result: dict[str, Any] | None = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _transition_subject(conn, task_id)
        _bq._apply_transition(
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
        result = _bq._get_task_on_conn(conn, task_id)
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
    import gateway.builder_queue as _bq

    conn = connect(db_path)
    result: dict[str, Any] | None = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _transition_subject(conn, task_id)
        _bq._apply_transition(
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
        result = _bq._get_task_on_conn(conn, task_id)
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
    """Privileged release from ``claimed`` or ``blocked`` back to ``queued``.

    Refuses while the task is ``running`` — the operator must block a
    running task first via :func:`transition_task` so the lease-scoped
    fencing semantics hold.
    """
    import gateway.builder_queue as _bq

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
        _bq._apply_transition(
            conn,
            task_id,
            row["state"],
            QUEUED,
            payload=payload,
            event_type="operator_released",
        )
        result = _bq._get_task_on_conn(conn, task_id)
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
    """Recover expired worker leases in one transaction.

    Scans for claimed tasks whose lease has expired and requeues them,
    then scans for running tasks whose lease has expired and blocks them
    with reason ``stale_heartbeat``. Both scans happen in a single
    ``BEGIN IMMEDIATE`` transaction so two scans interleaving cannot
    leave inconsistent state. Returns counts for telemetry.
    """
    import gateway.builder_queue as _bq

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
                _bq.append_event(
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
                _bq.append_event(
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

    Raises :class:`gateway.builder_queue_db.LeaseConflictError` when fencing
    fails or the lease is expired.
    """
    import gateway.builder_queue as _bq

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
        result = _bq._get_task_on_conn(conn, task_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if result is None:
        raise RuntimeError(f"Task {task_id} lease renewed but is not retrievable")
    return result
