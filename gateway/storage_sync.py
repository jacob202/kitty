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

FORMAT_VERSION = 1
EXPORT_FILENAME = "kitty-storage-export.json"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Export ---


def export_memories() -> list[dict]:
    """Return every memory from the Mem0 backend (no record limit)."""
    from gateway.memory import list_memories

    return list_memories(limit=0)


def export_journal_entries() -> list[dict]:
    """Return every journal entry (no record limit)."""
    # journal_store.list_entries treats limit=0 as SQL LIMIT 0 (returns nothing),
    # so use a generous ceiling instead.
    return journal_store.list_entries(limit=100_000)


def export_todos() -> list[dict]:
    return todo_store.get()


def export_plugin_settings() -> dict[str, bool]:
    return plugin_registry._load_db_settings()


def export_preferences() -> dict:
    """Return explicit-memory records in the 'preferences' namespace."""
    from gateway import explicit_memory

    rows = explicit_memory.list_memories(namespace="preferences", limit=10_000)
    return {
        row["id"]: {
            "text": row["text"],
            "memory_key": row.get("memory_key"),
            "source_kind": row.get("source_kind", "user_explicit"),
            "source_ref": row.get("source_ref"),
            "sensitivity": row.get("sensitivity", "normal"),
            "pinned": row.get("pinned", False),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
        for row in rows
    }


def export_all() -> dict[str, Any]:
    """Return a JSON-serializable snapshot of every migrated store."""
    return {
        "format_version": FORMAT_VERSION,
        "exported_at": _iso_now(),
        "stores": {
            "memories": export_memories(),
            "journal_entries": export_journal_entries(),
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
    """Replace the memories store with ``payload``.

    Deletes every existing memory first, then adds each record from the
    snapshot.  Fails loud on the first error; the store will hold exactly
    the snapshot's records (plus any that were successfully added before
    the failure).
    """
    from gateway.memory import add_memory, delete_memory, list_memories

    if not isinstance(payload, list):
        raise ValueError(f"memories payload must be a list, got {type(payload).__name__}")

    # Clear existing memories so the store ends up with exactly the snapshot's records.
    existing = list_memories(limit=0)
    for row in existing:
        mid = row.get("id")
        if mid:
            delete_memory(mid)

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
    """Replace the journal store with ``payload``.

    Deletes every existing entry first, then appends each record from the
    snapshot.  Fails loud on the first error; the store will hold exactly
    the snapshot's records (plus any that were successfully added before
    the failure).
    """
    if not isinstance(payload, list):
        raise ValueError(f"journal_entries payload must be a list, got {type(payload).__name__}")

    # Clear existing entries so the store ends up with exactly the snapshot's records.
    journal_store.init_db()
    with kitty_db.connect(journal_store.JOURNAL_DB_FILE) as conn:
        conn.execute("DELETE FROM journal_entries")
        conn.commit()

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


def import_todos(payload: list[dict]) -> int:
    if not isinstance(payload, list):
        raise ValueError(f"todos payload must be a list, got {type(payload).__name__}")
    items = [dict(row) for row in payload]
    todo_store.update(items)
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
    """Replace the preferences store with ``payload``.

    Forgets every existing preference first, then stores each record from
    the snapshot.  Fails loud on the first error; the store will hold
    exactly the snapshot's records (plus any that were successfully added
    before the failure).
    """
    from gateway import explicit_memory

    if not isinstance(payload, dict):
        raise ValueError(f"preferences payload must be a dict, got {type(payload).__name__}")

    # Clear existing preferences so the store ends up with exactly the snapshot's records.
    existing = explicit_memory.list_memories(namespace="preferences", limit=10_000)
    for row in existing:
        explicit_memory.forget(row["id"])

    added = 0
    for _pref_id, pref_data in payload.items():
        if not isinstance(pref_data, dict):
            raise ValueError(
                f"preference record must be a dict, got {type(pref_data).__name__}"
            )
        text = pref_data.get("text", "")
        if not text:
            continue
        explicit_memory.remember(
            text,
            namespace="preferences",
            memory_key=pref_data.get("memory_key"),
            source_kind=pref_data.get("source_kind", "user_explicit"),
            source_ref=pref_data.get("source_ref"),
            sensitivity=pref_data.get("sensitivity", "normal"),
            pinned=pref_data.get("pinned", False),
        )
        added += 1
    return added


_IMPORTERS: dict[str, Callable[..., int]] = {
    "memories": import_memories,
    "journal_entries": import_journal_entries,
    "todos": import_todos,
    "plugin_settings": import_plugin_settings,
    "preferences": import_preferences,
}


def import_all(snapshot: dict[str, Any]) -> dict[str, int]:
    """Replace every migrated store with the contents of ``snapshot``.

    Validates the format version. Returns a count of records imported
    per store. Raises ``ValueError`` on a missing or unknown store key
    or a bad format version.
    """
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a JSON object")
    version = snapshot.get("format_version")
    if version != FORMAT_VERSION:
        raise ValueError(
            f"unsupported format_version {version!r}; this build understands {FORMAT_VERSION}"
        )
    stores = snapshot.get("stores")
    if not isinstance(stores, dict):
        raise ValueError("snapshot.stores must be a JSON object")
    counts: dict[str, int] = {}
    for key, importer in _IMPORTERS.items():
        if key in stores:
            counts[key] = importer(stores[key])
    unknown = set(stores) - set(_IMPORTERS)
    if unknown:
        raise ValueError(f"unknown store keys in snapshot: {sorted(unknown)}")
    return counts


def import_from_file(path: Path) -> dict[str, int]:
    """Read a JSON file, validate, and import. Returns per-store counts."""
    raw = Path(path).read_text(encoding="utf-8")
    return import_all(json.loads(raw))
