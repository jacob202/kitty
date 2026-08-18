"""Durable Image Lab batch queue.

A batch is one user request for 1, 2, or 4 outputs. Child items survive
navigation and gateway restarts. Running provider work is never reported as
canceled or failed when the local worker loses ownership but the provider
outcome is not actually known.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from gateway import db as kitty_db
from gateway import paths as _paths
from gateway.paths import DB_MIGRATIONS_DIR

_MIGRATION_FILE = DB_MIGRATIONS_DIR / "034_image_batches.sql"
_VALID_COUNTS = frozenset({1, 2, 4})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_db(conn: Any = None) -> None:
    def apply(c: Any) -> None:
        c.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))

    if conn is not None:
        apply(conn)
    else:
        with kitty_db.connect(_paths.KITTY_DB_FILE) as c:
            apply(c)


def _copy_json(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value))


def scale_estimate(per_image: dict[str, Any], count: int) -> dict[str, Any]:
    if count not in _VALID_COUNTS:
        raise ValueError("image batch count must be one of 1, 2, or 4")
    estimate = _copy_json(per_image)
    raw_cost = estimate.get("cost")
    cost: dict[str, Any] = raw_cost if isinstance(raw_cost, dict) else {}
    estimate["cost"] = cost
    if cost.get("state") == "known" and cost.get("usd") is not None:
        cost["usd"] = round(float(cost["usd"]) * count, 6)
        cost["basis"] = f"{count} × ({cost.get('basis') or 'per-image estimate'})"
    raw_duration = estimate.get("duration")
    duration: dict[str, Any] = raw_duration if isinstance(raw_duration, dict) else {}
    estimate["duration"] = duration
    if duration.get("state") == "known" and duration.get("seconds") is not None:
        duration["seconds"] = round(float(duration["seconds"]) * count, 3)
        duration["basis"] = f"{count} sequential jobs × ({duration.get('basis') or 'per-image estimate'})"
    return estimate


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def create_batch(
    request: dict[str, Any], *, count: int, per_image_estimate: dict[str, Any]
) -> dict[str, Any]:
    if count not in _VALID_COUNTS:
        raise ValueError("image batch count must be one of 1, 2, or 4")
    now = _now_iso()
    batch_id = f"imgbatch_{uuid.uuid4().hex[:16]}"
    estimate = scale_estimate(per_image_estimate, count)
    session_id = request.get("session_id")
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute(
            """INSERT INTO image_batches
               (batch_id, session_id, status, count, request_json, estimate_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                batch_id,
                session_id,
                "queued",
                count,
                json.dumps(request, ensure_ascii=False),
                json.dumps(estimate, ensure_ascii=False),
                now,
                now,
            ),
        )
        for ordinal in range(count):
            conn.execute(
                """INSERT INTO image_batch_items
                   (item_id, batch_id, ordinal, status, created_at)
                   VALUES (?, ?, ?, 'queued', ?)""",
                (f"imgitem_{uuid.uuid4().hex[:16]}", batch_id, ordinal, now),
            )
        conn.commit()
    return get_batch(batch_id)


def get_batch(batch_id: str) -> dict[str, Any]:
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        row = conn.execute("SELECT * FROM image_batches WHERE batch_id = ?", (batch_id,)).fetchone()
        if row is None:
            raise KeyError(batch_id)
        items = conn.execute(
            "SELECT * FROM image_batch_items WHERE batch_id = ? ORDER BY ordinal", (batch_id,)
        ).fetchall()
    batch = _row_dict(row)
    batch["request"] = json.loads(batch.pop("request_json"))
    batch["estimate"] = json.loads(batch.pop("estimate_json"))
    batch["items"] = []
    for item_row in items:
        item = _row_dict(item_row)
        raw = item.pop("result_json")
        item["result"] = json.loads(raw) if raw else None
        batch["items"].append(item)
    return batch


def list_batches(*, session_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        if session_id:
            rows = conn.execute(
                "SELECT batch_id FROM image_batches WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT batch_id FROM image_batches ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [get_batch(row["batch_id"]) for row in rows]


def _refresh_batch(conn: Any, batch_id: str) -> None:
    counts = {
        row["status"]: row["n"]
        for row in conn.execute(
            "SELECT status, COUNT(*) AS n FROM image_batch_items WHERE batch_id = ? GROUP BY status",
            (batch_id,),
        ).fetchall()
    }
    if counts.get("running"):
        status = "running"
    elif counts.get("queued"):
        status = "queued"
    elif counts.get("unknown"):
        status = "unknown"
    elif counts.get("succeeded") and not counts.get("failed") and not counts.get("canceled"):
        status = "succeeded"
    elif counts.get("succeeded"):
        status = "partial"
    elif counts.get("canceled") and not counts.get("failed"):
        status = "canceled"
    else:
        status = "failed"
    conn.execute(
        "UPDATE image_batches SET status = ?, updated_at = ? WHERE batch_id = ?",
        (status, _now_iso(), batch_id),
    )


def claim_next_item() -> dict[str, Any] | None:
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT i.*, b.request_json
               FROM image_batch_items i
               JOIN image_batches b ON b.batch_id = i.batch_id
               WHERE i.status = 'queued'
               ORDER BY i.created_at, i.ordinal LIMIT 1"""
        ).fetchone()
        if row is None:
            conn.commit()
            return None
        now = _now_iso()
        changed = conn.execute(
            "UPDATE image_batch_items SET status = 'running', started_at = ? WHERE item_id = ? AND status = 'queued'",
            (now, row["item_id"]),
        ).rowcount
        if changed != 1:
            conn.rollback()
            return None
        conn.execute(
            "UPDATE image_batches SET status = 'running', updated_at = ? WHERE batch_id = ?",
            (now, row["batch_id"]),
        )
        conn.commit()
        item = _row_dict(row)
        item["request"] = json.loads(item.pop("request_json"))
        return item


def complete_item(item_id: str, result: dict[str, Any]) -> None:
    now = _now_iso()
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        row = conn.execute(
            "SELECT batch_id FROM image_batch_items WHERE item_id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise KeyError(item_id)
        conn.execute(
            """UPDATE image_batch_items
               SET status = 'succeeded', job_id = ?, result_json = ?, error = NULL, finished_at = ?
               WHERE item_id = ?""",
            (result.get("job_id"), json.dumps(result, ensure_ascii=False), now, item_id),
        )
        _refresh_batch(conn, row["batch_id"])
        conn.commit()


def fail_item(item_id: str, error: str, *, job_id: str | None = None) -> None:
    now = _now_iso()
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        row = conn.execute(
            "SELECT batch_id FROM image_batch_items WHERE item_id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise KeyError(item_id)
        conn.execute(
            """UPDATE image_batch_items
               SET status = 'failed', job_id = ?, error = ?, finished_at = ? WHERE item_id = ?""",
            (job_id, error[:1000], now, item_id),
        )
        _refresh_batch(conn, row["batch_id"])
        conn.commit()


def mark_item_unknown(item_id: str, reason: str, *, job_id: str | None = None) -> None:
    """Record loss of local ownership without inventing a provider outcome."""
    now = _now_iso()
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        row = conn.execute(
            "SELECT batch_id FROM image_batch_items WHERE item_id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise KeyError(item_id)
        conn.execute(
            """UPDATE image_batch_items
               SET status = 'unknown', job_id = COALESCE(?, job_id), error = ?, finished_at = ?
               WHERE item_id = ?""",
            (job_id, reason[:1000], now, item_id),
        )
        _refresh_batch(conn, row["batch_id"])
        conn.commit()


async def process_next(executor: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]) -> bool:
    item = claim_next_item()
    if item is None:
        return False
    try:
        result = await executor(item["request"])
    except asyncio.CancelledError:
        mark_item_unknown(
            item["item_id"],
            "gateway worker stopped while this image was running; provider outcome is unknown",
        )
        raise
    except Exception as exc:
        fail_item(item["item_id"], f"{type(exc).__name__}: {exc}")
    else:
        complete_item(item["item_id"], result)
    return True


async def worker_loop(
    executor: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]], *, idle_seconds: float = 0.5
) -> None:
    while True:
        if not await process_next(executor):
            await asyncio.sleep(idle_seconds)


def reconcile_inflight() -> int:
    now = _now_iso()
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        batch_ids = [
            row["batch_id"]
            for row in conn.execute(
                "SELECT DISTINCT batch_id FROM image_batch_items WHERE status = 'running'"
            ).fetchall()
        ]
        changed = conn.execute(
            """UPDATE image_batch_items
               SET status = 'unknown', error = ?, finished_at = ? WHERE status = 'running'""",
            ("gateway restarted while this image was running; provider outcome is unknown", now),
        ).rowcount
        for batch_id in batch_ids:
            _refresh_batch(conn, batch_id)
        conn.commit()
    return changed


def cancel_batch(batch_id: str) -> dict[str, Any]:
    now = _now_iso()
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        exists = conn.execute("SELECT 1 FROM image_batches WHERE batch_id = ?", (batch_id,)).fetchone()
        if exists is None:
            raise KeyError(batch_id)
        conn.execute(
            """UPDATE image_batch_items SET status = 'canceled', finished_at = ?
               WHERE batch_id = ? AND status = 'queued'""",
            (now, batch_id),
        )
        _refresh_batch(conn, batch_id)
        conn.commit()
    return get_batch(batch_id)


__all__ = [
    "cancel_batch",
    "claim_next_item",
    "complete_item",
    "create_batch",
    "fail_item",
    "get_batch",
    "list_batches",
    "mark_item_unknown",
    "process_next",
    "reconcile_inflight",
    "scale_estimate",
    "worker_loop",
]
