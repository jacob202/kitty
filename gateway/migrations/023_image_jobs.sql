-- IMG-01: durable provider-neutral image-job metadata store.
-- Kitty owns the primary key (job_id). Provider identifiers (ComfyUI prompt_id)
-- live in a nullable provider_job_id column. output_path is nullable until Kitty
-- verifies and persists the artifact. Lifecycle states and timestamps present
-- from the start so IMG-02 does not need to redesign the table.
-- workflow_hash stores a content hash of the ComfyUI workflow for reproducibility
-- without storing the executable graph (GPL-3.0 boundary).
CREATE TABLE IF NOT EXISTS image_jobs (
    job_id                   TEXT PRIMARY KEY,
    provider                 TEXT NOT NULL,
    provider_job_id          TEXT,
    operation                TEXT NOT NULL,
    status                   TEXT NOT NULL,
    prompt                   TEXT,
    negative_prompt          TEXT,
    seed                     INTEGER,
    model_id                 TEXT,
    preset_id                TEXT,
    width                    INTEGER,
    height                   INTEGER,
    steps                    INTEGER,
    guidance                 REAL,
    sampler                  TEXT,
    scheduler                TEXT,
    provider_params_json     TEXT,
    workflow_template_id     TEXT,
    workflow_hash            TEXT,
    artifact_id              TEXT,
    output_path              TEXT,
    normalized_error         TEXT,
    provider_diagnostics_json TEXT,
    parent_id                TEXT REFERENCES image_jobs(job_id),
    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL,
    started_at               TEXT,
    finished_at              TEXT
);
