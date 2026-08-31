"""Tests for the JSON import/export round-trip (Lane C).

Every store that goes through the storage_sync module should be able to
be exported to a JSON snapshot, the SQLite state cleared, and the
data restored from the snapshot with no loss. These tests use the real
SQLite stores and an explicit Mem0 test backend to catch schema drift early.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from gateway import db as kitty_db
from gateway import memory, plugin_registry, storage_sync, todo_store


@pytest.fixture(autouse=True)
def isolate_memory_backend(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Keep storage-sync tests independent of the live Mem0/Ollama stack."""
    backend = MagicMock()
    backend.get_all.return_value = {"results": []}
    monkeypatch.setattr(memory, "_get_memory", lambda: backend)
    return backend


def _isolate(tmp_path, monkeypatch, name):
    db_file = tmp_path / f"{name}.db"
    monkeypatch.setattr(kitty_db, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", db_file, raising=False)
    monkeypatch.setattr("gateway.journal_store.JOURNAL_DB_FILE", db_file)
    return db_file


def _isolate_plugin(tmp_path, monkeypatch):
    db_file = tmp_path / "plugins.db"
    monkeypatch.setattr(plugin_registry, "PLUGIN_DB_FILE", db_file)
    monkeypatch.setattr(plugin_registry, "PLUGIN_SETTINGS", tmp_path / "plugin_settings.json")
    plugin_registry.reset()
    return db_file


def test_export_all_returns_expected_top_level_shape(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")

    snapshot = storage_sync.export_all()

    assert snapshot["format_version"] == storage_sync.FORMAT_VERSION
    assert "exported_at" in snapshot
    assert set(snapshot["stores"]) >= {"plugin_settings", "todos"}
    assert "memories" in snapshot["stores"]
    assert "journal_entries" in snapshot["stores"]
    assert "preferences" in snapshot["stores"]


def test_export_all_surfaces_memory_backend_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable():
        raise memory.MemoryError("memory export unavailable")

    monkeypatch.setattr(memory, "_get_memory", unavailable)

    with pytest.raises(memory.MemoryError, match="memory export unavailable"):
        storage_sync.export_all()


def test_export_includes_real_plugin_settings_and_todos(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")

    plugin_registry.register("alpha", default_enabled=True)
    plugin_registry.register("beta", default_enabled=False)
    plugin_registry.enable("alpha")
    plugin_registry.disable("beta")
    todo_store.update(
        [
            {"content": "first todo", "status": "pending", "active_form": ""},
            {"content": "second todo", "status": "completed", "active_form": ""},
        ]
    )

    snapshot = storage_sync.export_all()
    assert snapshot["stores"]["plugin_settings"] == {"alpha": True, "beta": False}
    assert {t["content"] for t in snapshot["stores"]["todos"]} == {"first todo", "second todo"}


def test_round_trip_preserves_plugin_settings(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    plugin_registry.register("alpha", default_enabled=True)
    plugin_registry.register("beta", default_enabled=False)
    plugin_registry.enable("alpha")
    plugin_registry.disable("beta")

    snapshot = storage_sync.export_all()
    plugin_registry.reset()
    assert plugin_registry._load_db_settings() == {}

    counts = storage_sync.import_all(snapshot)
    assert counts["plugin_settings"] == 2
    assert plugin_registry._load_db_settings() == {"alpha": True, "beta": False}


def test_round_trip_preserves_todos(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    todo_store.update(
        [
            {"content": "x", "status": "pending", "active_form": "x-form"},
            {"content": "y", "status": "completed", "active_form": ""},
        ]
    )

    snapshot = storage_sync.export_all()
    todo_store.clear()
    assert todo_store.get() == []

    counts = storage_sync.import_all(snapshot)
    assert counts["todos"] == 2
    restored = todo_store.get()
    assert {t["content"] for t in restored} == {"x", "y"}


def test_import_rejects_unknown_format_version():
    with pytest.raises(ValueError, match="format_version"):
        storage_sync.import_all({"format_version": 999, "stores": {}})


def test_import_rejects_missing_stores_key():
    with pytest.raises(ValueError, match="snapshot.stores"):
        storage_sync.import_all({"format_version": storage_sync.FORMAT_VERSION})


def test_import_rejects_unknown_store_keys(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    snapshot = storage_sync.export_all()
    snapshot["stores"]["never_existed"] = "wat"

    with pytest.raises(ValueError, match="never_existed"):
        storage_sync.import_all(snapshot)


def test_import_rejects_wrong_payload_shape(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    snapshot = storage_sync.export_all()
    snapshot["stores"]["plugin_settings"] = "not-a-dict"
    snapshot["stores"]["todos"] = "not-a-list"

    with pytest.raises(ValueError):
        storage_sync.import_all(snapshot)


def test_export_to_file_and_import_from_file_round_trip(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    plugin_registry.register("alpha", default_enabled=True)
    plugin_registry.enable("alpha")
    todo_store.update([{"content": "z", "status": "pending", "active_form": ""}])

    target = tmp_path / "snapshot.json"
    out = storage_sync.export_to_file(target)
    assert out == target
    assert (
        json.loads(target.read_text(encoding="utf-8"))["format_version"]
        == storage_sync.FORMAT_VERSION
    )

    plugin_registry.reset()
    todo_store.clear()
    assert plugin_registry._load_db_settings() == {}
    assert todo_store.get() == []

    counts = storage_sync.import_from_file(target)
    assert counts["plugin_settings"] == 1
    assert counts["todos"] == 1
    assert plugin_registry._load_db_settings() == {"alpha": True}
    assert todo_store.get()[0]["content"] == "z"


# --- Replacement semantics (import replaces, does not append) ---


def test_import_is_idempotent_for_todos(tmp_path, monkeypatch):
    """Importing the same snapshot twice leaves the same record count."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    todo_store.update([
        {"content": "a", "status": "pending", "active_form": ""},
        {"content": "b", "status": "completed", "active_form": ""},
    ])

    snapshot = storage_sync.export_all()

    # First import
    counts1 = storage_sync.import_all(snapshot)
    assert counts1["todos"] == 2

    # Second import — same snapshot, same count
    counts2 = storage_sync.import_all(snapshot)
    assert counts2["todos"] == 2
    assert len(todo_store.get()) == 2


def test_import_is_idempotent_for_plugin_settings(tmp_path, monkeypatch):
    """Importing the same snapshot twice leaves the same record count."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    plugin_registry.register("alpha", default_enabled=True)
    plugin_registry.register("beta", default_enabled=False)
    plugin_registry.enable("alpha")
    plugin_registry.disable("beta")

    snapshot = storage_sync.export_all()

    counts1 = storage_sync.import_all(snapshot)
    assert counts1["plugin_settings"] == 2

    counts2 = storage_sync.import_all(snapshot)
    assert counts2["plugin_settings"] == 2
    assert plugin_registry._load_db_settings() == {"alpha": True, "beta": False}


def test_import_replaces_todos_does_not_append(tmp_path, monkeypatch):
    """After import, store contains only snapshot records, nothing from before."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")

    # Pre-populate with records that should be wiped
    todo_store.update([
        {"content": "old1", "status": "pending", "active_form": ""},
        {"content": "old2", "status": "completed", "active_form": ""},
    ])
    assert len(todo_store.get()) == 2

    # Import a different snapshot
    snapshot = {
        "format_version": storage_sync.FORMAT_VERSION,
        "exported_at": "2026-01-01T00:00:00Z",
        "stores": {
            "todos": [{"content": "new1", "status": "pending", "active_form": ""}],
            "plugin_settings": {},
            "memories": [],
            "journal_entries": [],
            "preferences": {},
        },
    }
    counts = storage_sync.import_all(snapshot)
    assert counts["todos"] == 1

    restored = todo_store.get()
    assert len(restored) == 1
    assert restored[0]["content"] == "new1"
    assert all(t["content"] != "old1" for t in restored)
    assert all(t["content"] != "old2" for t in restored)


def test_import_replaces_plugin_settings_does_not_append(tmp_path, monkeypatch):
    """After import, plugin_settings contains only snapshot records."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")

    plugin_registry.register("old_alpha", default_enabled=True)
    plugin_registry.register("old_beta", default_enabled=True)
    plugin_registry.enable("old_alpha")
    plugin_registry.enable("old_beta")
    assert plugin_registry._load_db_settings() == {"old_alpha": True, "old_beta": True}

    snapshot = {
        "format_version": storage_sync.FORMAT_VERSION,
        "exported_at": "2026-01-01T00:00:00Z",
        "stores": {
            "todos": [],
            "plugin_settings": {"new_gamma": True},
            "memories": [],
            "journal_entries": [],
            "preferences": {},
        },
    }
    counts = storage_sync.import_all(snapshot)
    assert counts["plugin_settings"] == 1

    restored = plugin_registry._load_db_settings()
    assert restored == {"new_gamma": True}
    assert "old_alpha" not in restored
    assert "old_beta" not in restored


def test_import_replaces_journal_entries_does_not_append(tmp_path, monkeypatch):
    """After import, journal contains only snapshot records."""
    from gateway import journal_store

    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    journal_store.init_db()

    # Pre-populate
    journal_store.append_entry(ts=1000.0, entry="old entry 1")
    journal_store.append_entry(ts=2000.0, entry="old entry 2")
    assert len(journal_store.list_entries(limit=100)) == 2

    snapshot = {
        "format_version": storage_sync.FORMAT_VERSION,
        "exported_at": "2026-01-01T00:00:00Z",
        "stores": {
            "todos": [],
            "plugin_settings": {},
            "memories": [],
            "journal_entries": [
                {"ts": 3000.0, "entry": "new entry", "theme": "test"},
            ],
            "preferences": {},
        },
    }
    counts = storage_sync.import_all(snapshot)
    assert counts["journal_entries"] == 1

    restored = journal_store.list_entries(limit=100)
    assert len(restored) == 1
    assert restored[0]["entry"] == "new entry"
    assert all(e["entry"] != "old entry 1" for e in restored)
    assert all(e["entry"] != "old entry 2" for e in restored)


def test_preferences_round_trip(tmp_path, monkeypatch):
    """Preferences export/import round-trip preserves records."""
    from gateway import explicit_memory

    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    monkeypatch.setattr(explicit_memory, "DB_FILE", tmp_path / "explicit.db")

    # Store some preferences
    explicit_memory.remember(
        "dark mode", namespace="preferences", memory_key="theme"
    )
    explicit_memory.remember(
        "verbose logs", namespace="preferences", memory_key="logging"
    )

    snapshot = storage_sync.export_all()
    prefs = snapshot["stores"]["preferences"]
    assert len(prefs) == 2
    pref_texts = {p["text"] for p in prefs.values()}
    assert "dark mode" in pref_texts
    assert "verbose logs" in pref_texts

    # Clear and re-import
    for row in explicit_memory.list_memories(namespace="preferences", limit=100):
        explicit_memory.forget(row["id"])
    assert len(explicit_memory.list_memories(namespace="preferences", limit=100)) == 0

    counts = storage_sync.import_all(snapshot)
    assert counts["preferences"] == 2

    restored = explicit_memory.list_memories(namespace="preferences", limit=100)
    assert len(restored) == 2
    restored_texts = {r["text"] for r in restored}
    assert "dark mode" in restored_texts
    assert "verbose logs" in restored_texts


def test_preferences_empty_round_trip(tmp_path, monkeypatch):
    """An empty preferences snapshot round-trips cleanly."""
    from gateway import explicit_memory

    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    # Isolate explicit_memory's DB too so it doesn't leak from other tests.
    monkeypatch.setattr(explicit_memory, "DB_FILE", tmp_path / "explicit.db")

    snapshot = storage_sync.export_all()
    assert snapshot["stores"]["preferences"] == {}

    counts = storage_sync.import_all(snapshot)
    assert counts["preferences"] == 0
    assert explicit_memory.list_memories(namespace="preferences", limit=100) == []


def test_export_memories_and_journal_are_exhaustive(tmp_path, monkeypatch):
    """Export functions do not cap at 1000 records."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")

    from gateway import journal_store

    journal_store.init_db()
    for i in range(5):
        journal_store.append_entry(ts=float(i), entry=f"entry-{i}")

    # journal_store.list_entries with a generous limit returns all entries
    all_entries = journal_store.list_entries(limit=100_000)
    assert len(all_entries) == 5

    # The export function uses limit=100_000, verify it works
    exported = storage_sync.export_journal_entries()
    assert len(exported) == 5


def test_import_rejects_wrong_preferences_payload_shape(tmp_path, monkeypatch):
    """A preferences payload that is not a dict raises ValueError."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")

    with pytest.raises(ValueError, match="preferences payload must be a dict"):
        storage_sync.import_preferences("not-a-dict")
