"""Composed read of Kitty's current state (P1, docs/packets/001).

compose_now() answers "what is going on right now" as one JSON document
built from the existing stores — it introduces no new source of truth.
Each section is computed independently under a hard time bound; a slow
or broken source yields {"ok": False, "error": ...} for that section
instead of failing the whole read or faking an empty result.

snapshot_now() persists a composed state to state_snapshots, and
changes_since_snapshot() returns a mechanical (no-LLM) diff of the
current state against the latest snapshot, plus signals that arrived
since. That diff is the "what changed" primitive everything else
(home surface, brief opening) builds on.

Sections: todos, inbox, journal, chats, calendar, signals.
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Callable

from gateway import (
    calendar_integration,
    chats_store,
    desktop_store,
    journal_store,
    signal_store,
    todo_store,
)
from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

logger = logging.getLogger("kitty.state_composer")

STATE_DB_FILE = KITTY_DB_FILE
SOURCE_TIMEOUT_SECONDS = 3.0


def init_db() -> None:
    """Apply pending migrations. Idempotent."""
    kitty_db.migrate(db_file=STATE_DB_FILE)


def compose_now() -> dict[str, Any]:
    """Compose the current state from all sources, each independently bounded."""
    sections: dict[str, Any] = {}
    # No `with` block: shutdown(wait=False) so one hung source (e.g. a stuck
    # osascript) cannot block the response past the per-source timeout.
    pool = ThreadPoolExecutor(max_workers=len(SOURCES))
    try:
        futures = {name: pool.submit(fn) for name, fn in SOURCES.items()}
        for name, future in futures.items():
            try:
                data = future.result(timeout=SOURCE_TIMEOUT_SECONDS)
                sections[name] = {"ok": True, **data}
            except FutureTimeoutError:
                sections[name] = {
                    "ok": False,
                    "error": f"timed out after {SOURCE_TIMEOUT_SECONDS}s",
                }
            except Exception as exc:
                logger.warning("state source %s failed: %s", name, exc)
                sections[name] = {"ok": False, "error": str(exc)}
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return {"ts": time.time(), "sections": sections}


def snapshot_now() -> dict[str, Any]:
    """Compose the current state and persist it as the new diff baseline."""
    state = compose_now()
    init_db()
    with kitty_db.connect(STATE_DB_FILE) as conn:
        cursor = conn.execute(
            "INSERT INTO state_snapshots (ts, snapshot) VALUES (?, ?)",
            (state["ts"], json.dumps(state)),
        )
        conn.commit()
        snapshot_id = cursor.lastrowid
    return {"id": snapshot_id, **state}


def changes_since_snapshot() -> dict[str, Any]:
    """Mechanical diff of current state vs the latest snapshot, plus new signals."""
    current = compose_now()
    init_db()
    with kitty_db.connect(STATE_DB_FILE) as conn:
        row = conn.execute(
            "SELECT id, ts, snapshot FROM state_snapshots "
            "ORDER BY ts DESC, id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return {
            "baseline_ts": None,
            "current_ts": current["ts"],
            "changes": [],
            "new_signals": [],
            "note": "no snapshot yet — POST /state/snapshot to create a baseline",
        }
    baseline = json.loads(row["snapshot"])
    return {
        "baseline_ts": row["ts"],
        "current_ts": current["ts"],
        "changes": _diff_sections(baseline.get("sections", {}), current["sections"]),
        "new_signals": signal_store.list_since(ts=row["ts"], limit=50),
    }


def _diff_sections(
    before: dict[str, Any], after: dict[str, Any]
) -> list[dict[str, Any]]:
    """Compare scalar section fields; lists/dicts are display detail, not state."""
    changes: list[dict[str, Any]] = []
    for section in sorted(set(before) | set(after)):
        b = before.get(section, {})
        a = after.get(section, {})
        for field in sorted(set(b) | set(a)):
            bv = b.get(field)
            av = a.get(field)
            if isinstance(bv, (list, dict)) or isinstance(av, (list, dict)):
                continue
            if bv != av:
                changes.append(
                    {"section": section, "field": field, "before": bv, "after": av}
                )
    return changes


def _todos_section() -> dict[str, Any]:
    items = todo_store.get()
    open_items = [t for t in items if t.get("status") != "completed"]
    return {
        "open_count": len(open_items),
        "latest": [t.get("content", "") for t in open_items[:5]],
    }


def _inbox_section() -> dict[str, Any]:
    rows = desktop_store.read_inbox(limit=0)
    unprocessed = [r for r in rows if not r.get("processed")]
    return {
        "total_count": len(rows),
        "untriaged_count": len(unprocessed),
        "latest_ts": rows[-1].get("created_at") if rows else None,
    }


def _journal_section() -> dict[str, Any]:
    latest = journal_store.list_entries(limit=1)
    return {
        "count": journal_store.count_entries(),
        "latest_ts": latest[0]["ts"] if latest else None,
    }


def _chats_section() -> dict[str, Any]:
    return {"count": len(chats_store.list_chats())}


def _calendar_section() -> dict[str, Any]:
    # Known limitation: calendar_integration.get_today masks AppleScript
    # failures as an empty day; fixing that belongs to the calendar module.
    events = calendar_integration.get_today()
    return {"today_count": len(events), "events": events[:10]}


def _signals_section() -> dict[str, Any]:
    return {
        "unprocessed_count": signal_store.count_unprocessed(),
        "latest": signal_store.list_recent(limit=5),
    }


SOURCES: dict[str, Callable[[], dict[str, Any]]] = {
    "todos": _todos_section,
    "inbox": _inbox_section,
    "journal": _journal_section,
    "chats": _chats_section,
    "calendar": _calendar_section,
    "signals": _signals_section,
}
