"""Cron Scheduler — runtime trigger system for recurring tasks.

Replaces launchd plists with runtime-managed schedules. Supports:
- Time-based: daily at 7am, every Monday, etc.
- Interval-based: every N minutes
- One-shot: fire once at a specific time

Public API:
  schedule(name, action, cron_expr, metadata) -> str
  list_schedules() -> list[dict]
  remove(name) -> bool
  start() -> start background runner
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from typing import Awaitable, Callable, Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.cron")

CRON_DB = DATA_DIR / "cron_schedules.db"

_runner_task: asyncio.Task | None = None
_actions: dict[str, Callable[[], Awaitable[None]]] = {}


def init_db() -> None:
    CRON_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(CRON_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                action TEXT NOT NULL,
                schedule_type TEXT NOT NULL,  -- daily, interval, once
                schedule_value TEXT NOT NULL,  -- "07:00", "30" (minutes), "2026-05-14T09:00"
                metadata TEXT DEFAULT '{}',
                enabled INTEGER DEFAULT 1,
                last_run REAL DEFAULT 0,
                created_at REAL
            )
        """)
        conn.commit()


def schedule(
    name: str,
    action: str,
    schedule_type: str = "daily",
    schedule_value: str = "07:00",
    metadata: Optional[dict] = None,
) -> str:
    """Schedule a recurring task. Returns schedule_id."""
    init_db()
    sid = str(uuid.uuid4())[:8]
    now = time.time()

    with sqlite3.connect(CRON_DB) as conn:
        conn.execute(
            "INSERT INTO schedules (id, name, action, schedule_type, schedule_value, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, name, action, schedule_type, schedule_value, json.dumps(metadata or {}), now),
        )
        conn.commit()

    logger.info("Cron scheduled: %s (%s %s)", name, schedule_type, schedule_value)

    # Start runner if not running
    start()
    return sid


def list_schedules() -> list[dict]:
    """List all schedules."""
    init_db()
    with sqlite3.connect(CRON_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM schedules ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def remove(sid: str) -> bool:
    """Remove a schedule by ID."""
    init_db()
    with sqlite3.connect(CRON_DB) as conn:
        cursor = conn.execute("DELETE FROM schedules WHERE id = ?", (sid,))
        conn.commit()
        return cursor.rowcount > 0


def toggle(sid: str) -> bool | None:
    """Flip the enabled flag. Returns new state, or None if not found."""
    init_db()
    with sqlite3.connect(CRON_DB) as conn:
        row = conn.execute("SELECT enabled FROM schedules WHERE id = ?", (sid,)).fetchone()
        if not row:
            return None
        new_val = 0 if row[0] else 1
        conn.execute("UPDATE schedules SET enabled = ? WHERE id = ?", (new_val, sid))
        conn.commit()
    return bool(new_val)


def update(
    sid: str,
    name: str,
    action: str,
    schedule_type: str,
    schedule_value: str,
    metadata: Optional[dict] = None,
) -> bool:
    """Update a schedule by ID. Returns False when the schedule is missing."""
    init_db()
    with sqlite3.connect(CRON_DB) as conn:
        cursor = conn.execute(
            """
            UPDATE schedules
               SET name = ?, action = ?, schedule_type = ?, schedule_value = ?, metadata = ?
             WHERE id = ?
            """,
            (name, action, schedule_type, schedule_value, json.dumps(metadata or {}), sid),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_actions() -> list[str]:
    """Return names of all registered action functions."""
    return sorted(_actions.keys())


def register_action(name: str, fn: Callable[[], Awaitable[None]]) -> None:
    """Register an action function that can be triggered by schedules."""
    _actions[name] = fn


def start() -> None:
    """Start the background cron runner."""
    global _runner_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # no event loop, skip in sync contexts
    if _runner_task is None or _runner_task.done():
        _runner_task = loop.create_task(_runner())


async def _runner() -> None:
    """Background loop that checks schedules and fires actions."""
    logger.info("Cron runner started")

    while True:
        try:
            now = time.time()
            schedules_list = list_schedules()

            for s in schedules_list:
                if not s.get("enabled"):
                    continue

                if _should_fire(s, now):
                    action_name = s.get("action", "")
                    if action_name in _actions:
                        try:
                            await _actions[action_name]()
                            logger.info("Cron action fired: %s", action_name)
                        except Exception as e:
                            logger.error("Cron action %s failed: %s", action_name, e)

                    _update_last_run(s["id"], now)

        except asyncio.CancelledError:
            logger.info("Cron runner stopped")
            return
        except Exception:
            logger.exception("Cron runner error")

        await asyncio.sleep(30)  # check every 30 seconds


def _should_fire(s: dict, now: float) -> bool:
    """Check if a schedule should fire now."""
    last_run = s.get("last_run", 0)
    s_type = s.get("schedule_type", "")
    s_value = s.get("schedule_value", "")

    if s_type == "interval":
        try:
            interval = int(s_value) * 60
            return (now - last_run) >= interval
        except ValueError:
            return False

    if s_type == "daily":
        # Parse HH:MM and check if we've passed it since last run
        try:
            parts = s_value.split(":")
            target_h, target_m = int(parts[0]), int(parts[1])
            import datetime
            today_target = datetime.datetime.now().replace(
                hour=target_h, minute=target_m, second=0, microsecond=0
            ).timestamp()
            return now >= today_target and last_run < today_target
        except (ValueError, IndexError):
            return False

    if s_type == "once":
        try:
            import datetime
            target = datetime.datetime.fromisoformat(s_value).timestamp()
            return now >= target and last_run == 0
        except (ValueError, TypeError):
            return False

    return False


def _update_last_run(sid: str, ts: float) -> None:
    with sqlite3.connect(CRON_DB) as conn:
        conn.execute("UPDATE schedules SET last_run = ? WHERE id = ?", (ts, sid))
        conn.commit()
