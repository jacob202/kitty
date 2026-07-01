"""Read-only current-state composition for /state/now."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from gateway import calendar_integration, chats_store, desktop_store, journal_store, todo_store

SCHEMA_VERSION = 1
DEFAULT_SOURCE_TIMEOUT_SECONDS = 4.0
_DONE_STATUSES = {"done", "completed"}
T = TypeVar("T")


class SourceTimeoutError(TimeoutError):
    pass


class SourceUnavailableError(RuntimeError):
    pass


def compose_now(timeout_seconds: float = DEFAULT_SOURCE_TIMEOUT_SECONDS) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    sections = {
        "today": _section("today", _read_today_items, timeout_seconds, errors),
        "open_loops": _section("open_loops", _read_open_loop_items, timeout_seconds, errors),
        "recent_activity": _section(
            "recent_activity", _read_recent_activity_items, timeout_seconds, errors
        ),
        "runtime_health": {"status": "error", "detail": "not yet wired"},
    }
    return {
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "schema_version": SCHEMA_VERSION,
        "sections": sections,
        "errors": errors,
    }


def _section(
    name: str,
    reader: Callable[[], list[dict[str, Any]]],
    timeout_seconds: float,
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    try:
        items = _with_timeout(reader, timeout_seconds)
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        errors.append({"section": name, "detail": detail})
        return {"status": "error", "items": [], "detail": detail}
    if not items:
        return {"status": "empty", "items": []}
    return {"status": "ok", "items": items}


def _with_timeout(fn: Callable[[], T], timeout_seconds: float) -> T:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeout as exc:
        future.cancel()
        raise SourceTimeoutError(f"source timed out after {timeout_seconds:g}s") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _read_today_items() -> list[dict[str, Any]]:
    if not calendar_integration.is_available():
        raise SourceUnavailableError("calendar integration unavailable")
    return [
        {
            "kind": "calendar_event",
            "id": event.get("id"),
            "title": event.get("title", ""),
            "starts_at": event.get("start"),
            "ends_at": event.get("end"),
            "source": "calendar",
        }
        for event in calendar_integration.get_today()
    ]


def _read_open_loop_items() -> list[dict[str, Any]]:
    return [*_read_todo_loop_items(), *_read_inbox_loop_items()]


def _read_todo_loop_items() -> list[dict[str, Any]]:
    rows = todo_store.get()
    active = [row for row in rows if str(row.get("status", "")).lower() not in _DONE_STATUSES]
    return [
        {
            "kind": "todo",
            "id": str(row.get("id")),
            "title": row.get("content", ""),
            "status": row.get("status"),
            "source": "todos",
            "updated_at": _coerce_time(row.get("updated_at")),
        }
        for row in active[:10]
    ]


def _read_inbox_loop_items() -> list[dict[str, Any]]:
    rows = desktop_store.read_inbox(limit=20)
    unprocessed = [row for row in rows if row.get("processed") is not True]
    return [
        {
            "kind": "inbox_entry",
            "id": str(row.get("id")),
            "title": _clip_text(str(row.get("text", ""))),
            "source": row.get("source", "inbox"),
            "created_at": row.get("created_at"),
        }
        for row in unprocessed[-5:]
    ]


def _read_recent_activity_items() -> list[dict[str, Any]]:
    return [*_read_journal_activity_items(), *_read_chat_activity_items()]


def _read_journal_activity_items() -> list[dict[str, Any]]:
    return [
        {
            "kind": "journal_entry",
            "id": str(entry.get("id")),
            "title": entry.get("theme") or _clip_text(str(entry.get("entry", ""))),
            "source": "journal",
            "updated_at": _coerce_time(entry.get("ts")),
        }
        for entry in journal_store.list_recent(days=14, limit=5)
    ]


def _read_chat_activity_items() -> list[dict[str, Any]]:
    return [
        {
            "kind": "chat_session",
            "id": str(chat.get("id")),
            "title": chat.get("title") or "Untitled chat",
            "source": "chats",
            "updated_at": _coerce_time(_chat_updated_at(chat)),
        }
        for chat in chats_store.list_chats()[:5]
    ]


def _chat_updated_at(chat: dict[str, Any]) -> Any:
    for key in ("updated_at", "updatedAt", "created_at", "createdAt", "ts"):
        if chat.get(key) is not None:
            return chat.get(key)
    messages = chat.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict):
                for key in ("ts", "timestamp", "created_at", "createdAt"):
                    if message.get(key) is not None:
                        return message.get(key)
    return None


def _coerce_time(value: Any) -> Any:
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000 if float(value) > 100_000_000_000 else float(value)
        try:
            return datetime.fromtimestamp(seconds, tz=UTC).isoformat().replace("+00:00", "Z")
        except (OverflowError, OSError, ValueError):
            return value
    return value


def _clip_text(text: str, limit: int = 80) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 1].rstrip() + "…"
