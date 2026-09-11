"""JSON import/export for the migrated SQLite stores.

Phase 1 deepening: this module merges the previous ``storage_io`` and ``sync``
modules. The shape wins from ``storage_io`` (versioned, ``format_version`` +
``stores`` dict), the additional stores (``memories``, ``journal_entries``,
``preferences``) come from ``sync``. ``gateway/sync.py`` has been deleted.

Use this module for:
  - Manual backup before a destructive operation
  - Restore from a known-good snapshot
  - Migrating a legacy single-file store into the new SQLite seam
  - Exporting user data on demand

This is NOT a second active runtime source of truth — nothing should be
reading or writing these JSON files at request time. SQLite is canonical.

The contract: every store is representable as a JSON object with a top-level
``"stores"`` dict, one entry per store, each entry is a JSON value
appropriate to that store. Bump ``FORMAT_VERSION`` when the shape changes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from gateway import db as kitty_db
from gateway import journal_store, plugin_registry, todo_store
from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.storage_sync")

FORMAT_VERSION = 2
# Every earlier version stays importable: the v1 -> v2 change only added the
# `projects` store, so an existing backup must not become un-restorable after a
# later bump. A v1 snapshot simply cannot carry user-created projects, so a todo
# owned by one fails loud rather than silently losing its owner.
_ACCEPTED_FORMAT_VERSIONS = frozenset(range(1, FORMAT_VERSION + 1))
EXPORT_FILENAME = "kitty-storage-export.json"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Export ---


def export_memories() -> list[dict]:
    from gateway.memory import list_memories

    return list_memories(limit=1000)


def export_journal_entries() -> list[dict]:
    return journal_store.list_entries(limit=1000)


def export_todos() -> list[dict]:
    return todo_store.get()


def export_projects() -> list[dict]:
    from gateway import project_store

    return project_store.list_projects()


def export_plugin_settings() -> dict[str, bool]:
    return plugin_registry._load_db_settings()


def export_preferences() -> dict:
    """Preferences store. Currently a placeholder; reserved for future use."""
    return {}


def export_all() -> dict[str, Any]:
    """Return a JSON-serializable snapshot of every migrated store."""
    return {
        "format_version": FORMAT_VERSION,
        "exported_at": _iso_now(),
        "stores": {
            "memories": export_memories(),
            "journal_entries": export_journal_entries(),
            "projects": export_projects(),
            "todos": export_todos(),
            "plugin_settings": export_plugin_settings(),
            "preferences": export_preferences(),
        },
    }


def export_to_file(path: Path | None = None) -> Path:
    """Write the current snapshot to a JSON file. Returns the path."""
    target = Path(path) if path is not None else DATA_DIR / EXPORT_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot = export_all()
    target.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return target


# --- Import ---


def import_memories(payload: list[dict]) -> int:
    from gateway.memory import add_memory

    if not isinstance(payload, list):
        raise ValueError(f"memories payload must be a list, got {type(payload).__name__}")
    added = 0
    for record in payload:
        if not isinstance(record, dict):
            raise ValueError(f"memory record must be a dict, got {type(record).__name__}")
        text = record.get("memory") or record.get("text") or ""
        if not text:
            continue
        namespace = (
            record.get("namespace") or (record.get("metadata") or {}).get("namespace") or "facts"
        )
        add_memory(text, namespace=namespace)
        added += 1
    return added


def import_journal_entries(payload: list[dict]) -> int:
    if not isinstance(payload, list):
        raise ValueError(f"journal_entries payload must be a list, got {type(payload).__name__}")
    added = 0
    for record in payload:
        if not isinstance(record, dict):
            raise ValueError(f"journal record must be a dict, got {type(record).__name__}")
        entry_text = record.get("entry", "")
        if not entry_text:
            continue
        theme = record.get("theme")
        session_id = record.get("session_id")
        ts = record.get("ts")
        if isinstance(ts, (int, float)):
            journal_store.append_entry(
                ts=float(ts),
                entry=entry_text,
                theme=theme,
                session_id=session_id,
            )
        else:
            import time as _time
            journal_store.append_entry(
                ts=_time.time(),
                entry=entry_text,
                theme=theme,
                session_id=session_id,
            )
        added += 1
    return added


def import_projects(payload: list[dict]) -> int:
    from gateway import project_store

    if not isinstance(payload, list):
        raise ValueError(f"projects payload must be a list, got {type(payload).__name__}")
    items = [dict(row) for row in payload]
    try:
        return project_store.restore(items)
    except project_store.ProjectError as exc:
        raise ValueError(str(exc)) from exc


def import_todos(payload: list[dict]) -> int:
    if not isinstance(payload, list):
        raise ValueError(f"todos payload must be a list, got {type(payload).__name__}")
    items = [dict(row) for row in payload]
    todo_store.restore(items)
    return len(items)


def import_plugin_settings(payload: dict[str, bool]) -> int:
    if not isinstance(payload, dict):
        raise ValueError(f"plugin_settings payload must be a dict, got {type(payload).__name__}")
    cleaned = {str(name): bool(enabled) for name, enabled in payload.items()}
    with kitty_db.connect(plugin_registry.PLUGIN_DB_FILE) as conn:
        conn.execute("DELETE FROM plugin_settings")
        rows = [(name, 1 if enabled else 0) for name, enabled in sorted(cleaned.items())]
        conn.executemany(
            "INSERT INTO plugin_settings (plugin_name, enabled) VALUES (?, ?)",
            rows,
        )
    return len(cleaned)


def import_preferences(payload: dict) -> int:
    """Preferences store. Currently a no-op (reserved)."""
    if not isinstance(payload, dict):
        raise ValueError(f"preferences payload must be a dict, got {type(payload).__name__}")
    return len(payload)


_IMPORTERS: dict[str, Callable[..., int]] = {
    "memories": import_memories,
    "journal_entries": import_journal_entries,
    # Projects must land before todos: todo_store.restore() validates every
    # todo's project_id against the destination projects table, so a todo
    # owned by a user-created project can only round-trip if that project is
    # materialized first.
    "projects": import_projects,
    "todos": import_todos,
    "plugin_settings": import_plugin_settings,
    "preferences": import_preferences,
}


def _validate_snapshot_references(stores: dict[str, Any]) -> None:
    """Reject a snapshot whose todos reference projects it does not carry.

    A v1 snapshot has no ``projects`` store at all, so it is skipped here and
    ``todo_store.restore`` alone validates its todos against the destination.
    A snapshot that does carry ``projects`` must be self-consistent: its todos
    may only reference projects in that same snapshot.
    """
    projects = stores.get("projects")
    todos = stores.get("todos")
    if not isinstance(projects, list) or not isinstance(todos, list):
        return
    project_ids: set[int] = set()
    for item in projects:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("id")
        if isinstance(raw_id, int) and not isinstance(raw_id, bool):
            project_ids.add(raw_id)
    missing: set[int] = set()
    for item in todos:
        if not isinstance(item, dict):
            continue
        raw_project = item.get("project_id")
        if (
            isinstance(raw_project, int)
            and not isinstance(raw_project, bool)
            and raw_project not in project_ids
        ):
            missing.add(raw_project)
    if missing:
        raise ValueError(
            "snapshot todos reference project ids absent from snapshot projects: "
            f"{sorted(missing)}"
        )


def import_all(snapshot: dict[str, Any]) -> dict[str, int]:
    """Replace every migrated store with the contents of ``snapshot``.

    Validates the format version. Returns a count of records imported
    per store. Raises ``ValueError`` on a missing or unknown store key
    or a bad format version.
    """
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a JSON object")
    version = snapshot.get("format_version")
    if version not in _ACCEPTED_FORMAT_VERSIONS:
        raise ValueError(
            f"unsupported format_version {version!r}; this build understands "
            f"{sorted(_ACCEPTED_FORMAT_VERSIONS)}"
        )
    stores = snapshot.get("stores")
    if not isinstance(stores, dict):
        raise ValueError("snapshot.stores must be a JSON object")
    unknown = set(stores) - set(_IMPORTERS)
    if unknown:
        raise ValueError(f"unknown store keys in snapshot: {sorted(unknown)}")
    # Fail before writing anything when the snapshot is internally inconsistent,
    # rather than importing earlier stores and then aborting at todos.
    _validate_snapshot_references(stores)
    counts: dict[str, int] = {}
    for key, importer in _IMPORTERS.items():
        if key in stores:
            counts[key] = importer(stores[key])
    return counts


def import_from_file(path: Path) -> dict[str, int]:
    """Read a JSON file, validate, and import. Returns per-store counts."""
    raw = Path(path).read_text(encoding="utf-8")
    return import_all(json.loads(raw))
