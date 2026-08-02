"""Tests for the local Kitty data backup drill."""

from __future__ import annotations

import json
import shutil
import sqlite3

import pytest

from gateway.paths import DATA_DIR, KITTY_DATA_DIR
from scripts import kitty_backup


def test_create_backup_copies_files_and_sqlite_db(tmp_path):
    source = tmp_path / "data" / "kitty"
    source.mkdir(parents=True)
    (source / "note.txt").write_text("hello", encoding="utf-8")
    db_file = source / "kitty.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE sample (name TEXT)")
        conn.execute("INSERT INTO sample (name) VALUES ('stored')")

    backup = kitty_backup.create_backup(
        source_dir=source,
        backup_root=tmp_path / "data" / "backups" / "kitty",
        timestamp="20260620T120000Z",
    )

    assert (backup / "note.txt").read_text(encoding="utf-8") == "hello"
    with sqlite3.connect(backup / "kitty.db") as conn:
        row = conn.execute("SELECT name FROM sample").fetchone()
    assert row == ("stored",)
    manifest = json.loads((backup / "backup_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"] == str(source)
    assert "kitty.db" in manifest["files"]


def test_create_backup_fails_when_source_missing(tmp_path):
    source = tmp_path / "missing"

    with pytest.raises(RuntimeError) as exc:
        kitty_backup.create_backup(source_dir=source, backup_root=tmp_path / "backups")

    assert str(source) in str(exc.value)


def test_create_backup_fails_when_destination_exists(tmp_path):
    source = tmp_path / "data" / "kitty"
    source.mkdir(parents=True)
    backup_root = tmp_path / "backups"
    (backup_root / "20260620T120000Z").mkdir(parents=True)

    with pytest.raises(RuntimeError) as exc:
        kitty_backup.create_backup(
            source_dir=source,
            backup_root=backup_root,
            timestamp="20260620T120000Z",
        )

    assert str(backup_root / "20260620T120000Z") in str(exc.value)


def test_restore_drill_copies_backup_into_new_directory(tmp_path):
    backup = tmp_path / "backup"
    backup.mkdir()
    (backup / "note.txt").write_text("hello", encoding="utf-8")
    target = tmp_path / "restore" / "kitty"

    restored = kitty_backup.restore_drill(backup_dir=backup, restore_dir=target)

    assert restored == target
    assert (target / "note.txt").read_text(encoding="utf-8") == "hello"


def test_restore_drill_refuses_existing_target(tmp_path):
    backup = tmp_path / "backup"
    backup.mkdir()
    target = tmp_path / "restore"
    target.mkdir()

    with pytest.raises(RuntimeError) as exc:
        kitty_backup.restore_drill(backup_dir=backup, restore_dir=target)

    assert str(target) in str(exc.value)


def test_default_paths_are_phase_b_locations():
    assert kitty_backup.DEFAULT_SOURCE_DIR == KITTY_DATA_DIR
    assert kitty_backup.DEFAULT_BACKUP_ROOT == DATA_DIR / "backups" / "kitty"


def _make_real_backup(tmp_path) -> tuple:
    """Create a source dir, back it up, and return (source, backup_dir)."""
    source = tmp_path / "data" / "kitty"
    source.mkdir(parents=True)
    (source / "note.txt").write_text("hello", encoding="utf-8")
    db_file = source / "kitty.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE sample (name TEXT)")
        conn.execute("INSERT INTO sample (name) VALUES ('stored')")
    backup_dir = kitty_backup.create_backup(
        source_dir=source,
        backup_root=tmp_path / "backups",
        timestamp="20260620T120000Z",
    )
    return source, backup_dir


def test_restore_restores_backup_into_live_target(tmp_path):
    source, backup_dir = _make_real_backup(tmp_path)
    shutil.rmtree(source)

    restored = kitty_backup.restore(backup_dir=backup_dir, target_dir=source)

    assert (source / "note.txt").read_text(encoding="utf-8") == "hello"
    with sqlite3.connect(source / "kitty.db") as conn:
        row = conn.execute("SELECT name FROM sample").fetchone()
    assert row == ("stored",)
    assert restored == source


def test_restore_refuses_directory_without_manifest(tmp_path):
    not_a_backup = tmp_path / "random"
    not_a_backup.mkdir()
    (not_a_backup / "file.txt").write_text("nope", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc:
        kitty_backup.restore(backup_dir=not_a_backup, target_dir=tmp_path / "target")

    assert "backup_manifest.json" in str(exc.value)


def test_restore_refuses_nonempty_target_without_replace(tmp_path):
    source, backup_dir = _make_real_backup(tmp_path)
    target = tmp_path / "live"
    target.mkdir()
    (target / "existing.txt").write_text("keep me", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc:
        kitty_backup.restore(backup_dir=backup_dir, target_dir=target)

    assert "not empty" in str(exc.value)
    assert (target / "existing.txt").read_text(encoding="utf-8") == "keep me"


def test_restore_replace_moves_existing_target_aside(tmp_path):
    source, backup_dir = _make_real_backup(tmp_path)
    target = tmp_path / "live"
    target.mkdir()
    (target / "existing.txt").write_text("keep me", encoding="utf-8")

    restored = kitty_backup.restore(backup_dir=backup_dir, target_dir=target, replace=True)

    assert restored == target
    assert (target / "note.txt").read_text(encoding="utf-8") == "hello"
    asides = [p for p in tmp_path.iterdir() if p.name.startswith("live.pre-restore-")]
    assert len(asides) == 1
    assert (asides[0] / "existing.txt").read_text(encoding="utf-8") == "keep me"


def test_restore_fails_loud_on_corrupt_sqlite(tmp_path):
    source, backup_dir = _make_real_backup(tmp_path)
    shutil.rmtree(source)

    corrupt_db = backup_dir / "kitty.db"
    with corrupt_db.open("wb") as fh:
        fh.write(b"this is not a real sqlite file at all")

    with pytest.raises(RuntimeError) as exc:
        kitty_backup.restore(backup_dir=backup_dir, target_dir=source)

    assert "integrity_check" in str(exc.value) or "SQLite" in str(exc.value)


def test_proof_drill_passes_on_clean_replica(tmp_path):
    from scripts import kitty_backup_proof

    exit_code = kitty_backup_proof.run_drill(seed_dir=tmp_path / "drill")

    assert exit_code == 0
