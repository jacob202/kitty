"""
Circuit breaker decorator backed by SQLite WAL mode.

States
------
closed    — normal operation; failures are counted within the sliding window.
open      — failure threshold exceeded; calls are rejected immediately.
half_open — cooldown elapsed; one probe call is allowed through to test recovery.
"""

import functools
import sqlite3
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from src.core.db_config import get_db_path

P = ParamSpec("P")
R = TypeVar("R")

_DB_PATH = get_db_path("circuit_breaker")

_FAILURE_THRESHOLD = 5
_WINDOW_SECONDS = 60.0
_RETRY_SECONDS = 30.0

_STATE_CLOSED = "closed"
_STATE_OPEN = "open"
_STATE_HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    pass


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=5.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS circuits (
            name         TEXT PRIMARY KEY,
            failures     INT  NOT NULL DEFAULT 0,
            last_failure REAL NOT NULL DEFAULT 0.0,
            state        TEXT NOT NULL DEFAULT 'closed'
        )
        """
    )
    conn.commit()
    return conn


def _get_or_create(conn: sqlite3.Connection, name: str) -> tuple[int, float, str]:
    conn.execute(
        "INSERT OR IGNORE INTO circuits (name, failures, last_failure, state) VALUES (?, 0, 0.0, 'closed')",
        (name,),
    )
    row = conn.execute(
        "SELECT failures, last_failure, state FROM circuits WHERE name = ?",
        (name,),
    ).fetchone()
    return row[0], row[1], row[2]


def _resolve_state(failures: int, last_failure: float, state: str) -> str:
    now = time.time()
    if state == _STATE_OPEN:
        if now - last_failure >= _RETRY_SECONDS:
            return _STATE_HALF_OPEN
        return _STATE_OPEN
    if failures >= _FAILURE_THRESHOLD and (now - last_failure) <= _WINDOW_SECONDS:
        return _STATE_OPEN
    return _STATE_CLOSED


def _record_success(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "UPDATE circuits SET failures = 0, state = 'closed' WHERE name = ?",
        (name,),
    )
    conn.commit()


def _record_failure(conn: sqlite3.Connection, name: str) -> None:
    now = time.time()
    conn.execute(
        """
        UPDATE circuits
           SET failures     = failures + 1,
               last_failure = ?,
               state        = CASE
                                  WHEN failures + 1 >= ? THEN 'open'
                                  ELSE state
                              END
         WHERE name = ?
        """,
        (now, _FAILURE_THRESHOLD, name),
    )
    conn.commit()


def circuit_breaker(name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator factory that applies a named circuit breaker to a function."""

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            conn = _connect()
            try:
                failures, last_failure, raw_state = _get_or_create(conn, name)
                effective_state = _resolve_state(failures, last_failure, raw_state)

                if effective_state == _STATE_OPEN:
                    raise CircuitOpenError(
                        f"Circuit '{name}' is open — rejecting call to {fn.__qualname__}"
                    )

                if effective_state == _STATE_HALF_OPEN:
                    conn.execute(
                        "UPDATE circuits SET state = 'half_open' WHERE name = ?",
                        (name,),
                    )
                    conn.commit()

                try:
                    result = fn(*args, **kwargs)
                    _record_success(conn, name)
                    return result
                except Exception as exc:
                    _record_failure(conn, name)
                    raise exc
            finally:
                conn.close()

        return wrapper

    return decorator
