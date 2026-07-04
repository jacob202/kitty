"""Push notification façade (P3, docs/packets/015).

The only path from "Kitty needs Jacob to see this" to a delivered iMessage
or Pushover push. Both transports already exist (gateway.imessage,
gateway.notify) — this module adds no new transport, only channel
resolution, quiet hours, dedupe, and an append-only audit log.

Pushes are deliveries, not actions: no action-queue rows, no new tier
kinds. Every attempt (successful or not) is appended to
``logs/push_log.jsonl``.

Public API:
  push_to_jacob(message, *, kind="info", title="Kitty", url=None,
                 dedupe_key=None) -> bool
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Callable

from gateway.paths import CONFIG_DIR, LOGS_DIR

logger = logging.getLogger("kitty.push")

PUSH_LOG_FILE = LOGS_DIR / "push_log.jsonl"
USER_PROFILE_PATH = CONFIG_DIR / "user_profile.json"
DEDUPE_WINDOW_SECONDS = 24 * 60 * 60


def _channels() -> list[str]:
    raw = os.environ.get("PUSH_CHANNELS", "imessage,pushover")
    return [c.strip() for c in raw.split(",") if c.strip()]


def _imessage_recipient() -> str:
    return os.environ.get("PUSH_IMESSAGE_RECIPIENT", "").strip()


def _quiet_hours_window() -> str | None:
    try:
        data = json.loads(USER_PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    value = data.get("quiet_hours")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _in_quiet_hours(window: str, now: datetime) -> bool:
    """``window`` like "23:00-08:00" (may wrap past midnight). Local time."""
    try:
        start_str, end_str = window.split("-")
        start_h, start_m = (int(x) for x in start_str.split(":"))
        end_h, end_m = (int(x) for x in end_str.split(":"))
    except Exception:
        logger.warning("malformed quiet_hours %r — ignoring", window)
        return False
    start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if start <= end:
        return start <= now < end
    return now >= start or now < end


def _recent_log_entries() -> list[dict[str, Any]]:
    if not PUSH_LOG_FILE.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in PUSH_LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _log_attempt(*, kind: str, title: str, channel: str, ok: bool, dedupe_key: str | None) -> None:
    PUSH_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.time(),
        "kind": kind,
        "title": title,
        "channel": channel,
        "ok": ok,
        "dedupe_key": dedupe_key,
    }
    with PUSH_LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def _already_sent(dedupe_key: str) -> bool:
    cutoff = time.time() - DEDUPE_WINDOW_SECONDS
    for entry in reversed(_recent_log_entries()):
        if (
            entry.get("dedupe_key") == dedupe_key
            and entry.get("ok")
            and entry.get("ts", 0) >= cutoff
        ):
            return True
    return False


def _send_imessage(message: str, title: str, url: str | None) -> bool:
    del title, url  # iMessage has no separate title/url fields — body only
    from gateway import imessage

    recipient = _imessage_recipient()
    if not recipient:
        logger.info("iMessage channel disabled — PUSH_IMESSAGE_RECIPIENT not set")
        return False
    return imessage.send(recipient, message)


def _send_pushover(message: str, title: str, url: str | None) -> bool:
    from gateway import notify

    if not notify.is_configured():
        logger.info("Pushover channel disabled — PUSHOVER_USER_KEY/PUSHOVER_API_TOKEN not set")
        return False
    return notify.send(message, title=title, url=url)


_SENDERS: dict[str, Callable[[str, str, str | None], bool]] = {
    "imessage": _send_imessage,
    "pushover": _send_pushover,
}


def push_to_jacob(
    message: str,
    *,
    kind: str = "info",
    title: str = "Kitty",
    url: str | None = None,
    dedupe_key: str | None = None,
) -> bool:
    """Deliver ``message`` to Jacob's phone. Returns True iff a channel accepted it.

    ``url`` is passed through to channels that support it (Pushover); iMessage
    has no separate url field and ignores it.
    """
    if dedupe_key and _already_sent(dedupe_key):
        logger.info("push deduped: %s", dedupe_key)
        return True

    if kind == "info":
        window = _quiet_hours_window()
        if window and _in_quiet_hours(window, datetime.now()):
            logger.info("push deferred (quiet hours %s): %s", window, title)
            return False

    for channel in _channels():
        sender = _SENDERS.get(channel)
        if sender is None:
            logger.warning("unknown push channel %r — skipping", channel)
            continue
        try:
            ok = sender(message, title, url)
        except Exception as exc:  # noqa: BLE001 — a channel raising must not crash the caller
            logger.error("push channel %s raised: %s", channel, exc)
            ok = False
        _log_attempt(kind=kind, title=title, channel=channel, ok=ok, dedupe_key=dedupe_key)
        if ok:
            return True

    logger.error("all push channels failed for %r (kind=%s)", title, kind)
    return False
