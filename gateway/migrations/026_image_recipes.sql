-- Image Studio V1: recipe registry.
-- Provider-neutral typed generation recipes that replace keyword parsing.
CREATE TABLE IF NOT EXISTS image_recipes (
    recipe_id               TEXT PRIMARY KEY,
    display_name            TEXT NOT NULL,
    description             TEXT,
    provider                TEXT NOT NULL,
    workflow_template_id    TEXT,
    model_family            TEXT,
    operation               TEXT NOT NULL DEFAULT 'txt2img',
    quality_tier            TEXT NOT NULL CHECK(quality_tier IN ('fast','quality','maximum')),
    expected_speed          TEXT,
    default_width           INTEGER DEFAULT 1024,
    default_height          INTEGER DEFAULT 1024,
    max_width               INTEGER DEFAULT 2048,
    max_height              INTEGER DEFAULT 2048,
    supported_aspects_json  TEXT,
    supports_img2img        INTEGER NOT NULL DEFAULT 0,
    supports_characters     INTEGER NOT NULL DEFAULT 0,
    max_characters          INTEGER NOT NULL DEFAULT 0,
    supports_pose_refs      INTEGER NOT NULL DEFAULT 0,
    supports_outfit_refs    INTEGER NOT NULL DEFAULT 0,
    supports_object_refs    INTEGER NOT NULL DEFAULT 0,
    supports_location_refs  INTEGER NOT NULL DEFAULT 0,
    supports_style_refs     INTEGER NOT NULL DEFAULT 0,
    supports_inpainting     INTEGER NOT NULL DEFAULT 0,
    supports_variation      INTEGER NOT NULL DEFAULT 0,
    supports_upscaling      INTEGER NOT NULL DEFAULT 0,
    identity_strength       INTEGER NOT NULL DEFAULT 0,
    required_models_json    TEXT,
    required_nodes_json     TEXT,
    license_notes           TEXT,
    is_available            INTEGER NOT NULL DEFAULT 1,
    priority                INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

-- Extend image_jobs with character/reference/recipe metadata.
ALTER TABLE image_jobs ADD COLUMN character_id TEXT;
ALTER TABLE image_jobs ADD COLUMN character_ref_ids_json TEXT;
ALTER TABLE image_jobs ADD COLUMN reference_ids_json TEXT;
ALTER TABLE image_jobs ADD COLUMN quality_mode TEXT;
ALTER TABLE image_jobs ADD COLUMN identity_mode TEXT;
ALTER TABLE image_jobs ADD COLUMN recipe_id TEXT;
ALTER TABLE image_jobs ADD COLUMN recipe_version TEXT;
ALTER TABLE image_jobs ADD COLUMN output_count INTEGER;
ALTER TABLE image_jobs ADD COLUMN routing_reason TEXT;
