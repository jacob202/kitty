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
import sqlite3
from typing import Any

from gateway.errors import KittyError, StorageNotFound, StorageUnavailable

logger = logging.getLogger("kitty.monitors")


class MonitorError(StorageUnavailable):
    """Raised when the canonical monitor store cannot complete an operation."""


class MonitorNotFoundError(StorageNotFound):
    """Raised when a requested monitor does not exist."""


class MonitorCheckError(KittyError):
    """Raised when a monitor exists but its upstream URL check fails."""

    status_code = 502
    code = "monitor.check_failed"


def _store_failure(operation: str, exc: Exception, **details: Any) -> MonitorError:
    # Raw exception text can contain filesystem paths; keep it in logs only,
    # never in the HTTP-visible message (same policy as gateway/memory.py).
    logger.error("monitor %s failed: %s: %s", operation, type(exc).__name__, exc)
    return MonitorError(
        f"monitor {operation} failed ({type(exc).__name__})",
        details={
            "operation": operation,
            "exception_type": type(exc).__name__,
            **details,
        },
    )


def list_monitors() -> list[dict]:
    """Return every URL/page monitor from the canonical store."""
    try:
        from gateway.web_monitor import list_watches

        watches = list_watches()
    except (sqlite3.Error, OSError) as exc:
        raise _store_failure("list", exc) from exc

    if not isinstance(watches, list):
        raise MonitorError(
            f"monitor list failed: backend returned {type(watches).__name__}, expected list",
            details={"operation": "list", "response_type": type(watches).__name__},
        )
    for index, watch in enumerate(watches):
        if not isinstance(watch, dict):
            raise MonitorError(
                f"monitor list failed: result {index} is {type(watch).__name__}, expected dict",
                details={
                    "operation": "list",
                    "result_index": index,
                    "result_type": type(watch).__name__,
                },
            )
    return watches


def create_monitor(url: str, *, label: str | None = None, interval_minutes: int = 300) -> dict:
    """Register a new monitor. Returns the watch as a dict."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")
    if label is not None and not isinstance(label, str):
        raise ValueError("label must be a string or None")
    if (
        not isinstance(interval_minutes, int)
        or isinstance(interval_minutes, bool)
        or interval_minutes <= 0
    ):
        raise ValueError("interval_minutes must be a positive int")

    try:
        from gateway.web_monitor import add_watch

        watch_id = add_watch(
            url=url,
            label=label or url,
            interval_minutes=interval_minutes,
        )
    except (sqlite3.Error, OSError) as exc:
        raise _store_failure("create", exc) from exc

    if not isinstance(watch_id, str) or not watch_id.strip():
        raise MonitorError(
            "monitor create failed: backend returned an invalid watch id",
            details={
                "operation": "create",
                "watch_id_type": type(watch_id).__name__,
            },
        )
    return {
        "watch_id": watch_id,
        "url": url,
        "interval": interval_minutes,
        "enabled": True,
    }


def delete_monitor(monitor_id: str) -> bool:
    """Remove a monitor by id. Returns ``False`` if it was not present."""
    if not isinstance(monitor_id, str) or not monitor_id.strip():
        raise ValueError("monitor_id must be a non-empty string")

    try:
        from gateway.web_monitor import remove_watch

        deleted = remove_watch(monitor_id)
    except (sqlite3.Error, OSError) as exc:
        raise _store_failure("delete", exc, monitor_id=monitor_id) from exc

    if not isinstance(deleted, bool):
        raise MonitorError(
            f"monitor delete failed: backend returned {type(deleted).__name__}, expected bool",
            details={
                "operation": "delete",
                "monitor_id": monitor_id,
                "response_type": type(deleted).__name__,
            },
        )
    return deleted


async def check_monitor(monitor_id: str) -> dict:
    """Force-check one monitor immediately."""
    if not isinstance(monitor_id, str) or not monitor_id.strip():
        raise ValueError("monitor_id must be a non-empty string")

    try:
        from gateway.web_monitor import check_now

        result = await check_now(monitor_id)
    except KittyError:
        raise
    except (sqlite3.Error, OSError) as exc:
        raise _store_failure("check", exc, monitor_id=monitor_id) from exc

    if not isinstance(result, dict):
        raise MonitorCheckError(
            f"monitor check failed for {monitor_id!r}: backend returned "
            f"{type(result).__name__}, expected dict",
            details={
                "operation": "check",
                "monitor_id": monitor_id,
                "response_type": type(result).__name__,
            },
        )

    if result.get("error") == "Watch not found":
        raise MonitorNotFoundError(
            f"monitor {monitor_id!r} was not found",
            details={"monitor_id": monitor_id},
        )

    if result.get("status") == "error" or result.get("error"):
        upstream_status = result.get("code")
        details: dict[str, Any] = {
            "operation": "check",
            "monitor_id": monitor_id,
        }
        if upstream_status is None:
            # web_monitor currently folds local persistence and transport
            # exceptions into the same untyped envelope. Treat that lost-origin
            # state as backend degradation; claiming a 502 would invent an
            # upstream HTTP response that may never have existed.
            raise MonitorError(
                f"monitor check failed for {monitor_id!r}: backend returned an unclassified error",
                details=details,
            )

        details["upstream_status"] = upstream_status
        raise MonitorCheckError(
            f"monitor check failed for {monitor_id!r}: upstream returned HTTP {upstream_status}",
            details=details,
        )

    result_watch_id = result.get("watch_id")
    if (
        not isinstance(result_watch_id, str)
        or not result_watch_id.strip()
        or result_watch_id != monitor_id
    ):
        raise MonitorCheckError(
            f"monitor check failed for {monitor_id!r}: backend returned an "
            "invalid or mismatched watch_id",
            details={
                "operation": "check",
                "monitor_id": monitor_id,
                "response_watch_id_type": type(result_watch_id).__name__,
            },
        )
    if not isinstance(result.get("changed"), bool):
        raise MonitorCheckError(
            f"monitor check failed for {monitor_id!r}: backend returned a "
            "non-boolean 'changed' value",
            details={
                "operation": "check",
                "monitor_id": monitor_id,
                "changed_type": type(result.get("changed")).__name__,
            },
        )

    return result
