-- Image Studio V1: saved character library.
-- Private by default. Stores identity reference images for identity-preserving generation.
CREATE TABLE IF NOT EXISTS image_characters (
    character_id    TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT,
    preferred_recipe TEXT,
    identity_preset TEXT DEFAULT 'balanced',
    privacy_state   TEXT NOT NULL DEFAULT 'private',
    soft_deleted    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS image_character_refs (
    ref_id          TEXT PRIMARY KEY,
    character_id    TEXT NOT NULL REFERENCES image_characters(character_id) ON DELETE CASCADE,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    is_primary      INTEGER NOT NULL DEFAULT 0,
    storage_path    TEXT NOT NULL,
    original_name   TEXT,
    media_type      TEXT,
    file_size       INTEGER,
    width           INTEGER,
    height          INTEGER,
    quality_notes   TEXT,
    created_at      TEXT NOT NULL
);
