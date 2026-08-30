-- Image Studio V1: reusable reference assets.
-- Pose, outfit, object, location, and style references for generation composition.
CREATE TABLE IF NOT EXISTS image_references (
    reference_id    TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK(kind IN ('pose','outfit','object','location','style')),
    storage_path    TEXT NOT NULL,
    original_name   TEXT,
    media_type      TEXT,
    file_size       INTEGER,
    width           INTEGER,
    height          INTEGER,
    description     TEXT,
    privacy_state   TEXT NOT NULL DEFAULT 'private',
    soft_deleted    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
