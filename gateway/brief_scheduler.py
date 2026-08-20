"""Daily brief scheduler — generates and delivers Jacob's brief at config time.

Public API:
  start_brief_scheduler() -> asyncio.Task | None
  generate_and_deliver_brief() -> str
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from gateway.paths import PROJECT_ROOT

logger = logging.getLogger("kitty.brief_scheduler")

USER_PROFILE_PATH = PROJECT_ROOT / "config" / "user_profile.json"
DEFAULT_BRIEF_TIME = "08:00"
DEFAULT_TIMEZONE = "America/Regina"


def _load_profile() -> dict:
    try:
        data = json.loads(USER_PROFILE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Could not read user profile for brief scheduling: %s", e)
        return {}


def load_brief_time() -> str:
    """Read the configured brief time (HH:MM) from user_profile.json."""
    brief_time = _load_profile().get("brief_time", DEFAULT_BRIEF_TIME)
    if isinstance(brief_time, str) and len(brief_time.split(":")) == 2:
        return brief_time
    return DEFAULT_BRIEF_TIME


def load_brief_timezone() -> ZoneInfo:
    """Return the user's configured IANA timezone for local-clock scheduling."""
    timezone_name = _load_profile().get("timezone", DEFAULT_TIMEZONE)
    if not isinstance(timezone_name, str) or not timezone_name.strip():
        timezone_name = DEFAULT_TIMEZONE
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.warning(
            "Unknown brief timezone %r; falling back to %s",
            timezone_name,
            DEFAULT_TIMEZONE,
        )
        return ZoneInfo(DEFAULT_TIMEZONE)


def seconds_until(hh_mm: str, now: datetime) -> float:
    """Return seconds from ``now`` until the next occurrence of ``hh:mm``."""
    hour_str, minute_str = hh_mm.split(":")
    target = now.replace(hour=int(hour_str), minute=int(minute_str), second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return (target - now).total_seconds()


def _format_brief_text(brief: dict) -> str:
    """Turn a brief dict into at most 5 plain-text bullets for stdout/log."""
    lines: list[str] = []

    date = brief.get("date") or datetime.now(timezone.utc).date().isoformat()
    lines.append(f"Brief for {date}")

    # Inbox / open items
    inbox_items = brief.get("inbox_items") or []
    for item in inbox_items[:2]:
        text = str(item.get("text") or item.get("title") or "").strip()
        if text:
            lines.append(f"- Inbox: {text[:120]}")

    # Signals from the last 24h
    signals = brief.get("signals") or []
    for signal in signals[:2]:
        payload = signal.get("payload") or {}
        text = str(payload.get("message") or payload.get("title") or "").strip()
        if text:
            lines.append(f"- Signal: {text[:120]}")

    # One "worth knowing" item (headline, knowledge, or memory)
    worth = None
    headlines = brief.get("headlines") or []
    if headlines:
        worth = str(headlines[0].get("title") if isinstance(headlines[0], dict) else headlines[0].title).strip()
    if worth:
        lines.append(f"- Worth knowing: {worth[:120]}")

    # Intention / next action
    intention = brief.get("intention") or ""
    if intention:
        lines.append(f"- Intention: {intention[:120]}")

    # What's B — each active project's curated next step (P4, 016)
    for next_step in (brief.get("next_steps") or [])[:3]:
        name = str(next_step.get("project_name") or "").strip()
        step = str(next_step.get("step") or "").strip()
        if name and step:
            lines.append(f"- {name}: {step[:120]}")

    # Deadlines — approaching benefits/admin obligations (P7, 017)
    for deadline in (brief.get("deadlines") or [])[:2]:
        due = str(deadline.get("due_date") or "").strip()
        obligation = str(deadline.get("obligation") or "").strip()
        amount = str(deadline.get("amount") or "").strip()
        if obligation:
            tail = f" ({amount})" if amount else ""
            lines.append(f"- Deadline {due}: {obligation[:120]}{tail}")

    # Cap at 5 bullets (date line + up to 4 bullets)
    return "\n".join(lines[:5])


def generate_and_deliver_brief() -> str:
    """Generate the brief, log it, and push if configured."""
    from gateway.brief import generate_brief

    brief = generate_brief()
    text = _format_brief_text(brief)

    # Deliver to stdout/log for now
    logger.info("Daily brief delivered:\n%s", text)

    # Push to Jacob's phone via the push façade (iMessage first, Pushover fallback).
    try:
        from gateway.push import push_to_jacob

        if not push_to_jacob(text, kind="info", title="Kitty Morning Brief"):
            logger.warning(
                "Brief push not delivered — no configured channel accepted it "
                "(set PUSH_IMESSAGE_RECIPIENT or PUSHOVER_USER_KEY/PUSHOVER_API_TOKEN)"
            )
    except Exception as e:
        logger.warning("Brief push notification failed: %s", e)

    return text


async def _scheduler_loop() -> None:
    """Background loop: sleep until brief_time, deliver, repeat daily."""
    while True:
        brief_time = load_brief_time()
        brief_timezone = load_brief_timezone()
        now = datetime.now(brief_timezone)
        wait_seconds = seconds_until(brief_time, now)
        logger.info(
            "Next brief scheduled at %s %s (in %.0f seconds)",
            brief_time,
            brief_timezone.key,
            wait_seconds,
        )
        await asyncio.sleep(wait_seconds)

        try:
            generate_and_deliver_brief()
        except Exception as e:
            logger.error("Scheduled brief delivery failed: %s", e)

        # Give the clock time to move past the just-fired minute, then recompute
        # from the user's local timezone. A fixed 24-hour sleep can skip a local
        # morning across daylight-saving transitions.
        await asyncio.sleep(60)


def start_brief_scheduler() -> asyncio.Task | None:
    """Start the daily brief scheduler as a background asyncio task."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return loop.create_task(_scheduler_loop())
