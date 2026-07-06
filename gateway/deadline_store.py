"""Deadline store — watched deadlines and escalation log (P7, docs/packets/017).

Public API:
  upsert(deadline: dict) -> dict
  get(deadline_id: int) -> dict | None
  list_open(status: str | None = None) -> list[dict]
  list_needs_jacob() -> list[dict]
  close(deadline_id: int) -> dict
  mark_pushed(deadline_id: int) -> None
  checkpoint_due(deadline: dict, now: date) -> str | None
  record_escalation(deadline_id: int, checkpoint: str) -> None
  escalation_already_sent(deadline_id: int, checkpoint: str) -> bool
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from datetime import date, datetime
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

DEADLINES_DB_FILE = KITTY_DB_FILE

_DEADLINE_COLUMNS = (
    "id, project_id, source, source_id, due_date, obligation, amount, currency, "
    "confidence, status, dedupe_key, created_at, updated_at, pushed_at"
)


class DeadlineError(RuntimeError):
    """Base for deadline-store errors."""


class DeadlineNotFound(DeadlineError):
    """No deadline row with that id."""


class DuplicateDeadline(DeadlineError):
    """Dedupe key collision."""


def init_db() -> None:
    kitty_db.migrate(db_file=DEADLINES_DB_FILE)


def _now_ts() -> float:
    return time.time()


def _make_dedupe_key(source: str, due_date: str, obligation: str) -> str:
    normalized = f"{source}|{due_date}|{obligation.strip().lower()}"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"deadline:{source.split(':')[0]}:{digest}"


def upsert(deadline: dict[str, Any]) -> dict[str, Any]:
    """Insert or update a deadline by dedupe_key."""
    required = {"project_id", "source", "due_date", "obligation"}
    missing = required - set(deadline.keys())
    if missing:
        raise DeadlineError(f"deadline missing required fields: {sorted(missing)}")

    source = str(deadline["source"])
    due_date = str(deadline["due_date"])
    obligation = str(deadline["obligation"])
    dedupe_key = str(deadline["dedupe_key"]) if "dedupe_key" in deadline else _make_dedupe_key(source, due_date, obligation)

    confidence = str(deadline.get("confidence", "needs_jacob")).lower()
    if confidence not in {"high", "medium", "low", "needs_jacob"}:
        confidence = "needs_jacob"

    status = str(deadline.get("status", "open")).lower()
    if status not in {"open", "closed", "needs_jacob"}:
        status = "open"
    if confidence == "needs_jacob":
        status = "needs_jacob"

    amount = deadline.get("amount")
    currency = deadline.get("currency")
    source_id = deadline.get("source_id")

    init_db()
    now = _now_ts()
    with kitty_db.connect(DEADLINES_DB_FILE) as conn:
        cursor = conn.execute(
            """
            INSERT INTO deadlines (
                project_id, source, source_id, due_date, obligation, amount, currency,
                confidence, status, dedupe_key, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dedupe_key) DO UPDATE SET
                source_id = excluded.source_id,
                due_date = excluded.due_date,
                obligation = excluded.obligation,
                amount = excluded.amount,
                currency = excluded.currency,
                confidence = excluded.confidence,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                int(deadline["project_id"]),
                source,
                source_id,
                due_date,
                str(deadline["obligation"]),
                amount,
                currency,
                confidence,
                status,
                dedupe_key,
                now,
                now,
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid
        if row_id is None or row_id == 0:
            existing = conn.execute(
                "SELECT id FROM deadlines WHERE dedupe_key = ?", (dedupe_key,)
            ).fetchone()
            row_id = existing["id"] if existing else None
        if row_id is None:
            raise DuplicateDeadline(f"could not resolve deadline for dedupe_key {dedupe_key!r}")
    return _require(row_id)


def get(deadline_id: int) -> dict[str, Any] | None:
    init_db()
    with kitty_db.connect(DEADLINES_DB_FILE) as conn:
        row = conn.execute(
            f"SELECT {_DEADLINE_COLUMNS} FROM deadlines WHERE id = ?", (deadline_id,)
        ).fetchone()
    return _row_to_deadline(row) if row else None


def list_open(status: str | None = None) -> list[dict[str, Any]]:
    init_db()
    target_status = status or "open"
    with kitty_db.connect(DEADLINES_DB_FILE) as conn:
        rows = conn.execute(
            f"SELECT {_DEADLINE_COLUMNS} FROM deadlines WHERE status = ? "
            "ORDER BY due_date ASC, created_at ASC",
            (target_status,),
        ).fetchall()
    return [_row_to_deadline(r) for r in rows]


def list_needs_jacob() -> list[dict[str, Any]]:
    return list_open(status="needs_jacob")


def close(deadline_id: int) -> dict[str, Any]:
    init_db()
    _require(deadline_id)
    with kitty_db.connect(DEADLINES_DB_FILE) as conn:
        conn.execute(
            "UPDATE deadlines SET status = 'closed', updated_at = ? WHERE id = ?",
            (_now_ts(), deadline_id),
        )
        conn.commit()
    return _require(deadline_id)


def mark_pushed(deadline_id: int) -> None:
    init_db()
    with kitty_db.connect(DEADLINES_DB_FILE) as conn:
        conn.execute(
            "UPDATE deadlines SET pushed_at = ? WHERE id = ?",
            (_now_ts(), deadline_id),
        )
        conn.commit()


def checkpoint_due(deadline: dict[str, Any], now: date | None = None) -> str | None:
    """Return the escalation checkpoint that should fire for `deadline` today.

    Returns one of T-7d, T-3d, T-1d, day-of, or None.
    """
    if deadline.get("status") != "open":
        return None

    today = now if now is not None else date.today()
    try:
        due = datetime.strptime(str(deadline["due_date"]), "%Y-%m-%d").date()
    except ValueError:
        return None

    delta = (due - today).days
    checkpoints = {
        7: "T-7d",
        3: "T-3d",
        1: "T-1d",
        0: "day-of",
    }
    return checkpoints.get(delta)


def record_escalation(deadline_id: int, checkpoint: str) -> None:
    init_db()
    dedupe_key = f"esc:{deadline_id}:{checkpoint}"
    now = _now_ts()
    with kitty_db.connect(DEADLINES_DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO deadline_escalations (deadline_id, checkpoint, pushed_at, dedupe_key)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(dedupe_key) DO NOTHING
            """,
            (deadline_id, checkpoint, now, dedupe_key),
        )
        conn.commit()


def escalation_already_sent(deadline_id: int, checkpoint: str) -> bool:
    init_db()
    with kitty_db.connect(DEADLINES_DB_FILE) as conn:
        row = conn.execute(
            "SELECT 1 FROM deadline_escalations WHERE deadline_id = ? AND checkpoint = ?",
            (deadline_id, checkpoint),
        ).fetchone()
    return row is not None


def _require(deadline_id: int) -> dict[str, Any]:
    deadline = get(deadline_id)
    if deadline is None:
        raise DeadlineNotFound(f"no deadline with id {deadline_id}")
    return deadline


def _row_to_deadline(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "source": row["source"],
        "source_id": row["source_id"],
        "due_date": row["due_date"],
        "obligation": row["obligation"],
        "amount": row["amount"],
        "currency": row["currency"],
        "confidence": row["confidence"],
        "status": row["status"],
        "dedupe_key": row["dedupe_key"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "pushed_at": row["pushed_at"],
    }
