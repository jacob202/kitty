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


def export_projects_and_todos() -> tuple[list[dict], list[dict]]:
    """Read Projects and Todos as one coherent snapshot.

    A project's ``selected_todo_id`` and a todo's owning ``project_id`` are one
    cross-table state. Reading them through separate connections can capture a
    selection or reassignment that landed between the two reads, exporting a
    state that never existed — and importing it would silently restore without
    the user's chosen action. One deferred read transaction sees a single WAL
    snapshot of both tables and does not block writers.
    """
    from gateway import project_store

    if Path(project_store.PROJECTS_DB_FILE).resolve() != Path(todo_store.TODO_DB_FILE).resolve():
        raise ValueError(
            "cannot export projects and todos coherently while the project and "
            "todo stores are separate databases"
        )
    project_store.init_db()
    todo_store.init_db()
    with kitty_db.connect(todo_store.TODO_DB_FILE) as conn:
        conn.execute("BEGIN")
        projects = [
            project_store._row_to_project(row)
            for row in conn.execute(
                f"SELECT {project_store._COLUMNS} FROM projects ORDER BY id ASC"
            ).fetchall()
        ]
        todos = [
            todo_store._row_to_dict(row)
            for row in conn.execute(
                "SELECT id, content, status, active_form, sort_order, progress_note, "
                "project_id, created_at, updated_at FROM todos ORDER BY sort_order ASC"
            ).fetchall()
        ]
    return projects, todos


def export_plugin_settings() -> dict[str, bool]:
    return plugin_registry._load_db_settings()


def export_preferences() -> dict:
    """Preferences store. Currently a placeholder; reserved for future use."""
    return {}


def export_all() -> dict[str, Any]:
    """Return a JSON-serializable snapshot of every migrated store."""
    projects, todos = export_projects_and_todos()
    return {
        "format_version": FORMAT_VERSION,
        "exported_at": _iso_now(),
        "stores": {
            "memories": export_memories(),
            "journal_entries": export_journal_entries(),
            "projects": projects,
            "todos": todos,
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

_REQUIRED_PAYLOAD_TYPES: dict[str, type] = {
    "memories": list,
    "journal_entries": list,
    "projects": list,
    "todos": list,
    "plugin_settings": dict,
    "preferences": dict,
}


def _validate_snapshot_payloads(stores: dict[str, Any]) -> None:
    """Reject a wrongly-shaped store payload before any store is written.

    ``_IMPORTERS`` writes in declaration order, so a payload shape error raised
    by a later importer would otherwise follow successful writes by earlier
    ones. Every importer's top-level shape check is therefore applied up front.
    """
    for key, expected in _REQUIRED_PAYLOAD_TYPES.items():
        if key not in stores:
            continue
        payload = stores[key]
        if not isinstance(payload, expected):
            raise ValueError(
                f"{key} payload must be a {expected.__name__}, "
                f"got {type(payload).__name__}"
            )


def _validate_snapshot_references(stores: dict[str, Any]) -> None:
    """Reject an un-restorable snapshot before any store is written.

    ``_IMPORTERS`` restores memories, journal entries, and projects ahead of
    todos, so a todo payload that only fails inside ``todo_store.restore`` would
    leave those earlier stores committed against a rejected snapshot. Every
    precondition restore enforces is therefore checked here first.

    The cross-store reference check needs a ``projects`` store. A v1 snapshot
    has none, so its todos are validated only for internal shape here and are
    checked against the destination by ``todo_store.restore`` instead.
    """
    todos = stores.get("todos")
    if todos is None:
        return
    if not isinstance(todos, list):
        raise ValueError(f"todos payload must be a list, got {type(todos).__name__}")

    projects = stores.get("projects")
    project_ids: set[int] | None = None
    if isinstance(projects, list):
        project_ids = set()
        for item in projects:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            if isinstance(raw_id, int) and not isinstance(raw_id, bool):
                project_ids.add(raw_id)

    seen_ids: set[int] = set()
    seen_sort_orders: set[int] = set()
    missing: set[int] = set()
    for position, item in enumerate(todos):
        if not isinstance(item, dict):
            raise ValueError(
                f"snapshot todo record must be a JSON object, got {type(item).__name__}"
            )
        raw_id = item.get("id")
        if raw_id is not None:
            if not isinstance(raw_id, int) or isinstance(raw_id, bool):
                raise ValueError("snapshot todo id must be an integer or null")
            if raw_id in seen_ids:
                raise ValueError(f"duplicate todo id {raw_id} in snapshot")
            seen_ids.add(raw_id)
        raw_order = item.get("sort_order", position)
        sort_order = (
            raw_order
            if isinstance(raw_order, int) and not isinstance(raw_order, bool)
            else position
        )
        if sort_order in seen_sort_orders:
            raise ValueError(
                f"cannot restore todos with duplicate sort_order {sort_order}"
            )
        seen_sort_orders.add(sort_order)
        raw_project = item.get("project_id")
        if raw_project is None:
            continue
        if not isinstance(raw_project, int) or isinstance(raw_project, bool):
            raise ValueError("snapshot todo project_id must be an integer or null")
        if project_ids is not None and raw_project not in project_ids:
            missing.add(raw_project)
    if missing:
        raise ValueError(
            "snapshot todos reference project ids absent from snapshot projects: "
            f"{sorted(missing)}"
        )
    if project_ids is None:
        # No projects store means the destination keeps its own rows, so an
        # owner can only be validated against this database.
        _validate_todo_owners_against_destination(todos)


def _validate_todo_owners_against_destination(todos: list[Any]) -> None:
    """Reject snapshot todos whose owner does not exist in this database.

    A v1 snapshot carries no ``projects`` store, so the cross-store check above
    cannot see its owners and ``todo_store.restore`` would be the first to
    notice — after Memories and Journal are already committed. Checking the
    destination here fails the whole snapshot before any write.
    """
    referenced: set[int] = set()
    for item in todos:
        if not isinstance(item, dict):
            continue
        raw_project = item.get("project_id")
        if isinstance(raw_project, int) and not isinstance(raw_project, bool):
            referenced.add(raw_project)
    if not referenced:
        return
    from gateway import project_store

    available = {project["id"] for project in project_store.list_projects()}
    missing = sorted(referenced - available)
    if missing:
        raise ValueError(
            "snapshot todos reference project ids absent from the destination: "
            f"{missing}"
        )


def _validate_memories(payload: list[Any]) -> None:
    """Reject memory records the importer cannot accept.

    Memories live in an external backend that cannot share one transaction with
    the SQLite stores, so a record that fails mid-import cannot be rolled back.
    The importer's only shape failure is a non-dict record; the text is read
    defensively, so anything else is the backend's own outage, not the
    snapshot's.
    """
    for record in payload:
        if not isinstance(record, dict):
            raise ValueError(f"memory record must be a dict, got {type(record).__name__}")
        for field in ("memory", "text"):
            value = record.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"memory {field} must be a string")


def _validate_real_writes(stores: dict[str, Any]) -> None:
    """Dry-run every store that writes before a later one could fail.

    ``_IMPORTERS`` runs Memories, Journal, Projects, Todos, then plugin
    settings. Hand-written type checks cannot stay in step with what the real
    statements accept, so each owning store is asked to execute its own write
    path in a transaction that is always rolled back. Any failure rejects the
    whole snapshot before a single row is committed.
    """
    from gateway import journal_store, project_store, todo_store

    memories = stores.get("memories")
    if isinstance(memories, list):
        _reject_if_unrestorable("memories", lambda: _validate_memories(memories))

    journal_entries = stores.get("journal_entries")
    if isinstance(journal_entries, list):
        _reject_if_unrestorable(
            "journal_entries",
            lambda: journal_store.validate_records(journal_entries),
        )

    projects = stores.get("projects")
    if isinstance(projects, list):
        _reject_if_unrestorable(
            "projects", lambda: project_store.validate_restore(projects)
        )

    todos = stores.get("todos")
    if isinstance(todos, list):
        future_ids = None
        if isinstance(projects, list):
            future_ids = frozenset(
                item["id"]
                for item in projects
                if isinstance(item, dict)
                and isinstance(item.get("id"), int)
                and not isinstance(item.get("id"), bool)
            )
        _reject_if_unrestorable(
            "todos",
            lambda: todo_store.validate_restore(todos, future_project_ids=future_ids),
        )


def _reject_if_unrestorable(name: str, validate: Callable[[], None]) -> None:
    """Turn any dry-run failure into the snapshot rejection the caller expects."""
    try:
        validate()
    except Exception as exc:
        # Any non-snapshot exception is still the caller's reject signal, but
        # the original failure stays attached as the cause.
        raise ValueError(f"snapshot {name} cannot be restored: {exc}") from exc


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
    # rather than importing earlier stores and then aborting at a later one.
    _validate_snapshot_payloads(stores)
    _validate_snapshot_references(stores)
    _validate_real_writes(stores)
    counts: dict[str, int] = {}
    for key, importer in _IMPORTERS.items():
        if key in stores:
            counts[key] = importer(stores[key])
    return counts


def import_from_file(path: Path) -> dict[str, int]:
    """Read a JSON file, validate, and import. Returns per-store counts."""
    raw = Path(path).read_text(encoding="utf-8")
    return import_all(json.loads(raw))
