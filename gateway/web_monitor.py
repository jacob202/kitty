"""Web Monitor — persistent URL polling with change detection and keyword matching.

Public API:
  add_watch(url, label, keywords, interval_minutes) -> watch_id
  remove_watch(watch_id) -> bool
  check_now(watch_id) -> dict
  list_watches() -> list[dict]

Storage: SQLite in data/web_monitors.db
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sqlite3
import time
import uuid
from typing import Optional

import httpx

from gateway.db import connect as db_connect
from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.web_monitor")

MONITOR_DB = DATA_DIR / "web_monitors.db"
CHECK_INTERVAL_SECONDS: int = 300  # 5 minutes between global poll cycles

# check_due() sweeps every watch sequentially, each with an HTTP round trip
# plus a fixed inter-watch delay, so one pass can run well past the cron
# interval that triggers it. Nothing stops that same sweep from being
# reachable a second way — a manual POST /automations/actions/monitors.check/run
# has no equivalent to cron's atomic per-schedule claim. A held lock means a
# second, overlapping sweep attempt skips instead of racing the first one on
# the same watches' last_hash/last_checked reads-then-writes.
_sweep_lock = asyncio.Lock()



def init_db() -> None:
    MONITOR_DB.parent.mkdir(parents=True, exist_ok=True)
    with db_connect(MONITOR_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watches (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                label TEXT NOT NULL,
                keywords TEXT DEFAULT '[]',
                interval_minutes INTEGER DEFAULT 30,
                last_hash TEXT DEFAULT '',
                last_checked REAL DEFAULT 0,
                last_result TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                created_at REAL
            )
        """)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(watches)").fetchall()}
        if "last_keyword_matched" not in cols:
            conn.execute("ALTER TABLE watches ADD COLUMN last_keyword_matched INTEGER DEFAULT 0")
        conn.commit()


def add_watch(
    url: str,
    label: str = "",
    keywords: Optional[list[str]] = None,
    interval_minutes: int = 30,
) -> str:
    """Add a URL to monitor. Returns watch_id."""
    init_db()
    watch_id = str(uuid.uuid4())[:8]
    now = time.time()

    with db_connect(MONITOR_DB) as conn:
        conn.execute(
            "INSERT INTO watches (id, url, label, keywords, interval_minutes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (watch_id, url, label or url, json.dumps(keywords or []), interval_minutes, now),
        )
        conn.commit()

    logger.info("Web watch added: %s -> %s", watch_id, url[:80])

    return watch_id


def remove_watch(watch_id: str) -> bool:
    """Remove a watch by ID."""
    init_db()
    with db_connect(MONITOR_DB) as conn:
        cursor = conn.execute("DELETE FROM watches WHERE id = ?", (watch_id,))
        conn.commit()
        return cursor.rowcount > 0



def set_watch_enabled(watch_id: str, enabled: bool) -> bool | None:
    """Set one watch enabled state. Returns the new state, or None if missing."""
    init_db()
    with db_connect(MONITOR_DB) as conn:
        row = conn.execute("SELECT 1 FROM watches WHERE id = ?", (watch_id,)).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE watches SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, watch_id),
        )
        conn.commit()
    return enabled

def list_watches() -> list[dict]:
    """List all watches."""
    init_db()
    with db_connect(MONITOR_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM watches ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


async def check_now(watch_id: str) -> dict:
    """Force-check a single watch immediately."""
    init_db()
    with db_connect(MONITOR_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM watches WHERE id = ?", (watch_id,)).fetchone()

    if not row:
        return {"error": "Watch not found"}

    watch = _row_to_dict(row)
    result = await _check_watch(watch)

    await _handle_watch_result(watch, result)
    return result


async def check_due() -> dict:
    """Check enabled watches whose per-watch interval is due once.

    Timing ownership belongs to the canonical cron/Automation lifecycle; this
    function retains web-monitor domain semantics and per-watch cadence.

    A sweep already in progress holds `_sweep_lock` for its full duration, so
    an overlapping call skips rather than racing it over the same watches'
    stored state. Any watch still due when the running sweep finishes gets
    picked up on the next scheduled tick.
    """
    if _sweep_lock.locked():
        logger.info("Web monitor sweep already in progress; skipping overlapping trigger")
        return {"checked": 0, "changed": 0, "failed": 0, "skipped": True}

    async with _sweep_lock:
        checked = 0
        changed = 0
        failed = 0
        now = time.time()

        for watch in [w for w in list_watches() if w.get("enabled")]:
            interval = float(watch.get("interval_minutes", 30)) * 60
            last_checked = float(watch.get("last_checked", 0) or 0)
            if interval <= 0 or now - last_checked < interval:
                continue

            try:
                result = await _check_watch(watch)
                checked += 1
                if result.get("changed"):
                    changed += 1
                if result.get("status") == "error":
                    failed += 1
                await _handle_watch_result(watch, result)
            except Exception:
                failed += 1
                logger.exception("Watch check failed for %s", watch.get("id"))

            await asyncio.sleep(2)

        return {"checked": checked, "changed": changed, "failed": failed}


async def _check_watch(watch: dict) -> dict:
    """Check a single watch for changes. Returns result dict."""
    url = watch["url"]
    keywords = json.loads(watch.get("keywords", "[]")) if isinstance(watch.get("keywords"), str) else (watch.get("keywords") or [])
    old_hash = watch.get("last_hash", "")
    was_keyword_matched = bool(watch.get("last_keyword_matched", False))

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Kitty/1.0 Web Monitor (personal use)"
            })
            if resp.status_code != 200:
                return {"status": "error", "code": resp.status_code, "changed": False}

            text = resp.text
            new_hash = hashlib.sha256(text.encode()).hexdigest()
            lower = text.lower()
            matches = [k for k in keywords if k.lower() in lower] if keywords else []
            now_matched = bool(matches)

            # Update last checked time, hash, and keyword-match state.
            now = time.time()
            with db_connect(MONITOR_DB) as conn:
                conn.execute(
                    "UPDATE watches SET last_hash = ?, last_checked = ?, last_result = ?, "
                    "last_keyword_matched = ? WHERE id = ?",
                    (new_hash, now, text[:5000], int(now_matched), watch["id"]),
                )
                conn.commit()

            if keywords:
                # A keyword watch's condition is "this keyword is present". It
                # must fire only on the false -> true transition: never on
                # every poll while content keeps changing but the keyword
                # stays matched (that was spamming a fresh notification per
                # poll), and never on the very first check before any
                # baseline exists (that was a false positive on creation).
                content_changed = old_hash != "" and now_matched and not was_keyword_matched
            else:
                content_changed = new_hash != old_hash and old_hash != ""

            result = {
                "watch_id": watch["id"],
                "url": url,
                "changed": content_changed,
                "hash": new_hash[:16],
                "content_length": len(text),
            }
            if matches:
                result["keyword_matches"] = matches

            return result

    except Exception as e:
        logger.error("Watch check failed for %s: %s", url, e)
        return {"status": "error", "error": str(e), "changed": False}


async def _handle_watch_result(watch: dict, result: dict) -> None:
    """Record monitor truth, emitting a signal before any notification action."""
    from gateway import automation_actions, automation_runs

    automation_id = f"web_monitor:{watch.get('id')}"
    if result.get("status") == "error":
        run = automation_runs.begin_run(
            automation_id=automation_id,
            action="web_monitor.notify",
            trigger_kind="monitor",
            trigger_ref=str(watch.get("id") or ""),
        )
        automation_runs.finish_run(
            run["id"],
            status="source_unavailable",
            error=str(result.get("error") or result.get("code") or "monitor source unavailable"),
        )
        return

    if not result.get("changed"):
        run = automation_runs.begin_run(
            automation_id=automation_id,
            action="web_monitor.notify",
            trigger_kind="monitor",
            trigger_ref=str(watch.get("id") or ""),
        )
        automation_runs.finish_run(
            run["id"],
            status="condition_false",
            error="watch condition did not match",
        )
        return

    from gateway.signal_store import emit

    signal = emit(
        source="web_monitor",
        kind="watch_match",
        payload={
            "watch_id": watch.get("id"),
            "label": watch.get("label"),
            "url": watch.get("url"),
            "keyword_matches": result.get("keyword_matches", []),
            "changed": True,
        },
        dedupe_key=f"web_monitor:{watch.get('id')}:{result.get('hash') or ''}",
    )
    if signal is None:
        return
    await automation_actions.run_action(
        "web_monitor.notify",
        trigger_kind="signal",
        automation_id=automation_id,
        trigger_ref=str(signal["id"]),
        policy_scope_type="automation",
        policy_scope_id=automation_id,
        payload={
            "signal_id": signal["id"],
            "watch_id": watch.get("id"),
            "label": watch.get("label"),
            "url": watch.get("url"),
            "keyword_matches": result.get("keyword_matches", []),
        },
    )


async def deliver_notification(payload: dict) -> object:
    """Send a web-monitor notification as one registered Automation action."""
    from gateway.automation_actions import ActionResult, SourceUnavailable
    from gateway.notify import is_configured, send

    if not is_configured():
        raise SourceUnavailable("Pushover is not configured")
    label = str(payload.get("label") or payload.get("url") or "watch")
    keywords = payload.get("keyword_matches") or []
    kw_text = f" Keywords: {', '.join(map(str, keywords))}" if keywords else ""
    delivered = await asyncio.to_thread(
        send,
        message=f"Watch '{label}' updated.{kw_text}",
        title="Kitty Web Monitor",
        url=payload.get("url"),
        url_title="Open URL",
    )
    if not delivered:
        raise RuntimeError("web monitor notification was not delivered")
    return ActionResult(result_pointer=f"signal:{payload.get('signal_id')}")


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["keywords"] = json.loads(d.get("keywords", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["keywords"] = []
    d["enabled"] = bool(d.get("enabled", 0))
    d["last_keyword_matched"] = bool(d.get("last_keyword_matched", 0))
    return d
