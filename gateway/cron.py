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
import inspect
import json
import logging
import sqlite3
import time
import uuid
from typing import Any, Awaitable, Callable, Optional

from gateway import automation_actions, automation_runs
from gateway import db as kitty_db
from gateway.paths import DATA_DIR, KITTY_DB_FILE

logger = logging.getLogger("kitty.cron")

TABLE = "cron_schedules"
LEGACY_CRON_DB = DATA_DIR / "cron_schedules.db"
LEGACY_IMPORT_SETTING = "cron_legacy_imported"

_runner_task: asyncio.Task | None = None


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
        existing = conn.execute(
            f"SELECT id FROM {TABLE} "
            "WHERE action = ? AND schedule_type = ? AND schedule_value = ? AND metadata = ? "
            "LIMIT 1",
            (action, schedule_type, schedule_value, json.dumps(metadata or {})),
        ).fetchone()
        if existing:
            logger.warning(
                "Cron schedule for action %r (%s %s) already exists (id=%s); skipping duplicate",
                action,
                schedule_type,
                schedule_value,
                existing[0],
            )
            return existing[0]
        conn.execute(
            f"INSERT INTO {TABLE} "
            "(id, name, action, schedule_type, schedule_value, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, name, action, schedule_type, schedule_value, json.dumps(metadata or {}), now),
        )
        conn.commit()

    logger.info("Cron scheduled: %s (%s %s)", name, schedule_type, schedule_value)
    return sid


def ensure_schedule(
    name: str,
    action: str,
    schedule_type: str = "daily",
    schedule_value: str = "07:00",
    metadata: Optional[dict] = None,
) -> str:
    """Create or update one stable schedule identity keyed by ``name``.

    Reconfiguration preserves the existing row (including enabled/last_run) and
    removes accidental duplicate rows with the same automation name.
    """
    init_db()
    metadata_json = json.dumps(metadata or {})
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        rows = conn.execute(
            f"SELECT id FROM {TABLE} WHERE name = ? ORDER BY created_at, id",
            (name,),
        ).fetchall()
        if rows:
            sid = str(rows[0][0])
            conn.execute(
                f"UPDATE {TABLE} SET action = ?, schedule_type = ?, schedule_value = ?, metadata = ? "
                "WHERE id = ?",
                (action, schedule_type, schedule_value, metadata_json, sid),
            )
            for duplicate in rows[1:]:
                conn.execute(f"DELETE FROM {TABLE} WHERE id = ?", (duplicate[0],))
        else:
            sid = str(uuid.uuid4())[:8]
            conn.execute(
                f"INSERT INTO {TABLE} "
                "(id, name, action, schedule_type, schedule_value, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sid, name, action, schedule_type, schedule_value, metadata_json, time.time()),
            )
        conn.commit()
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
    """Return names from the canonical Automation action registry."""
    return automation_actions.get_actions()


def register_action(
    name: str,
    fn: Callable[[], Any | Awaitable[Any]],
    *,
    tier: str = "T0",
    capability: str | None = None,
) -> None:
    """Compatibility wrapper for no-payload cron actions."""

    async def _adapter(_payload: dict[str, Any]) -> Any:
        result = fn()
        if inspect.isawaitable(result):
            return await result
        return result

    automation_actions.register_action(
        name,
        _adapter,
        policy=automation_actions.ActionPolicy(capability=capability or name, tier=tier),
    )


def start() -> asyncio.Task | None:
    """Start the background cron runner with restart reconciliation."""
    global _runner_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("Cron start skipped: no running event loop")
        return None
    if _runner_task is None or _runner_task.done():
        try:
            interrupted = automation_runs.reconcile_interrupted_runs()
        except Exception:
            logger.exception("Cron start blocked: automation run evidence unavailable")
            return None
        if interrupted:
            logger.warning("Reconciled %d interrupted automation run(s)", interrupted)
        _runner_task = loop.create_task(_runner())
    return _runner_task


async def stop() -> None:
    """Stop the cron runner and clear its in-process task handle."""
    global _runner_task
    task = _runner_task
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _runner_task = None


async def _run_due_once(*, now: float | None = None) -> None:
    """Claim and execute each due schedule at most once for this pass."""
    claim_at = time.time() if now is None else float(now)
    for schedule_row in list_schedules():
        due_at = _due_at(schedule_row, claim_at)
        if due_at is None:
            continue
        cursor_at = claim_at if schedule_row.get("schedule_type") == "interval" else due_at
        run = automation_runs.claim_scheduled_run(
            schedule_row, due_at=due_at, claim_at=claim_at, cursor_at=cursor_at
        )
        if run is None:
            continue
        action_name = str(schedule_row.get("action") or "")
        await automation_actions.run_action(
            action_name,
            trigger_kind="time",
            automation_id=str(schedule_row["id"]),
            trigger_ref=str(schedule_row["id"]),
            schedule_id=str(schedule_row["id"]),
            run_id=str(run["id"]),
            policy_scope_type="automation",
            policy_scope_id=str(schedule_row["id"]),
        )


async def _runner() -> None:
    """Background loop that checks schedules and fires actions."""
    logger.info("Cron runner started")
    from gateway.automation_supervisor import supervisor

    while True:
        try:
            supervisor.heartbeat("cron")
            await _run_due_once()
        except asyncio.CancelledError:
            logger.info("Cron runner stopped")
            return
        except Exception:
            logger.exception("Cron runner error")
        await asyncio.sleep(30)


def _should_fire(s: dict, now: float) -> bool:
    """Check if a schedule should fire now."""
    return _due_at(s, now) is not None


def _due_at(s: dict, now: float) -> float | None:
    """Return the due occurrence timestamp, or ``None`` when not due."""
    last_run = s.get("last_run", 0)
    s_type = s.get("schedule_type", "")
    s_value = s.get("schedule_value", "")

    if s_type == "interval":
        try:
            interval = float(s_value) * 60
            if interval > 0 and (now - last_run) >= interval:
                return now
            return None
        except (TypeError, ValueError):
            logger.warning("Cron interval schedule invalid: %s", s_value)
            return None

    if s_type == "daily":
        try:
            import datetime
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

            parts = s_value.split(":")
            target_h, target_m = int(parts[0]), int(parts[1])
            raw_metadata = s.get("metadata") or {}
            metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata
            timezone_name = metadata.get("timezone") if isinstance(metadata, dict) else None
            if timezone_name:
                try:
                    zone = ZoneInfo(str(timezone_name))
                except ZoneInfoNotFoundError:
                    logger.warning("Cron daily schedule has unknown timezone: %s", timezone_name)
                    return None
                local_now = datetime.datetime.fromtimestamp(now, zone)
            else:
                local_now = datetime.datetime.fromtimestamp(now)
            today_target = local_now.replace(
                hour=target_h, minute=target_m, second=0, microsecond=0
            ).timestamp()
            if now >= today_target and last_run < today_target:
                return today_target
            return None
        except (TypeError, ValueError, IndexError, json.JSONDecodeError):
            logger.warning("Cron daily schedule invalid: %s", s_value)
            return None

    if s_type == "once":
        try:
            import datetime
            target = datetime.datetime.fromisoformat(s_value).timestamp()
            if now >= target and last_run == 0:
                return target
            return None
        except (ValueError, TypeError):
            logger.warning("Cron once schedule invalid: %s", s_value)
            return None

    return None


def explain_schedule(s: dict[str, Any], *, now: float | None = None) -> dict[str, Any]:
    """Explain the schedule-level reason an automation has or has not run."""
    current = time.time() if now is None else float(now)
    if not s.get("enabled"):
        return {"state": "disabled", "reason": "schedule is disabled"}
    due_at = _due_at(s, current)
    if due_at is None:
        return {"state": "not_due", "reason": "next occurrence is not due yet"}
    return {"state": "due", "reason": "scheduled occurrence is due", "due_at": due_at}
