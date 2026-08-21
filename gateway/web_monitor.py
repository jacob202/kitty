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

    if result.get("changed"):
        _notify_match(watch, result)

    return result


async def check_due() -> dict:
    """Check enabled watches whose per-watch interval is due once.

    Timing ownership belongs to the canonical cron/Automation lifecycle; this
    function retains web-monitor domain semantics and per-watch cadence.
    """
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
                _notify_match(watch, result)
            if result.get("status") == "error":
                failed += 1
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

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Kitty/1.0 Web Monitor (personal use)"
            })
            if resp.status_code != 200:
                return {"status": "error", "code": resp.status_code, "changed": False}

            text = resp.text
            new_hash = hashlib.sha256(text.encode()).hexdigest()

            # Update last checked time and hash
            now = time.time()
            with db_connect(MONITOR_DB) as conn:
                conn.execute(
                    "UPDATE watches SET last_hash = ?, last_checked = ?, last_result = ? WHERE id = ?",
                    (new_hash, now, text[:5000], watch["id"]),
                )
                conn.commit()

            changed = new_hash != old_hash and old_hash != ""

            result = {
                "watch_id": watch["id"],
                "url": url,
                "changed": changed,
                "hash": new_hash[:16],
                "content_length": len(text),
            }

            # Check keyword matches
            if keywords:
                lower = text.lower()
                matches = [k for k in keywords if k.lower() in lower]
                if matches:
                    result["keyword_matches"] = matches
                    result["changed"] = True  # keyword match counts as change

            return result

    except Exception as e:
        logger.error("Watch check failed for %s: %s", url, e)
        return {"status": "error", "error": str(e), "changed": False}


def _notify_match(watch: dict, result: dict) -> None:
    """Send notification and emit a signal when a watch finds a match."""
    try:
        from gateway.notify import send
        label = watch.get("label", watch.get("url", ""))
        keywords = result.get("keyword_matches", [])
        kw_text = f" Keywords: {', '.join(keywords)}" if keywords else ""
        send(
            message=f"Watch '{label}' updated.{kw_text}",
            title="Kitty Web Monitor",
            url=watch.get("url"),
            url_title="Open URL",
        )
    except Exception:
        logger.exception("Failed to send watch notification")

    try:
        from gateway.signal_store import emit

        emit(
            source="web_monitor",
            kind="watch_match",
            payload={
                "watch_id": watch.get("id"),
                "label": watch.get("label"),
                "url": watch.get("url"),
                "keyword_matches": result.get("keyword_matches", []),
                "changed": result.get("changed", False),
            },
        )
    except Exception:
        logger.exception("Failed to emit web_monitor signal")


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["keywords"] = json.loads(d.get("keywords", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["keywords"] = []
    return d
