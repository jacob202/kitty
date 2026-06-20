"""JSON import/export for the migrated SQLite stores.

Lane C: Phase B consolidation. SQLite is the canonical runtime store.
This module provides a JSON round-trip for backup, restore, and legacy
import/export. It is NOT a second active runtime source of truth —
nothing should be reading or writing these JSON files at request
time. Use this for:

  - Manual backup before a destructive operation
  - Restore from a known-good snapshot
  - Migrating a legacy single-file store into the new SQLite seam
  - Exporting user data on demand

The contract is: every store is representable as a JSON object with a
top-level "stores" dict, one entry per store, each entry is a JSON
value appropriate to that store (object for keyed stores, list of
records for list stores). Versioning is the responsibility of the
caller — bump ``format_version`` when the shape changes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway import plugin_registry, todo_store
from gateway.paths import DATA_DIR


FORMAT_VERSION = 1
EXPORT_FILENAME = "kitty-storage-export.json"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def export_plugin_settings() -> dict[str, bool]:
    return plugin_registry._load_db_settings()


def export_todos() -> list[dict]:
    return todo_store.get()


def export_all() -> dict[str, Any]:
    """Return a JSON-serializable snapshot of every migrated store."""
    return {
        "format_version": FORMAT_VERSION,
        "exported_at": _iso_now(),
        "stores": {
            "plugin_settings": export_plugin_settings(),
            "todos": export_todos(),
        },
    }


def export_to_file(path: Path | None = None) -> Path:
    """Write the current snapshot to a JSON file. Returns the path."""
    target = Path(path) if path is not None else DATA_DIR / EXPORT_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot = export_all()
    target.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return target


def import_plugin_settings(payload: dict[str, bool]) -> int:
    """Replace the plugin_settings table with ``payload``. Returns count."""
    if not isinstance(payload, dict):
        raise ValueError(f"plugin_settings payload must be a dict, got {type(payload).__name__}")
    cleaned = {str(name): bool(enabled) for name, enabled in payload.items()}
    with plugin_registry.kitty_db.connect(plugin_registry.PLUGIN_DB_FILE) as conn:
        conn.execute("DELETE FROM plugin_settings")
        rows = [(name, 1 if enabled else 0) for name, enabled in sorted(cleaned.items())]
        conn.executemany(
            "INSERT INTO plugin_settings (plugin_name, enabled) VALUES (?, ?)",
            rows,
        )
    return len(cleaned)


def import_todos(payload: list[dict]) -> int:
    """Replace the todos table with ``payload``. Returns count."""
    if not isinstance(payload, list):
        raise ValueError(f"todos payload must be a list, got {type(payload).__name__}")
    items = [dict(row) for row in payload]
    todo_store.update(items)
    return len(items)


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
    if "plugin_settings" in stores:
        counts["plugin_settings"] = import_plugin_settings(stores["plugin_settings"])
    if "todos" in stores:
        counts["todos"] = import_todos(stores["todos"])
    unknown = set(stores) - set(counts)
    if unknown:
        raise ValueError(f"unknown store keys in snapshot: {sorted(unknown)}")
    return counts


def import_from_file(path: Path) -> dict[str, int]:
    """Read a JSON file, validate, and import. Returns per-store counts."""
    raw = Path(path).read_text(encoding="utf-8")
    return import_all(json.loads(raw))
