"""Signal store — one append table for connector and system events (P1).

A signal is a timestamped event from a connector or internal system:
"mail received", "PR check failed", "monitor tripped", "nudge fired".
Connectors emit signals; consumers (triage, the state composer, the
brief) read them. A signal is never mutated except to be marked
processed.

Payloads carry summaries and pointers, not blobs — anything over
MAX_PAYLOAD_BYTES is rejected so the table cannot silently absorb
message bodies or documents.

Public API:
  emit(source, kind, payload=None, dedupe_key=None, ts=None) -> dict | None
      Append one signal. Returns the stored record, or None when
      dedupe_key already exists (a duplicate from a re-polling
      connector is expected behaviour, not an error).
  list_recent(limit=50, source=None) -> list[dict]
  list_unprocessed(limit=50) -> list[dict]
  list_since(ts, limit=50) -> list[dict]
  count_unprocessed() -> int
  mark_processed(signal_id) -> bool
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

logger = logging.getLogger("kitty.signal_store")

SIGNALS_DB_FILE = KITTY_DB_FILE
MAX_PAYLOAD_BYTES = 16_384


def init_db() -> None:
    """Apply pending migrations. Idempotent."""
    kitty_db.migrate(db_file=SIGNALS_DB_FILE)


def emit(
    *,
    source: str,
    kind: str,
    payload: dict | None = None,
    dedupe_key: str | None = None,
    ts: float | None = None,
) -> dict | None:
    """Append one signal. Returns the record, or None on a dedupe hit."""
    if not source or not source.strip():
        raise ValueError("signal source is required")
    if not kind or not kind.strip():
        raise ValueError("signal kind is required")
    payload = payload or {}
    payload_json = json.dumps(payload)
    payload_size = len(payload_json.encode("utf-8"))
    if payload_size > MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"signal payload is {payload_size} bytes, max {MAX_PAYLOAD_BYTES} — "
            "store a pointer, not the content"
        )
    signal_ts = time.time() if ts is None else float(ts)
    init_db()
    with kitty_db.connect(SIGNALS_DB_FILE) as conn:
        cursor = conn.execute(
            """
            INSERT INTO signals (ts, source, kind, payload, dedupe_key)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(dedupe_key) DO NOTHING
            """,
            (signal_ts, source, kind, payload_json, dedupe_key),
        )
        conn.commit()
        if cursor.rowcount == 0:
            logger.debug("signal deduped: %s/%s key=%s", source, kind, dedupe_key)
            return None
        return {
            "id": cursor.lastrowid,
            "ts": signal_ts,
            "source": source,
            "kind": kind,
            "payload": payload,
            "dedupe_key": dedupe_key,
            "processed_at": None,
        }


def list_recent(limit: int = 50, source: str | None = None) -> list[dict]:
    """Return signals, newest first. Optional source filter."""
    init_db()
    with kitty_db.connect(SIGNALS_DB_FILE) as conn:
        if source is None:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM signals ORDER BY ts DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM signals WHERE source = ? "
                "ORDER BY ts DESC, id DESC LIMIT ?",
                (source, limit),
            ).fetchall()
    return [_row_to_signal(r) for r in rows]


def list_unprocessed(limit: int = 50) -> list[dict]:
    """Return signals not yet marked processed, oldest first."""
    init_db()
    with kitty_db.connect(SIGNALS_DB_FILE) as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM signals WHERE processed_at IS NULL "
            "ORDER BY ts ASC, id ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_signal(r) for r in rows]


def list_since(ts: float, limit: int = 50) -> list[dict]:
    """Return signals with ts strictly after `ts`, newest first."""
    init_db()
    with kitty_db.connect(SIGNALS_DB_FILE) as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM signals WHERE ts > ? "
            "ORDER BY ts DESC, id DESC LIMIT ?",
            (float(ts), limit),
        ).fetchall()
    return [_row_to_signal(r) for r in rows]


def count_unprocessed() -> int:
    init_db()
    with kitty_db.connect(SIGNALS_DB_FILE) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM signals WHERE processed_at IS NULL"
        ).fetchone()[0]


def mark_processed(signal_id: int) -> bool:
    """Mark one signal processed. True if a row changed."""
    init_db()
    with kitty_db.connect(SIGNALS_DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE signals SET processed_at = ? WHERE id = ? AND processed_at IS NULL",
            (time.time(), signal_id),
        )
        conn.commit()
        return cursor.rowcount > 0


_COLUMNS = "id, ts, source, kind, payload, dedupe_key, processed_at, created_at"


def _row_to_signal(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "ts": row["ts"],
        "source": row["source"],
        "kind": row["kind"],
        "payload": json.loads(row["payload"]),
        "dedupe_key": row["dedupe_key"],
        "processed_at": row["processed_at"],
        "created_at": row["created_at"],
    }
