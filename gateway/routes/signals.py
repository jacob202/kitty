"""Signals feed — proactive signal feed as RepairsIssue-shaped records.

Combines unprocessed signals from signal_store with expert inbox entries
into the same shape the RepairsCard already renders.  The client renders
both RepairsCard and SignalsCard from one component pattern.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

logger = logging.getLogger("kitty.signals")
router = APIRouter(tags=["signals"])


@router.get("/signals")
async def list_signals():
    """Return unprocessed signals as RepairsIssue-shaped records.

    Sources:
    1. signal_store.list_unprocessed — connector and system events
    2. expert_inbox_log — unprocessed expert inbox entries (status='new')
    """
    import pathlib
    import sys

    ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(ROOT))

    try:
        from gateway import signal_store, expert_state
    except ImportError:
        logger.error("cannot import signal_store/expert_state", exc_info=True)
        return {
            "ok": False,
            "error": "signals engine unavailable",
            "checks_run": 0,
            "issues": 0,
            "repairs": [],
        }

    issues: list[dict] = []
    checks_run = 0

    # 1. Unprocessed signals from signal_store
    try:
        unprocessed = signal_store.list_unprocessed(limit=50)
        checks_run += 1
        for sig in unprocessed:
            issues.append(_signal_to_repair(sig))
    except Exception as exc:
        logger.warning("signal_store query failed: %s", exc)
        checks_run += 1

    # 2. Expert inbox entries with status='new'
    try:
        inbox_entries = _list_new_inbox_entries()
        checks_run += 1
        for entry in inbox_entries:
            issues.append(_inbox_to_repair(entry))
    except Exception as exc:
        logger.warning("expert_inbox_log query failed: %s", exc)
        checks_run += 1

    return {
        "ok": True,
        "checks_run": checks_run,
        "issues": len(issues),
        "repairs": issues,
    }


@router.post("/signals/dismiss")
async def dismiss_signal(body: dict):
    """Dismiss a signal — marks it processed and (for expert signals)
    increments the dismissed count for the topic_hash."""
    signal_id = body.get("signal_id")
    if not isinstance(signal_id, int):
        raise HTTPException(status_code=400, detail="signal_id must be an integer")

    try:
        from gateway import signal_store, expert_state
    except ImportError:
        raise HTTPException(status_code=500, detail="signals engine unavailable")

    sig = signal_store.get_signal(signal_id)
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Mark processed
    signal_store.mark_processed(signal_id)

    # For expert signals, also increment dismissed count
    source = sig.get("source", "")
    if source.startswith("expert."):
        expert_id = source[len("expert."):]
        topic_hash = sig.get("payload", {}).get("topic_hash")
        if topic_hash:
            try:
                expert_state.increment_dismissed_count(expert_id, topic_hash)
            except Exception as exc:
                logger.warning("increment_dismissed_count failed: %s", exc)

    from gateway.sse import broadcaster
    broadcaster.broadcast("state_updated")

    return {"ok": True, "signal_id": signal_id}


def _list_new_inbox_entries() -> list[dict]:
    """Return expert_inbox_log entries with status='new'."""
    from gateway import db as kitty_db
    from gateway.paths import KITTY_DB_FILE

    kitty_db.migrate()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        rows = conn.execute(
            "SELECT expert_id, inbox_id, status, created_at, updated_at "
            "FROM expert_inbox_log WHERE status = 'new' "
            "ORDER BY created_at ASC LIMIT 50"
        ).fetchall()
    return [
        {
            "expert_id": r["expert_id"],
            "inbox_id": r["inbox_id"],
            "status": r["status"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def _signal_to_repair(sig: dict) -> dict:
    """Convert a signal_store record to RepairsIssue shape."""
    source = sig.get("source", "unknown")
    kind = sig.get("kind", "unknown")
    payload = sig.get("payload", {})

    # Expert signals are suggestions (warn), others vary by kind
    is_expert = source.startswith("expert.")
    if is_expert:
        severity = "warn"
        expert_id = source[len("expert."):]
        title = payload.get("headline") or kind.replace(".", " ").replace("_", " ")
        detail = payload.get("analysis") or payload.get("action") or f"Expert {expert_id} suggestion"
        topic_hash = payload.get("topic_hash")

        fix = None
        if topic_hash:
            fix = {
                "label": "snooze for a day",
                "action_kind": "signal.snooze",
                "check_name": f"expert:{expert_id}",
            }
    else:
        severity = "warn"
        title = f"{source}: {kind.replace('.', ' ').replace('_', ' ')}"
        detail = payload.get("message") or payload.get("summary") or ""
        fix = None

    return {
        "id": f"signal-{sig['id']}",
        "severity": severity,
        "title": title,
        "detail": detail,
        "fix": fix,
    }


def _inbox_to_repair(entry: dict) -> dict:
    """Convert an expert_inbox_log entry to RepairsIssue shape."""
    expert_id = entry.get("expert_id", "unknown")
    inbox_id = entry.get("inbox_id", "unknown")

    return {
        "id": f"inbox-{expert_id}-{inbox_id}",
        "severity": "warn",
        "title": f"New insight from {expert_id}",
        "detail": f"Inbox entry {inbox_id} awaiting review",
        "fix": {
            "label": "review",
            "action_kind": "signal.dismiss",
            "check_name": f"inbox:{expert_id}:{inbox_id}",
        },
    }
