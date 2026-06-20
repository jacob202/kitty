"""Tests for the Phase B SQLite foundation."""

from __future__ import annotations

import sqlite3

import pytest

from gateway import db


def test_migrate_applies_foundation_once(tmp_path):
    db_file = tmp_path / "data" / "kitty" / "kitty.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_foundation.sql").write_text(
        """
        CREATE TABLE app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """,
        encoding="utf-8",
    )

    first = db.migrate(db_file=db_file, migrations_dir=migrations_dir)
    second = db.migrate(db_file=db_file, migrations_dir=migrations_dir)

    assert first == ["001_foundation.sql"]
    assert second == []
    with sqlite3.connect(db_file) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        applied = conn.execute(
            "SELECT name FROM schema_migrations ORDER BY name"
        ).fetchall()

    assert "schema_migrations" in tables
    assert "app_settings" in tables
    assert applied == [("001_foundation.sql",)]


def test_connect_sets_row_factory_and_foreign_keys(tmp_path):
    db_file = tmp_path / "kitty.db"

    with db.connect(db_file) as conn:
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO sample (name) VALUES (?)", ("Kitty",))
        row = conn.execute("SELECT id, name FROM sample").fetchone()

    assert foreign_keys == 1
    assert row["name"] == "Kitty"


def test_default_migrations_create_app_settings(tmp_path):
    db_file = tmp_path / "kitty.db"

    applied = db.migrate(db_file=db_file)

    assert "001_foundation.sql" in applied
    with sqlite3.connect(db_file) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'app_settings'"
        ).fetchone()
    assert table == ("app_settings",)


def test_default_migrations_create_chats_table(tmp_path):
    """Phase C C1: 004_chats.sql adds a chats table keyed by id with a JSON payload."""
    db_file = tmp_path / "kitty.db"

    applied = db.migrate(db_file=db_file)

    assert "004_chats.sql" in applied
    with sqlite3.connect(db_file) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'chats'"
        ).fetchone()
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(chats)").fetchall()
        }
    assert table == ("chats",)
    assert columns == {"id", "payload", "updated_at"}


def test_migrate_failure_names_file_and_database(tmp_path):
    db_file = tmp_path / "kitty.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_bad.sql").write_text("SELECT nope FROM", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc:
        db.migrate(db_file=db_file, migrations_dir=migrations_dir)

    message = str(exc.value)
    assert "001_bad.sql" in message
    assert str(db_file) in message
    with sqlite3.connect(db_file) as conn:
        applied = conn.execute("SELECT name FROM schema_migrations").fetchall()
    assert applied == []
