"""Tests for DB-backed plugin settings."""

from __future__ import annotations

import json

import pytest

from gateway import db, plugin_registry


def _isolate_plugin_registry(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty.db"
    legacy_file = tmp_path / "plugin_settings.json"
    monkeypatch.setattr(plugin_registry, "PLUGIN_DB_FILE", db_file)
    monkeypatch.setattr(plugin_registry, "PLUGIN_SETTINGS", legacy_file)
    plugin_registry.reset()
    return db_file, legacy_file


def test_plugin_setting_persists_to_sqlite_only(monkeypatch, tmp_path):
    """Phase 1: writes go to kitty.db only. The legacy JSON is not mirrored."""
    db_file, legacy_file = _isolate_plugin_registry(monkeypatch, tmp_path)
    plugin_registry.register("sample", default_enabled=False)

    assert plugin_registry.enable("sample") is True

    with db.connect(db_file) as conn:
        row = conn.execute(
            "SELECT plugin_name, enabled FROM plugin_settings WHERE plugin_name = ?",
            ("sample",),
        ).fetchone()

    assert dict(row) == {"plugin_name": "sample", "enabled": 1}
    assert not legacy_file.exists(), "Phase 1: legacy JSON must not be written"

    plugin_registry._registry = {}
    plugin_registry.register("sample", default_enabled=False)
    assert plugin_registry.is_enabled("sample") is True


def test_legacy_json_is_imported_once_then_ignored(monkeypatch, tmp_path):
    """Phase 1: legacy JSON is read once on first access, then never re-read.

    After the one-shot import, the DB is canonical. Subsequent changes to
    the legacy file are not picked up. The migration flag in app_settings
    ensures the import runs at most once.
    """
    db_file, legacy_file = _isolate_plugin_registry(monkeypatch, tmp_path)
    legacy_file.write_text(json.dumps({"legacy-only": True}), encoding="utf-8")
    plugin_registry.register("legacy-only", default_enabled=False)

    assert plugin_registry.is_enabled("legacy-only") is True
    with db.connect(db_file) as conn:
        row = conn.execute(
            "SELECT enabled FROM plugin_settings WHERE plugin_name = ?",
            ("legacy-only",),
        ).fetchone()
    assert row["enabled"] == 1

    # The flag should now be set, so the legacy file is dead weight.
    with db.connect(db_file) as conn:
        flag = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (plugin_registry._MIGRATION_FLAG,),
        ).fetchone()
    assert flag is not None

    # Mutate the legacy file. The DB is canonical; the change is ignored.
    legacy_file.write_text(json.dumps({"legacy-only": False, "ghost": True}), encoding="utf-8")
    assert plugin_registry.is_enabled("legacy-only") is True
    assert plugin_registry.is_enabled("ghost") is False


def test_legacy_plugin_settings_import_without_deleting_file(monkeypatch, tmp_path):
    db_file, legacy_file = _isolate_plugin_registry(monkeypatch, tmp_path)
    legacy_file.write_text(json.dumps({"legacy": False}), encoding="utf-8")
    plugin_registry.register("legacy", default_enabled=True)

    assert plugin_registry.is_enabled("legacy") is False
    assert legacy_file.exists()
    with db.connect(db_file) as conn:
        row = conn.execute(
            "SELECT enabled FROM plugin_settings WHERE plugin_name = ?",
            ("legacy",),
        ).fetchone()
    assert row["enabled"] == 0


def test_corrupt_legacy_plugin_settings_fail_loud(monkeypatch, tmp_path):
    _db_file, legacy_file = _isolate_plugin_registry(monkeypatch, tmp_path)
    legacy_file.write_text("{not json", encoding="utf-8")
    plugin_registry.register("broken")

    with pytest.raises(RuntimeError) as exc:
        plugin_registry.is_enabled("broken")

    assert str(legacy_file) in str(exc.value)
