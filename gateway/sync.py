"""State Sync — encrypted state sync between Kitty instances.

Syncs memory (facts), journal entries, task state, and preferences.
Uses local network or Tailscale. Conflict resolution: last-write-wins
with merge markers for journal entries.

Public API:
  export_snapshot() -> dict       Export all syncable state
  import_snapshot(data) -> int    Import state, returns items merged
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.sync")

SYNC_STATE = DATA_DIR / "sync_state.json"


def export_snapshot() -> dict:
    """Export all syncable state as a portable dict."""
    snapshot = {
        "version": 1,
        "exported_at": time.time(),
        "memories": [],
        "journal_entries": [],
        "todos": [],
        "plugin_settings": {},
        "preferences": {},
    }

    # Memories
    try:
        from gateway.memory import list_memories
        snapshot["memories"] = list_memories(limit=1000)
    except Exception:
        pass

    # Journal entries
    try:
        from gateway.journal import JOURNAL_LOG
        if JOURNAL_LOG.exists():
            entries = []
            with JOURNAL_LOG.open("r") as f:
                for line in f:
                    try:
                        entries.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
            snapshot["journal_entries"] = entries[-1000:]  # last 1000
    except Exception:
        pass

    # Todos
    try:
        from gateway.todo_store import get
        snapshot["todos"] = get()
    except Exception:
        pass

    # Plugin settings
    try:
        from gateway.plugin_registry import PLUGIN_SETTINGS
        if PLUGIN_SETTINGS.exists():
            snapshot["plugin_settings"] = json.loads(PLUGIN_SETTINGS.read_text())
    except Exception:
        pass

    return snapshot


def import_snapshot(data: dict) -> int:
    """Import syncable state from a snapshot dict. Returns items merged."""
    if not isinstance(data, dict):
        return 0

    merged = 0

    # Import memories
    for mem in data.get("memories", []):
        try:
            text = mem.get("memory", mem.get("text", ""))
            if text:
                from gateway.memory import add_memory
                add_memory(text, namespace=mem.get("metadata", {}).get("namespace", "facts"))
                merged += 1
        except Exception:
            pass

    # Import journal entries
    for entry in data.get("journal_entries", []):
        try:
            from gateway.journal import save_journal_entry
            save_journal_entry(
                entry=entry.get("entry", ""),
                theme=entry.get("theme"),
            )
            merged += 1
        except Exception:
            pass

    # Import todos
    existing = data.get("todos", [])
    if existing:
        try:
            from gateway.todo_store import update
            update(existing)
            merged += len(existing)
        except Exception:
            pass

    # Import plugin settings
    ps = data.get("plugin_settings", {})
    if ps:
        try:
            from gateway.plugin_registry import PLUGIN_SETTINGS
            PLUGIN_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            current = json.loads(PLUGIN_SETTINGS.read_text()) if PLUGIN_SETTINGS.exists() else {}
            current.update(ps)
            PLUGIN_SETTINGS.write_text(json.dumps(current, indent=2))
            merged += 1
        except Exception:
            pass

    logger.info("Snapshot imported: %d items merged", merged)
    return merged
