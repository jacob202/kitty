"""Write-side StorageRouter.

Phase B B4: route handlers must not import write functions from concrete
store modules. This module is the single seam for state writes.

Why: the storage substrate is migrating from JSON files to SQLite. If
routes call ``todo_store.add()`` directly, every future migration means
editing every route. If routes call ``storage_router.add_todo()``, the
substrate can change without touching routes.

Phase 1 deepening (per
``docs/superpowers/specs/2026-06-24-gateway-deepening-program-design.md``):
each entry point now also (1) validates its inputs and (2) emits a
``kind=storage_write`` record to ``data/kitty_token_log.jsonl`` so
operators can see writes happening without enabling a debug log. The
write itself still happens through the underlying store — the router
adds the seam behavior, it does not replace the store.

Reads are intentionally not routed through here. Reads are cheap,
cache-friendly, and used in hot paths; routing them adds an indirection
without buying anything. Reads still go to the store modules directly.

When to add a method: a route handler needs to mutate state owned by
a store module. Add a thin wrapper here that validates, forwards, and
emits telemetry.

When NOT to add a method: read-only access, derived computation, or
anything that doesn't mutate persistent state. Those go through the
store module directly.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from gateway import plugin_registry, todo_store
from gateway.paths import KITTY_TOKEN_LOG_FILE

logger = logging.getLogger("kitty.storage_router")

_TELEMETRY_KIND = "storage_write"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ms_since(start: float) -> float:
    return round((time.monotonic() - start) * 1000.0, 3)


def _emit_telemetry(store: str, op: str, *, key: Any = None, ms: float) -> None:
    """Append one record to the shared token log. Best-effort; never raise."""
    try:
        KITTY_TOKEN_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": _iso_now(),
            "kind": _TELEMETRY_KIND,
            "store": store,
            "op": op,
            "key": str(key) if key is not None else None,
            "ms": ms,
        }
        with KITTY_TOKEN_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("storage_router: telemetry write failed: %s", exc)


# --- Todos ---


def replace_todos(items: list[dict]) -> list[dict]:
    if not isinstance(items, list):
        raise TypeError(f"items must be a list, got {type(items).__name__}")
    start = time.monotonic()
    result = todo_store.update(items)
    _emit_telemetry("todos", "replace", ms=_ms_since(start))
    return result


def add_todo(content: str, status: str = "pending", active_form: str = "") -> dict:
    if not isinstance(content, str):
        raise TypeError(f"content must be str, got {type(content).__name__}")
    if not isinstance(status, str):
        raise TypeError(f"status must be str, got {type(status).__name__}")
    if not isinstance(active_form, str):
        raise TypeError(f"active_form must be str, got {type(active_form).__name__}")
    start = time.monotonic()
    result = todo_store.add(content, status=status, active_form=active_form)
    _emit_telemetry("todos", "add", key=result.get("id"), ms=_ms_since(start))
    return result


def complete_todo(todo_id: int) -> bool:
    if not isinstance(todo_id, int) or isinstance(todo_id, bool):
        raise TypeError(f"todo_id must be int, got {type(todo_id).__name__}")
    start = time.monotonic()
    result = todo_store.complete_by_id(todo_id)
    _emit_telemetry("todos", "complete", key=todo_id, ms=_ms_since(start))
    return result


def delete_todo(todo_id: int) -> bool:
    if not isinstance(todo_id, int) or isinstance(todo_id, bool):
        raise TypeError(f"todo_id must be int, got {type(todo_id).__name__}")
    start = time.monotonic()
    result = todo_store.delete_by_id(todo_id)
    _emit_telemetry("todos", "delete", key=todo_id, ms=_ms_since(start))
    return result


def clear_todos() -> None:
    start = time.monotonic()
    todo_store.clear()
    _emit_telemetry("todos", "clear", ms=_ms_since(start))


# --- Plugin settings ---


def enable_plugin(name: str) -> bool:
    if not isinstance(name, str):
        raise TypeError(f"name must be str, got {type(name).__name__}")
    start = time.monotonic()
    result = plugin_registry.enable(name)
    _emit_telemetry("plugin_settings", "enable", key=name, ms=_ms_since(start))
    return result


def disable_plugin(name: str) -> bool:
    if not isinstance(name, str):
        raise TypeError(f"name must be str, got {type(name).__name__}")
    start = time.monotonic()
    result = plugin_registry.disable(name)
    _emit_telemetry("plugin_settings", "disable", key=name, ms=_ms_since(start))
    return result
