"""Tests for image_characters — character CRUD and reference management."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gateway.image_characters import (
    CharacterError,
    CharacterNotFoundError,
    add_character_ref,
    create_character,
    delete_character_ref,
    get_character,
    list_character_refs,
    list_characters,
    soft_delete_character,
    update_character,
)


@pytest.fixture(autouse=True)
def override_db(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "test_kitty.db"
    monkeypatch.setattr("gateway.image_characters.KITTY_DB_FILE", db_path)
    monkeypatch.setattr(
        "gateway.image_characters.CHARACTER_STORAGE_DIR",
        tmp_path / "chars",
    )

    def _test_connect(db_file=db_path):
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    monkeypatch.setattr("gateway.db.connect", _test_connect)

    conn = _test_connect()
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS image_jobs (
            job_id TEXT PRIMARY KEY, provider TEXT NOT NULL, provider_job_id TEXT,
            operation TEXT NOT NULL, status TEXT NOT NULL, prompt TEXT, negative_prompt TEXT,
            seed INTEGER, model_id TEXT, preset_id TEXT, width INTEGER, height INTEGER,
            steps INTEGER, guidance REAL, sampler TEXT, scheduler TEXT,
            provider_params_json TEXT, workflow_template_id TEXT, workflow_hash TEXT,
            artifact_id TEXT, output_path TEXT, normalized_error TEXT,
            provider_diagnostics_json TEXT, parent_id TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, started_at TEXT, finished_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS image_characters (
            character_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
            preferred_recipe TEXT, identity_preset TEXT DEFAULT 'balanced',
            privacy_state TEXT NOT NULL DEFAULT 'private', soft_deleted INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS image_character_refs (
            ref_id TEXT PRIMARY KEY, character_id TEXT NOT NULL REFERENCES image_characters(character_id),
            sort_order INTEGER NOT NULL DEFAULT 0, is_primary INTEGER NOT NULL DEFAULT 0,
            storage_path TEXT NOT NULL, original_name TEXT, media_type TEXT,
            file_size INTEGER, width INTEGER, height INTEGER, quality_notes TEXT, created_at TEXT NOT NULL
        )
    """)
    conn.execute("INSERT INTO schema_migrations (name) VALUES ('024_image_characters.sql')")
    for name in ["023_image_jobs.sql", "025_image_references.sql", "026_image_recipes.sql"]:
        conn.execute("INSERT OR IGNORE INTO schema_migrations (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    return db_path


class TestCharacterCRUD:
    def test_create_and_get(self, override_db):
        char = create_character("Jacob")
        assert char.name == "Jacob"
        assert char.character_id.startswith("char_")
        assert char.identity_preset == "balanced"

        retrieved = get_character(char.character_id)
        assert retrieved.name == "Jacob"

    def test_create_empty_name_raises(self, override_db):
        with pytest.raises(CharacterError, match="name must not be empty"):
            create_character("")

    def test_create_too_long_name_raises(self, override_db):
        with pytest.raises(CharacterError, match="name too long"):
            create_character("x" * 121)

    def test_update(self, override_db):
        char = create_character("Test")
        updated = update_character(char.character_id, name="Updated")
        assert updated.name == "Updated"

    def test_update_identity_preset(self, override_db):
        char = create_character("Test")
        updated = update_character(char.character_id, identity_preset="identity_first")
        assert updated.identity_preset == "identity_first"

    def test_update_invalid_preset(self, override_db):
        char = create_character("Test")
        with pytest.raises(CharacterError, match="identity_preset must be"):
            update_character(char.character_id, identity_preset="invalid_preset")

    def test_soft_delete(self, override_db):
        char = create_character("Test")
        deleted = soft_delete_character(char.character_id)
        assert deleted.soft_deleted

        # Not in normal listing
        chars = list_characters()
        assert all(c.character_id != char.character_id for c in chars)

        # In listing with deleted
        chars_all = list_characters(include_soft_deleted=True)
        assert any(c.character_id == char.character_id for c in chars_all)

    def test_soft_deleted_cannot_update(self, override_db):
        char = create_character("Test")
        soft_delete_character(char.character_id)
        with pytest.raises(CharacterError, match="soft-deleted"):
            update_character(char.character_id, name="Changed")

    def test_get_missing_raises(self, override_db):
        with pytest.raises(CharacterNotFoundError):
            get_character("nonexistent")

    def test_list_empty(self, override_db):
        chars = list_characters()
        assert chars == []

    def test_list_multiple(self, override_db):
        create_character("A")
        create_character("B")
        chars = list_characters()
        assert len(chars) == 2


class TestCharacterRefs:
    def test_add_ref(self, override_db):
        char = create_character("Test")
        ref = add_character_ref(
            char.character_id,
            b"fake-image-data",
            original_name="photo.jpg",
            media_type="image/jpeg",
        )
        assert ref.character_id == char.character_id
        assert ref.original_name == "photo.jpg"
        assert ref.file_size == 15

    def test_add_primary_ref(self, override_db):
        char = create_character("Test")
        ref = add_character_ref(char.character_id, b"data", is_primary=True)
        assert ref.is_primary

    def test_max_six_refs(self, override_db):
        char = create_character("Test")
        for i in range(6):
            add_character_ref(char.character_id, f"data-{i}".encode())
        with pytest.raises(CharacterError, match="6 reference images"):
            add_character_ref(char.character_id, b"too-many")

    def test_list_refs(self, override_db):
        char = create_character("Test")
        add_character_ref(char.character_id, b"1")
        add_character_ref(char.character_id, b"2")
        refs = list_character_refs(char.character_id)
        assert len(refs) == 2

    def test_delete_ref(self, override_db):
        char = create_character("Test")
        ref = add_character_ref(char.character_id, b"data")
        delete_character_ref(char.character_id, ref.ref_id)
        refs = list_character_refs(char.character_id)
        assert len(refs) == 0

    def test_soft_deleted_cannot_add_ref(self, override_db):
        char = create_character("Test")
        soft_delete_character(char.character_id)
        with pytest.raises(CharacterError, match="soft-deleted"):
            add_character_ref(char.character_id, b"data")
