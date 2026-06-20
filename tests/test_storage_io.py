"""Tests for the JSON import/export round-trip (Lane C).

Every store that goes through the storage_io module should be able to
be exported to a JSON snapshot, the SQLite state cleared, and the
data restored from the snapshot with no loss. These tests use the
real store modules (not mocks) to catch schema drift early.
"""

from __future__ import annotations

import json

import pytest

from gateway import plugin_registry, storage_io, todo_store
from gateway import db as kitty_db
from gateway.paths import DATA_DIR


def _isolate(tmp_path, monkeypatch, name):
    db_file = tmp_path / f"{name}.db"
    monkeypatch.setattr(kitty_db, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", db_file, raising=False)
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

    snapshot = storage_io.export_all()

    assert snapshot["format_version"] == storage_io.FORMAT_VERSION
    assert "exported_at" in snapshot
    assert set(snapshot["stores"]) == {"plugin_settings", "todos"}


def test_export_includes_real_plugin_settings_and_todos(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")

    plugin_registry.register("alpha", default_enabled=True)
    plugin_registry.register("beta", default_enabled=False)
    plugin_registry.enable("alpha")
    plugin_registry.disable("beta")
    todo_store.update([
        {"content": "first todo", "status": "pending", "active_form": ""},
        {"content": "second todo", "status": "completed", "active_form": ""},
    ])

    snapshot = storage_io.export_all()
    assert snapshot["stores"]["plugin_settings"] == {"alpha": True, "beta": False}
    assert {t["content"] for t in snapshot["stores"]["todos"]} == {"first todo", "second todo"}


def test_round_trip_preserves_plugin_settings(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    plugin_registry.register("alpha", default_enabled=True)
    plugin_registry.register("beta", default_enabled=False)
    plugin_registry.enable("alpha")
    plugin_registry.disable("beta")

    snapshot = storage_io.export_all()
    plugin_registry.reset()
    assert plugin_registry._load_db_settings() == {}

    counts = storage_io.import_all(snapshot)
    assert counts["plugin_settings"] == 2
    assert plugin_registry._load_db_settings() == {"alpha": True, "beta": False}


def test_round_trip_preserves_todos(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    todo_store.update([
        {"content": "x", "status": "pending", "active_form": "x-form"},
        {"content": "y", "status": "completed", "active_form": ""},
    ])

    snapshot = storage_io.export_all()
    todo_store.clear()
    assert todo_store.get() == []

    counts = storage_io.import_all(snapshot)
    assert counts["todos"] == 2
    restored = todo_store.get()
    assert {t["content"] for t in restored} == {"x", "y"}


def test_import_rejects_unknown_format_version():
    with pytest.raises(ValueError, match="format_version"):
        storage_io.import_all({"format_version": 999, "stores": {}})


def test_import_rejects_missing_stores_key():
    with pytest.raises(ValueError, match="snapshot.stores"):
        storage_io.import_all({"format_version": storage_io.FORMAT_VERSION})


def test_import_rejects_unknown_store_keys(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    snapshot = storage_io.export_all()
    snapshot["stores"]["never_existed"] = "wat"

    with pytest.raises(ValueError, match="never_existed"):
        storage_io.import_all(snapshot)


def test_import_rejects_wrong_payload_shape(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    snapshot = storage_io.export_all()
    snapshot["stores"]["plugin_settings"] = "not-a-dict"
    snapshot["stores"]["todos"] = "not-a-list"

    with pytest.raises(ValueError, match="plugin_settings"):
        storage_io.import_all(snapshot)


def test_export_to_file_and_import_from_file_round_trip(tmp_path, monkeypatch):
    _isolate_plugin(tmp_path, monkeypatch)
    _isolate(tmp_path, monkeypatch, "todo")
    plugin_registry.register("alpha", default_enabled=True)
    plugin_registry.enable("alpha")
    todo_store.update([{"content": "z", "status": "pending", "active_form": ""}])

    target = tmp_path / "snapshot.json"
    out = storage_io.export_to_file(target)
    assert out == target
    assert json.loads(target.read_text(encoding="utf-8"))["format_version"] == storage_io.FORMAT_VERSION

    plugin_registry.reset()
    todo_store.clear()
    assert plugin_registry._load_db_settings() == {}
    assert todo_store.get() == []

    counts = storage_io.import_from_file(target)
    assert counts["plugin_settings"] == 1
    assert counts["todos"] == 1
    assert plugin_registry._load_db_settings() == {"alpha": True}
    assert todo_store.get()[0]["content"] == "z"
