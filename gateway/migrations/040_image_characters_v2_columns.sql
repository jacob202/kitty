-- Issue #580: add the v2 character columns that were never actually created.
--
-- 027_image_characters_v2.sql's header claims these are "added at runtime by the
-- Python code (image_characters._ensure_db)". That is false — `_ensure_db()`
-- only calls kitty_db.migrate(), and no .sql file adds them. So since f455c48d
-- (2026-07-24) `create_character()` has written face_embedding,
-- face_embedding_model, version and tags into a table that has none of them, and
-- POST /studio/characters has returned 500 every time. Reading a character would
-- fail the same way on _row_to_character()'s row["face_embedding"], and
-- add_character_ref() writes four columns image_character_refs does not have.
--
-- Result: saved characters were unusable, which makes identity-locked generation
-- unreachable — you could never create the character it depends on.
--
-- Numbered 040 deliberately: 036/037 are taken on main, and open Image Lab
-- branches already claim 036-039 for their own migrations.

ALTER TABLE image_characters ADD COLUMN face_embedding BLOB;
ALTER TABLE image_characters ADD COLUMN face_embedding_model TEXT;
ALTER TABLE image_characters ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE image_characters ADD COLUMN superseded_by TEXT;
ALTER TABLE image_characters ADD COLUMN tags TEXT;

ALTER TABLE image_character_refs ADD COLUMN face_embedding BLOB;
ALTER TABLE image_character_refs ADD COLUMN face_embedding_model TEXT;
ALTER TABLE image_character_refs ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE image_character_refs ADD COLUMN tags TEXT;

-- Version lookups walk the supersede chain; character_id is already the PK.
CREATE INDEX IF NOT EXISTS idx_image_characters_superseded_by
    ON image_characters (superseded_by);
