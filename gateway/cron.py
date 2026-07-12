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

The cron schedules live in `data/kitty/kitty.db` (table `cron_schedules`)
since the C3 consolidation. The legacy `data/cron_schedules.db` is
imported once on first `init_db()` if the destination table is empty.
The legacy DB is never deleted; rollback is a one-line change in
this file. See `docs/phases/PHASE_C3_PLAN.md` for the full sequence.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from typing import Awaitable, Callable, Optional

from gateway import db as kitty_db
from gateway.paths import DATA_DIR, KITTY_DB_FILE

logger = logging.getLogger("kitty.cron")

TABLE = "cron_schedules"
LEGACY_CRON_DB = DATA_DIR / "cron_schedules.db"
LEGACY_IMPORT_SETTING = "cron_legacy_imported"

_runner_task: asyncio.Task | None = None
_actions: dict[str, Callable[[], Awaitable[None]]] = {}


def _import_legacy_cron_once() -> None:
    """One-shot import from the legacy `cron_schedules.db` into kitty.db.

    Pattern matches `todo_store`, `chats_store`, `journal_store`,
    `buddy_store`:
      - If the destination `cron_schedules` table is non-empty, skip
        and mark the setting (the live data is the source of truth).
      - If the legacy DB does not exist, no-op.
      - If the legacy DB exists and destination is empty, copy rows
        verbatim, then mark the setting in `app_settings` with the
        outcome.
      - Never deletes the source file.
    """
    if not LEGACY_CRON_DB.exists():
        return

    with kitty_db.connect(KITTY_DB_FILE) as conn:
        already = conn.execute(
            "SELECT 1 FROM app_settings WHERE key = ?",
            (LEGACY_IMPORT_SETTING,),
        ).fetchone()
        if already is not None:
            return

        try:
            with sqlite3.connect(f"file:{LEGACY_CRON_DB}?mode=ro", uri=True) as legacy:
                legacy.row_factory = sqlite3.Row
                rows = legacy.execute(
                    "SELECT id, name, action, schedule_type, schedule_value, "
                    "metadata, enabled, last_run, created_at FROM schedules"
                ).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("Cron legacy import: legacy DB unreadable (%s)", exc)
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                (LEGACY_IMPORT_SETTING, f"skipped: legacy DB unreadable ({exc})"),
            )
            conn.commit()
            return

        dst_count = conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
        if dst_count > 0:
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                (LEGACY_IMPORT_SETTING, "skipped: destination non-empty"),
            )
            conn.commit()
            return

        for r in rows:
            conn.execute(
                f"INSERT OR IGNORE INTO {TABLE} "
                "(id, name, action, schedule_type, schedule_value, metadata, "
                "enabled, last_run, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    r["id"], r["name"], r["action"], r["schedule_type"],
                    r["schedule_value"], r["metadata"], r["enabled"],
                    r["last_run"], r["created_at"],
                ),
            )
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
            (LEGACY_IMPORT_SETTING, f"imported {len(rows)} row(s) from legacy"),
        )
        conn.commit()
        if rows:
            logger.info("Cron legacy import: %d row(s) imported from %s", len(rows), LEGACY_CRON_DB)


def init_db() -> None:
    """Apply the legacy import shim. Schema is owned by migration 012."""
    KITTY_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    _import_legacy_cron_once()


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

    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            f"INSERT INTO {TABLE} "
            "(id, name, action, schedule_type, schedule_value, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, name, action, schedule_type, schedule_value, json.dumps(metadata or {}), now),
        )
        conn.commit()

    logger.info("Cron scheduled: %s (%s %s)", name, schedule_type, schedule_value)
    start()
    return sid


def list_schedules() -> list[dict]:
    """List all schedules."""
    init_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM {TABLE} ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def remove(sid: str) -> bool:
    """Remove a schedule by ID."""
    init_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        cursor = conn.execute(f"DELETE FROM {TABLE} WHERE id = ?", (sid,))
        conn.commit()
        return cursor.rowcount > 0


def toggle(sid: str) -> bool | None:
    """Flip the enabled flag. Returns new state, or None if not found."""
    init_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            f"SELECT enabled FROM {TABLE} WHERE id = ?", (sid,)
        ).fetchone()
        if not row:
            return None
        new_val = 0 if row[0] else 1
        conn.execute(f"UPDATE {TABLE} SET enabled = ? WHERE id = ?", (new_val, sid))
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
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        cursor = conn.execute(
            f"""
            UPDATE {TABLE}
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
            logger.warning("Unparseable interval schedule %r for %s", s_value, s.get("id", "?"))
            return False

    if s_type == "daily":
        try:
            parts = s_value.split(":")
            target_h, target_m = int(parts[0]), int(parts[1])
            import datetime
            today_target = datetime.datetime.now().replace(
                hour=target_h, minute=target_m, second=0, microsecond=0
            ).timestamp()
            return now >= today_target and last_run < today_target
        except (ValueError, IndexError):
            logger.warning("Unparseable daily schedule %r for %s", s_value, s.get("id", "?"))
            return False

    if s_type == "once":
        try:
            import datetime
            target = datetime.datetime.fromisoformat(s_value).timestamp()
            return now >= target and last_run == 0
        except (ValueError, TypeError):
            logger.warning("Unparseable once schedule %r for %s", s_value, s.get("id", "?"))
            return False

    return False


def _update_last_run(sid: str, ts: float) -> None:
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(f"UPDATE {TABLE} SET last_run = ? WHERE id = ?", (ts, sid))
        conn.commit()
