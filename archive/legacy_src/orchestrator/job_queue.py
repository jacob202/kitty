"""
SQLite-backed priority job queue.
Safe for concurrent use across multiple processes (WAL mode).
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta

from src.core.db_config import get_db_path

_DB_PATH = get_db_path("job_queue")
_lock = threading.Lock()


def _init_db():
    """Initialize the database schema once."""
    _DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(str(_DB_PATH)) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                status         TEXT    NOT NULL DEFAULT 'pending',
                priority       INTEGER NOT NULL DEFAULT 5,
                correlation_id TEXT,
                task_type      TEXT    NOT NULL,
                payload        TEXT    NOT NULL DEFAULT '{}',
                result         TEXT,
                error          TEXT,
                pid            INTEGER,
                created_at     TEXT    NOT NULL,
                updated_at     TEXT    NOT NULL
            )
        """)
        c.commit()


# Initialize on import
_init_db()


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()


def enqueue(
    task_type: str, payload: dict = None, priority: int = 5, correlation_id: str = None
) -> int:
    """Add a job. Lower priority number = higher priority. Returns job id."""
    now = datetime.now().isoformat()
    with _lock:
        with get_db() as c:
            cur = c.execute(
                "INSERT INTO jobs (task_type, payload, priority, correlation_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (task_type, json.dumps(payload or {}), priority, correlation_id, now, now),
            )
            c.commit()
            return cur.lastrowid


def dequeue(stale_after_seconds: int = 300) -> dict | None:
    """Claim the highest-priority pending job. Also reclaim stale running jobs. Returns None if queue is empty."""
    with _lock:
        with get_db() as c:
            if stale_after_seconds > 0:
                stale_threshold = (
                    datetime.now() - timedelta(seconds=stale_after_seconds)
                ).isoformat()
                c.execute(
                    "UPDATE jobs SET status='pending', updated_at=? "
                    "WHERE status='running' AND updated_at < ?",
                    (datetime.now().isoformat(), stale_threshold),
                )
                c.commit()

            row = c.execute(
                "SELECT id, task_type, payload, priority, correlation_id FROM jobs "
                "WHERE status = 'pending' ORDER BY priority ASC, id ASC LIMIT 1"
            ).fetchone()

            if not row:
                return None

            job_id = row[0]
            c.execute(
                "UPDATE jobs SET status='running', updated_at=? WHERE id=?",
                (datetime.now().isoformat(), job_id),
            )
            c.commit()

            return {
                "id": row[0],
                "task_type": row[1],
                "payload": json.loads(row[2]),
                "priority": row[3],
                "correlation_id": row[4],
            }


def update_status(job_id: int, status: str, result: str = None, error: str = None, pid: int = None):
    """Update a job's status after processing."""
    with _lock:
        with get_db() as c:
            if result is not None:
                if isinstance(result, str):
                    try:
                        json.loads(result)
                    except json.JSONDecodeError:
                        result = json.dumps(result)
                else:
                    result = json.dumps(result)
            if error is not None:
                if isinstance(error, str):
                    try:
                        json.loads(error)
                    except json.JSONDecodeError:
                        error = json.dumps(error)
                else:
                    error = json.dumps(error)
            c.execute(
                "UPDATE jobs SET status=?, result=?, error=?, pid=?, updated_at=? WHERE id=?",
                (status, result, error, pid, datetime.now().isoformat(), job_id),
            )
            c.commit()


def list_jobs(status: str = None, limit: int = 50) -> list[dict]:
    """List jobs, optionally filtered by status."""
    with get_db() as c:
        if status:
            rows = c.execute(
                "SELECT id, status, priority, task_type, correlation_id, created_at, updated_at, pid, error "
                "FROM jobs WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, status, priority, task_type, correlation_id, created_at, updated_at, pid, error "
                "FROM jobs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

        keys = [
            "id",
            "status",
            "priority",
            "task_type",
            "correlation_id",
            "created_at",
            "updated_at",
            "pid",
            "error",
        ]
        return [dict(zip(keys, r)) for r in rows]
