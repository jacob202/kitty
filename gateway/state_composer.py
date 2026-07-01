"""Read-only current-state composition for /state/now."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from gateway import calendar_integration, chats_store, desktop_store, journal_store, todo_store

SCHEMA_VERSION = 1
_DONE_STATUSES = {"done", "completed"}


def compose_now(timeout_seconds: float = 4.0) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    sections = {
        "today": _section("today", _read_today_items, errors),
        "open_loops": _section("open_loops", _read_open_loop_items, errors),
        "recent_activity": _section("recent_activity", _read_recent_activity_items, errors),
        "runtime_health": {"status": "error", "detail": "not yet wired"},
    }
    return {
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "schema_version": SCHEMA_VERSION,
        "sections": sections,
        "errors": errors,
    }


def _section(name: str, reader, errors: list[dict[str, str]]) -> dict[str, Any]:
    try:
        items = reader()
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        errors.append({"section": name, "detail": detail})
        return {"status": "error", "items": [], "detail": detail}
    if not items:
        return {"status": "empty", "items": []}
    return {"status": "ok", "items": items}


def _read_today_items() -> list[dict[str, Any]]:
    if not calendar_integration.is_available():
        raise RuntimeError("calendar integration unavailable")
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
    items = []
    for row in todo_store.get():
        if str(row.get("status", "")).lower() in _DONE_STATUSES:
            continue
        items.append({"kind": "todo", "id": str(row.get("id")), "title": row.get("content", ""), "source": "todos"})
    for row in desktop_store.read_inbox(limit=20):
        if row.get("processed") is True:
            continue
        items.append({"kind": "inbox_entry", "id": str(row.get("id")), "title": str(row.get("text", ""))[:80], "source": row.get("source", "inbox")})
    return items[:15]


def _read_recent_activity_items() -> list[dict[str, Any]]:
    items = []
    for entry in journal_store.list_recent(days=14, limit=5):
        items.append({"kind": "journal_entry", "id": str(entry.get("id")), "title": entry.get("theme") or str(entry.get("entry", ""))[:80], "source": "journal"})
    for chat in chats_store.list_chats()[:5]:
        items.append({"kind": "chat_session", "id": str(chat.get("id")), "title": chat.get("title") or "Untitled chat", "source": "chats"})
    return items
