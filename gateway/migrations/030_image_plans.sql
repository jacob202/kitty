-- IMG-A2 (issue #336): persisted, session-owned image plans.
--
-- A2 upgrades the plan from an ephemeral preview to a durable, approved
-- artifact: /studio/plan persists the validated ImagePlan (refined prompt,
-- resolved references, guidance tags) under a stable plan_id owned by the
-- session that created it, and /studio/generate dispatches from that stored
-- plan instead of re-deriving from mutable form state.
--
-- image_plans is the record of what the user approved; image_jobs remains the
-- record of what was rendered; image_runner remains the only dispatch path.
-- Nothing here submits work to a renderer.
CREATE TABLE IF NOT EXISTS image_plans (
    plan_id            TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL REFERENCES image_sessions(session_id),
    status             TEXT NOT NULL,
    original_prompt    TEXT NOT NULL,
    refined_prompt     TEXT NOT NULL,
    character_id       TEXT,
    character_ref_path TEXT,
    recipe_id          TEXT,
    guidance_tags_json TEXT NOT NULL,
    references_json    TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_image_plans_session
    ON image_plans(session_id);
