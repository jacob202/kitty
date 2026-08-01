-- IMG-A1 (issue #336): durable conversational image sessions.
--
-- Extends the existing image_jobs store rather than replacing it. A session is
-- the conversation; image_jobs remains the record of what was rendered. The
-- link runs one way: image_jobs.session_id points at the session that produced
-- the job (added by image_sessions._ensure_session_column, since ALTER TABLE
-- cannot be expressed idempotently here).
--
-- The anchor is the selected result a follow-up edit operates on. Storing both
-- anchor_job_id and anchor_artifact_id keeps the renderer input resolvable even
-- if a later job reuses an artifact.
CREATE TABLE IF NOT EXISTS image_sessions (
    session_id             TEXT PRIMARY KEY,
    status                 TEXT NOT NULL,
    title                  TEXT,
    character_id           TEXT,
    reference_ids_json     TEXT,
    anchor_job_id          TEXT REFERENCES image_jobs(job_id),
    anchor_artifact_id     TEXT,
    protected_traits_json  TEXT,
    requested_changes_json TEXT,
    last_plan_json         TEXT,
    spend_usd              REAL NOT NULL DEFAULT 0,
    attempt_count          INTEGER NOT NULL DEFAULT 0,
    created_at             TEXT NOT NULL,
    updated_at             TEXT NOT NULL,
    ended_at               TEXT
);

-- Ordered conversation turns. seq is dense and session-scoped so resume can
-- replay in order without relying on timestamp collisions.
CREATE TABLE IF NOT EXISTS image_session_turns (
    turn_id    TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES image_sessions(session_id),
    seq        INTEGER NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT,
    job_id     TEXT REFERENCES image_jobs(job_id),
    created_at TEXT NOT NULL,
    UNIQUE (session_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_image_session_turns_session
    ON image_session_turns(session_id, seq);

CREATE INDEX IF NOT EXISTS idx_image_sessions_active
    ON image_sessions(updated_at DESC) WHERE status = 'active';
