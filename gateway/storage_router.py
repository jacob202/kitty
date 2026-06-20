"""Write-side StorageRouter.

Phase B B4: route handlers must not import write functions from concrete
store modules. This module is the single seam for state writes.

Why: the storage substrate is migrating from JSON files to SQLite. If
routes call `todo_store.add()` directly, every future migration means
editing every route. If routes call `storage_router.add_todo()`, the
substrate can change without touching routes.

Reads are intentionally not routed through here. Reads are cheap,
cache-friendly, and used in hot paths; routing them adds an indirection
without buying anything. Reads still go to the store modules directly.

When to add a method: a route handler needs to mutate state owned by
a store module. Add a thin wrapper here that delegates to the store.

When NOT to add a method: read-only access, derived computation, or
anything that doesn't mutate persistent state. Those go through the
store module directly.
"""

from __future__ import annotations

from gateway import plugin_registry, todo_store


# --- Todos ---


def replace_todos(items: list[dict]) -> list[dict]:
    return todo_store.update(items)


def add_todo(content: str, status: str = "pending", active_form: str = "") -> dict:
    return todo_store.add(content, status=status, active_form=active_form)


def complete_todo(todo_id: int) -> bool:
    return todo_store.complete_by_id(todo_id)


def delete_todo(todo_id: int) -> bool:
    return todo_store.delete_by_id(todo_id)


def clear_todos() -> None:
    todo_store.clear()


# --- Plugin settings ---


def enable_plugin(name: str) -> bool:
    return plugin_registry.enable(name)


def disable_plugin(name: str) -> bool:
    return plugin_registry.disable(name)
