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
from gateway import memory, plugin_registry, project_store, storage_sync, todo_store


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
    monkeypatch.setattr(project_store, "PROJECTS_DB_FILE", db_file, raising=False)
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


def test_snapshot_import_replaces_omitted_selected_todo_and_clears_dangling_pointer(
    tmp_path, monkeypatch
):
    """Snapshot restore is exact replacement, not generated-list reconciliation."""
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    project_store.init_db()
    project = project_store.create(name="job-search", kind="admin")
    current = todo_store.update(
        [
            {"content": "Chosen current action"},
            {"content": "Also current"},
        ]
    )
    project_store.select_todo(project["id"], current[0]["id"])

    # Restoring an older snapshot that does not contain the currently selected
    # row must not smuggle that newer row into the restored state.
    storage_sync.import_todos(
        [
            {
                "id": 9001,
                "content": "Only snapshot todo",
                "status": "pending",
                "active_form": "",
                "sort_order": 0,
                "progress_note": None,
                "project_id": None,
                "created_at": 10.0,
                "updated_at": 11.0,
            }
        ]
    )

    restored = todo_store.get()
    assert [row["content"] for row in restored] == ["Only snapshot todo"]
    assert project_store.get(project["id"])["selected_todo_id"] is None


def test_snapshot_import_rejects_duplicate_sort_orders_before_replacing_todos(
    tmp_path, monkeypatch
):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    todo_store.update([{"content": "Keep current state"}])
    before = todo_store.get()

    with pytest.raises(todo_store.TodoStoreError, match="duplicate sort_order 4"):
        storage_sync.import_todos(
            [
                {"content": "First snapshot todo", "sort_order": 4},
                {"content": "Second snapshot todo", "sort_order": 4},
            ]
        )

    assert todo_store.get() == before


def test_snapshot_import_rejects_missing_project_owner_before_replacing_todos(
    tmp_path, monkeypatch
):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    todo_store.update([{"content": "Keep current state"}])
    before = todo_store.get()
    missing_project_id = (
        max(project["id"] for project in project_store.list_projects()) + 100
    )

    with pytest.raises(
        todo_store.TodoStoreError,
        match=rf"unknown project_id.*{missing_project_id}",
    ):
        storage_sync.import_todos(
            [
                {
                    "content": "Snapshot todo with a missing owner",
                    "sort_order": 0,
                    "project_id": missing_project_id,
                }
            ]
        )

    assert todo_store.get() == before


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
