"""Deadline watch cron — escalating pushes for approaching deadlines (P7, docs/packets/017).

Public API:
  check_and_push(now=None, push_fn=None) -> dict
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable

from gateway import deadline_store

logger = logging.getLogger("kitty.deadline_watch")

PushFn = Callable[[str], bool]


def _default_push(message: str, *, title: str, kind: str, dedupe_key: str) -> bool:
    from gateway.push import push_to_jacob

    return push_to_jacob(message, title=title, kind=kind, dedupe_key=dedupe_key)


def check_and_push(
    now: date | None = None,
    push_fn: Callable[..., bool] | None = None,
) -> dict[str, Any]:
    """Scan open deadlines and push for any due escalation checkpoint today.

    ``push_fn`` accepts (message, *, title, kind, dedupe_key) -> bool.
    """
    today = now if now is not None else date.today()
    sender = push_fn or _default_push

    checked = 0
    pushed = 0
    skipped = 0

    for deadline in deadline_store.list_open(status="open"):
        checked += 1
        checkpoint = deadline_store.checkpoint_due(deadline, today)
        if checkpoint is None:
            skipped += 1
            continue
        if deadline_store.escalation_already_sent(deadline["id"], checkpoint):
            skipped += 1
            continue

        message = _format_message(deadline, checkpoint)
        dedupe_key = f"deadline-{deadline['id']}-{checkpoint}"
        try:
            ok = sender(
                message,
                title=f"Deadline {checkpoint}",
                kind="alert",
                dedupe_key=dedupe_key,
            )
        except Exception as exc:  # noqa: BLE001 — a push failure must not crash the cron
            logger.error("push failed for deadline %s: %s", deadline["id"], exc)
            ok = False

        if ok:
            deadline_store.record_escalation(deadline["id"], checkpoint)
            deadline_store.mark_pushed(deadline["id"])
            pushed += 1
        else:
            skipped += 1

    return {"checked": checked, "pushed": pushed, "skipped": skipped}


def _format_message(deadline: dict[str, Any], checkpoint: str) -> str:
    parts = [f"{deadline['obligation']} — due {deadline['due_date']} ({checkpoint})"]
    if deadline.get("amount"):
        parts.append(f"Amount: {deadline['amount']}")
    return "\n".join(parts)
