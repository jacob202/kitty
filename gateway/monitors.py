"""URL/page monitors — owned substrate for the monitors endpoint.

Why this module exists (Phase 3 of the gateway deepening program):
the route used to keep a parallel in-memory ``_monitors`` list and
swallow every ``ImportError`` / ``AttributeError`` from
``gateway.web_monitor`` with a try/except that fell back to the
mock. That violated the "Fail loud" prime directive. The new
module delegates to ``web_monitor`` (the real, SQLite-backed store)
and lets its exceptions surface.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("kitty.monitors")


def list_monitors() -> list[dict]:
    """Return every URL/page monitor from the canonical store."""
    from gateway.web_monitor import list_watches

    return list_watches()


def create_monitor(url: str, *, label: str | None = None, interval_minutes: int = 300) -> dict:
    """Register a new monitor. Returns the watch as a dict."""
    from gateway.web_monitor import add_watch

    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")
    if not isinstance(interval_minutes, int) or interval_minutes <= 0:
        raise ValueError("interval_minutes must be a positive int")
    watch_id = add_watch(url=url, label=label or url, interval_minutes=interval_minutes)
    return {
        "watch_id": watch_id,
        "url": url,
        "interval": interval_minutes,
        "enabled": True,
    }


def delete_monitor(monitor_id: str) -> bool:
    """Remove a monitor by id. Returns ``False`` if it was not present."""
    from gateway.web_monitor import remove_watch

    if not isinstance(monitor_id, str) or not monitor_id:
        raise ValueError("monitor_id must be a non-empty string")
    return remove_watch(monitor_id)


async def check_monitor(monitor_id: str) -> dict:
    """Force-check one monitor immediately."""
    from gateway.web_monitor import check_now

    if not isinstance(monitor_id, str) or not monitor_id:
        raise ValueError("monitor_id must be a non-empty string")
    return await check_now(monitor_id)
