-- Image Studio V2: character gallery table.
--
-- An earlier version of this header claimed the face embedding, versioning and
-- tag columns on image_characters/image_character_refs were "added at runtime by
-- the Python code (image_characters._ensure_db)". That was never true —
-- `_ensure_db()` only calls kitty_db.migrate(). The columns simply did not
-- exist, and saved characters were broken from this migration until
-- 044_image_characters_v2_columns.sql actually added them (issue #580).
CREATE TABLE IF NOT EXISTS image_character_gallery (
    item_id         TEXT PRIMARY KEY,
    character_id    TEXT NOT NULL REFERENCES image_characters(character_id) ON DELETE CASCADE,
    job_id          TEXT,
    output_path     TEXT NOT NULL,
    prompt          TEXT,
    recipe_id       TEXT,
    identity_mode   TEXT,
    identity_strength REAL,
    rating          INTEGER,
    tags            TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_char_gallery_char ON image_character_gallery(character_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_char_gallery_job ON image_character_gallery(job_id);