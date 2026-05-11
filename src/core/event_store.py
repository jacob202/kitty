"""
Event store — append-only, SQLite-backed, globally sequenced.
Use append_event() from canonical_logger instead of calling directly.
Thread-safe via module-level lock.
"""

import json
import sqlite3
import threading
from datetime import datetime

from src.core.db_config import get_db_path

_EVENT_DB = get_db_path("event_store")
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    _EVENT_DB.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(str(_EVENT_DB), check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            seq_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            schema         TEXT    NOT NULL,
            correlation_id TEXT,
            timestamp      TEXT    NOT NULL,
            payload        TEXT    NOT NULL
        )
    """)
    c.commit()
    return c


def append_event(schema: str, payload: dict, correlation_id: str = None) -> int:
    """Write an event, return its globally unique sequence number."""
    with _lock:
        c = _conn()
        try:
            cur = c.execute(
                "INSERT INTO events (schema, correlation_id, timestamp, payload) VALUES (?, ?, ?, ?)",
                (schema, correlation_id, datetime.now().isoformat(), json.dumps(payload)),
            )
            c.commit()
            seq_id = cur.lastrowid
            return seq_id
        finally:
            c.close()


def replay_range(start_seq: int, end_seq: int = None) -> list[dict]:
    """Return events from start_seq to end_seq (inclusive). Omit end_seq for open range."""
    with _lock:
        c = _conn()
        try:
            if end_seq is not None:
                rows = c.execute(
                    "SELECT seq_id, schema, correlation_id, timestamp, payload "
                    "FROM events WHERE seq_id BETWEEN ? AND ? ORDER BY seq_id",
                    (start_seq, end_seq),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT seq_id, schema, correlation_id, timestamp, payload "
                    "FROM events WHERE seq_id >= ? ORDER BY seq_id",
                    (start_seq,),
                ).fetchall()
            return [
                {
                    "seq_id": r[0],
                    "schema": r[1],
                    "correlation_id": r[2],
                    "timestamp": r[3],
                    "payload": json.loads(r[4]),
                }
                for r in rows
            ]
        finally:
            c.close()


def latest_seq() -> int:
    """Return the highest seq_id written so far, or 0 if empty."""
    with _lock:
        c = _conn()
        try:
            row = c.execute("SELECT MAX(seq_id) FROM events").fetchone()
            return row[0] or 0
        finally:
            c.close()
