"""Tests for image_characters — character CRUD and reference management (V2)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gateway.image.characters import (
    CharacterError,
    CharacterNotFoundError,
    GalleryItemNotFoundError,
    add_character_ref,
    add_gallery_item,
    create_character,
    delete_character_ref,
    delete_gallery_item,
    get_character,
    get_gallery_item,
    list_character_refs,
    list_characters,
    list_gallery,
    soft_delete_character,
    supersede_character,
    update_character,
    update_gallery_item,
)


@pytest.fixture(autouse=True)
def override_db(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "test_kitty.db"
    monkeypatch.setattr("gateway.image.characters.KITTY_DB_FILE", db_path)
    monkeypatch.setattr(
        "gateway.image.characters.CHARACTER_STORAGE_DIR",
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
            priority INTEGER NOT NULL DEFAULT 0, retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 0, last_error TEXT, queued_at TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, started_at TEXT, finished_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS image_characters (
            character_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
            preferred_recipe TEXT, identity_preset TEXT DEFAULT 'balanced',
            privacy_state TEXT NOT NULL DEFAULT 'private', soft_deleted INTEGER NOT NULL DEFAULT 0,
            face_embedding BLOB, face_embedding_model TEXT,
            version INTEGER NOT NULL DEFAULT 1, superseded_by TEXT,
            tags TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS image_character_refs (
            ref_id TEXT PRIMARY KEY, character_id TEXT NOT NULL REFERENCES image_characters(character_id),
            sort_order INTEGER NOT NULL DEFAULT 0, is_primary INTEGER NOT NULL DEFAULT 0,
            storage_path TEXT NOT NULL, original_name TEXT, media_type TEXT,
            file_size INTEGER, width INTEGER, height INTEGER, quality_notes TEXT,
            tags TEXT, face_embedding BLOB, face_embedding_model TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS image_character_gallery (
            item_id TEXT PRIMARY KEY, character_id TEXT NOT NULL REFERENCES image_characters(character_id),
            job_id TEXT, output_path TEXT NOT NULL, prompt TEXT,
            recipe_id TEXT, identity_mode TEXT, identity_strength REAL,
            rating INTEGER, tags TEXT, sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("INSERT INTO schema_migrations (name) VALUES ('024_image_characters.sql')")
    for name in ["023_image_jobs.sql", "025_image_references.sql", "026_image_recipes.sql",
                  "027_image_characters_v2.sql"]:
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
        assert char.version == 1
        assert char.tags is None

        retrieved = get_character(char.character_id)
        assert retrieved.name == "Jacob"

    def test_create_empty_name_raises(self, override_db):
        with pytest.raises(CharacterError, match="name must not be empty"):
            create_character("")

    def test_create_too_long_name_raises(self, override_db):
        with pytest.raises(CharacterError, match="name too long"):
            create_character("x" * 121)

    def test_create_invalid_preset(self, override_db):
        with pytest.raises(CharacterError, match="identity_preset must be"):
            create_character("Test", identity_preset="bogus")

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

        chars = list_characters()
        assert all(c.character_id != char.character_id for c in chars)

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


class TestCharacterV2:
    def test_create_with_tags(self, override_db):
        char = create_character("Test", tags=["fantasy", "elf"])
        assert set(char.tags) == {"elf", "fantasy"}

    def test_create_with_face_embedding(self, override_db):
        emb = b"fake_embedding_data_32_bytes!!"
        char = create_character("Test", face_embedding=emb, face_embedding_model="insightface")
        assert char.face_embedding == emb
        assert char.face_embedding_model == "insightface"

    def test_update_tags(self, override_db):
        char = create_character("Test")
        updated = update_character(char.character_id, tags=["warrior"])
        assert updated.tags == ["warrior"]

    def test_update_face_embedding(self, override_db):
        char = create_character("Test")
        emb = b"new_embedding_data_here!!"
        updated = update_character(char.character_id, face_embedding=emb, face_embedding_model="arcface")
        assert updated.face_embedding == emb
        assert updated.face_embedding_model == "arcface"

    def test_supersede(self, override_db):
        char1 = create_character("V1")
        char2 = create_character("V2")
        superseded = supersede_character(char1.character_id, char2.character_id)
        assert superseded.superseded_by == char2.character_id
        assert superseded.version >= 2

    def test_supersede_soft_deleted_raises(self, override_db):
        char1 = create_character("V1")
        char2 = create_character("V2")
        soft_delete_character(char1.character_id)
        with pytest.raises(CharacterError, match="soft-deleted"):
            supersede_character(char1.character_id, char2.character_id)

    def test_list_by_tag(self, override_db):
        create_character("A", tags=["fantasy"])
        create_character("B", tags=["sci-fi"])
        create_character("C", tags=["fantasy"])
        fantasy = list_characters(tag="fantasy")
        assert len(fantasy) == 2
        sci_fi = list_characters(tag="sci-fi")
        assert len(sci_fi) == 1


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

    def test_add_ref_with_tags_embedding(self, override_db):
        char = create_character("Test")
        ref = add_character_ref(
            char.character_id, b"data",
            tags=["front-facing", "smiling"],
            face_embedding=b"\x00\x01\x02",
            face_embedding_model="insightface",
        )
        assert ref.tags == ["front-facing", "smiling"]
        assert ref.face_embedding == b"\x00\x01\x02"


class TestCharacterGallery:
    def test_add_gallery_item(self, override_db):
        char = create_character("Test")
        item = add_gallery_item(
            char.character_id, "/path/to/image.png",
            job_id="job_abc", prompt="a test image",
            recipe_id="comfyui_sdxl_standard",
            identity_mode="balanced", identity_strength=0.7,
            rating=5, tags=["best", "test"],
        )
        assert item.character_id == char.character_id
        assert item.rating == 5
        assert item.tags == ["best", "test"]

    def test_list_gallery(self, override_db):
        char = create_character("Test")
        add_gallery_item(char.character_id, "/path/1.png", prompt="img1")
        add_gallery_item(char.character_id, "/path/2.png", prompt="img2")
        items = list_gallery(char.character_id)
        assert len(items) == 2

    def test_list_gallery_tag_filter(self, override_db):
        char = create_character("Test")
        add_gallery_item(char.character_id, "/path/1.png", tags=["portrait"])
        add_gallery_item(char.character_id, "/path/2.png", tags=["landscape"])
        portraits = list_gallery(char.character_id, tag="portrait")
        assert len(portraits) == 1

    def test_update_gallery_item(self, override_db):
        char = create_character("Test")
        item = add_gallery_item(char.character_id, "/path/img.png", rating=3)
        updated = update_gallery_item(item.item_id, rating=5, tags=["favorite"])
        assert updated.rating == 5
        assert updated.tags == ["favorite"]

    def test_get_gallery_item(self, override_db):
        char = create_character("Test")
        item = add_gallery_item(char.character_id, "/path/img.png")
        retrieved = get_gallery_item(item.item_id)
        assert retrieved.item_id == item.item_id

    def test_get_gallery_item_not_found(self, override_db):
        with pytest.raises(GalleryItemNotFoundError):
            get_gallery_item("nonexistent")

    def test_delete_gallery_item(self, override_db):
        char = create_character("Test")
        item = add_gallery_item(char.character_id, "/path/img.png")
        delete_gallery_item(item.item_id)
        with pytest.raises(GalleryItemNotFoundError):
            get_gallery_item(item.item_id)

    def test_delete_gallery_item_not_found(self, override_db):
        with pytest.raises(GalleryItemNotFoundError):
            delete_gallery_item("nonexistent")
