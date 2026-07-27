"""Insight lifecycle: capture, classify, return, act, learn (issue #270).

Reuses idea_mine_items as the durable store with lifecycle fields in
payload_json. The existing review gate (user_review) maps to consent:
- approved = explicitly consented (live capture)
- unreviewed = inferred/imported, must be approved before surfacing
- rejected/keep_quiet = permanently suppressed
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from gateway import idea_mine_store, signal_store
from gateway.paths import KITTY_DB_FILE

logger = logging.getLogger("kitty.insight_loop")

INSIGHT_DB_FILE = KITTY_DB_FILE

CATEGORIES = frozenset({
    "task",
    "reminder",
    "product_idea",
    "research_question",
    "script_opportunity",
    "builder_packet",
    "decision",
    "reference",
})

RETURN_POLICIES = frozenset({"explicit_time", "next_brief"})

LIFECYCLE_STATUSES = frozenset({
    "pending", "returned", "acted", "snoozed", "archived",
})

# Categories whose payload.return_at must be set before capture.
_TIME_REQUIRED_CATEGORIES = frozenset({"reminder"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def capture(
    text: str,
    source_ref: str | None = None,
    category: str | None = None,
    return_at: str | None = None,
    return_policy: str = "next_brief",
    explicit_consent: bool = False,
) -> int:
    """Persist a new insight. Returns the item id.

    explicit_consent=True → user_review=approved (may surface immediately).
    explicit_consent=False → user_review=unreviewed (must be approved first).

    Raises ValueError on bad category, policy, or missing return_at.
    """
    category = category or "reference"
    if category not in CATEGORIES:
        raise ValueError(f"unknown category: {category!r}")
    if return_policy not in RETURN_POLICIES:
        raise ValueError(f"unknown return_policy: {return_policy!r}")
    if category in _TIME_REQUIRED_CATEGORIES and return_at is None:
        raise ValueError(f"{category} requires a return_at")

    payload: dict[str, Any] = {
        "summary": text.strip(),
        "category": category,
        "return_policy": return_policy,
        "return_at": return_at,
        "status": "pending",
        "returned_count": 0,
        "last_returned_at": None,
        "action_id": None,
        "outcome": None,
    }

    item: dict[str, Any] = {
        "object_type": "insight",
        "source_ref": source_ref,
        "user_review": "approved" if explicit_consent else "unreviewed",
    }
    item.update(payload)

    item_id = idea_mine_store.insert_item(item, db_file=INSIGHT_DB_FILE)
    logger.info("insight captured id=%s category=%s consent=%s", item_id, category, explicit_consent)
    return item_id


def list_due(now: str | None = None) -> list[dict[str, Any]]:
    """Return approved pending insights whose return_at has passed or is next_brief.

    Items are deterministic within a call. Suppressed items never appear.
    """
    now = now or _now_iso()
    due: list[dict[str, Any]] = []

    for item in _list_pending_approved():
        payload = item.get("payload", {})
        policy = payload.get("return_policy", "next_brief")

        if policy == "next_brief":
            due.append(item)
        elif policy == "explicit_time":
            ret_at = payload.get("return_at")
            if ret_at and ret_at <= now:
                due.append(item)

    return due


def mark_returned(item_id: int, channel: str = "signal") -> bool:
    """Record that an insight was returned to Jacob. Returns False if missing.

    Emits a signal so the state composer and UI surface see it.
    """
    item = idea_mine_store.get_item(item_id, db_file=INSIGHT_DB_FILE)
    if item is None:
        return False

    payload = item.get("payload", {})
    current_status = payload.get("status", "pending")
    if current_status != "pending":
        logger.warning("insight %s mark_returned skipped: status is %s", item_id, current_status)
        return False

    now_iso = _now_iso()
    returned_count = (payload.get("returned_count") or 0) + 1

    idea_mine_store.update_payload(
        item_id,
        {"status": "returned", "returned_count": returned_count, "last_returned_at": now_iso},
        db_file=INSIGHT_DB_FILE,
    )

    signal_store.emit(
        source="insight_loop",
        kind="insight.returned",
        payload={
            "insight_id": item_id,
            "summary": payload.get("summary", ""),
            "category": payload.get("category", ""),
            "channel": channel,
            "returned_count": returned_count,
        },
        dedupe_key=f"insight_returned_{item_id}_{returned_count}",
    )

    logger.info("insight %s returned (channel=%s, count=%d)", item_id, channel, returned_count)
    return True


def respond(
    item_id: int,
    choice: str,
    snooze_until: str | None = None,
    archive_reason: str | None = None,
) -> dict[str, Any]:
    """Record Jacob's response to a returned insight.

    choice must be one of: act, snooze, archive.

    act → creates a todo.create action and links it.
    snooze → updates return_at and resets to pending.
    archive → closes with an outcome reason.

    Returns the updated item dict.
    """
    if choice not in ("act", "snooze", "archive"):
        raise ValueError(f"invalid choice: {choice!r}")

    item = idea_mine_store.get_item(item_id, db_file=INSIGHT_DB_FILE)
    if item is None:
        raise LookupError(f"no insight with id {item_id}")

    payload = item.get("payload", {})
    current_status = payload.get("status")
    if current_status not in ("returned", "pending"):
        raise ValueError(f"insight {item_id} cannot respond in status {current_status!r}")

    if choice == "act":
        return _do_act(item_id, item, payload)
    elif choice == "snooze":
        return _do_snooze(item_id, payload, snooze_until)
    else:
        return _do_archive(item_id, payload, archive_reason)


def _do_act(item_id: int, item: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    from gateway import action_queue

    summary = payload.get("summary", "")
    action = action_queue.propose(
        source_kind="insight_loop",
        kind="todo.create",
        title=f"Insight: {summary[:80]}",
        preview=summary[:200],
        source_id=str(item_id),
        payload={"content": summary},
    )
    executed = action_queue.execute(action["id"])

    idea_mine_store.update_payload(
        item_id,
        {"status": "acted", "action_id": executed["id"], "outcome": "acted"},
        db_file=INSIGHT_DB_FILE,
    )

    signal_store.emit(
        source="insight_loop",
        kind="insight.acted",
        payload={
            "insight_id": item_id,
            "summary": summary[:200],
            "action_id": executed["id"],
        },
    )

    logger.info("insight %s acted → action %s", item_id, executed["id"])
    updated = idea_mine_store.get_item(item_id, db_file=INSIGHT_DB_FILE)
    return updated or item


def _do_snooze(
    item_id: int, payload: dict[str, Any], snooze_until: str | None
) -> dict[str, Any]:
    if not snooze_until:
        raise ValueError("snooze requires a snooze_until ISO datetime")

    idea_mine_store.update_payload(
        item_id,
        {"status": "snoozed", "return_at": snooze_until, "outcome": None},
        db_file=INSIGHT_DB_FILE,
    )

    logger.info("insight %s snoozed until %s", item_id, snooze_until)
    updated = idea_mine_store.get_item(item_id, db_file=INSIGHT_DB_FILE)
    return updated or {"id": item_id, "payload": {**payload, "status": "snoozed", "return_at": snooze_until}}


def _do_archive(
    item_id: int, payload: dict[str, Any], archive_reason: str | None
) -> dict[str, Any]:
    reason = archive_reason or "not_useful"
    if reason not in ("not_useful", "already_handled", "no_longer_relevant"):
        raise ValueError(f"invalid archive_reason: {reason!r}")

    idea_mine_store.update_payload(
        item_id,
        {"status": "archived", "outcome": reason},
        db_file=INSIGHT_DB_FILE,
    )

    logger.info("insight %s archived (%s)", item_id, reason)
    updated = idea_mine_store.get_item(item_id, db_file=INSIGHT_DB_FILE)
    return updated or {"id": item_id, "payload": {**payload, "status": "archived", "outcome": reason}}


def get_insight(item_id: int) -> dict[str, Any] | None:
    """Return one insight by its idea_mine_items id."""
    return idea_mine_store.get_item(item_id, db_file=INSIGHT_DB_FILE)


def list_insights(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """List insights, newest first. Optional lifecycle status filter."""
    items = idea_mine_store.list_items(object_type="insight", db_file=INSIGHT_DB_FILE)
    result: list[dict[str, Any]] = []
    for item in items:
        payload = item.get("payload", {})
        if status is None or payload.get("status") == status:
            result.append(item)
    result.reverse()
    return result[:limit]


def get_metrics() -> dict[str, Any]:
    """Return counts and summary metrics for the insight loop."""
    items = idea_mine_store.list_items(object_type="insight", db_file=INSIGHT_DB_FILE)

    total = len(items)
    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    acted_count = 0
    total_returned = 0

    for item in items:
        payload = item.get("payload", {})
        status = payload.get("status", "pending")
        by_status[status] = by_status.get(status, 0) + 1

        cat = payload.get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1

        rc = payload.get("returned_count") or 0
        total_returned += rc

        if status == "acted":
            acted_count += 1

    return {
        "total": total,
        "by_status": by_status,
        "by_category": by_category,
        "acted_count": acted_count,
        "total_returns": total_returned,
    }


def _list_pending_approved() -> list[dict[str, Any]]:
    """Return all insight items that are approved and status=pending."""
    items = idea_mine_store.list_items(object_type="insight", db_file=INSIGHT_DB_FILE)
    result: list[dict[str, Any]] = []
    for item in items:
        if not idea_mine_store.is_surfaceable(item):
            continue
        payload = item.get("payload", {})
        if payload.get("status", "pending") == "pending":
            result.append(item)
    return result


async def return_due() -> None:
    """Cron action: sweep due insights, mark them returned, emit signals.

    At most 3 per sweep. Idempotent: mark_returned only transitions pending items.
    """
    due = list_due()
    selected = due[:3]
    for item in selected:
        mark_returned(item["id"], channel="cron")


__all__ = [
    "CATEGORIES",
    "RETURN_POLICIES",
    "LIFECYCLE_STATUSES",
    "capture",
    "list_due",
    "mark_returned",
    "respond",
    "get_insight",
    "list_insights",
    "get_metrics",
    "return_due",
]
