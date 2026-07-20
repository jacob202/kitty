-- IMG-01: durable, provider-neutral image-job metadata store.
-- Replaces gateway/image_gen.py's in-memory _history so jobs, seeds, and
-- outputs survive restarts. Provider-neutral: Draw Things and ComfyUI both
-- record through it. API-only to ComfyUI (GPL-3.0): we store only a workflow
-- template name/hash, never the executable graph.
CREATE TABLE IF NOT EXISTS image_jobs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  engine          TEXT    NOT NULL,
  provider_job_id TEXT,
  kind            TEXT    NOT NULL DEFAULT 'txt2img',
  prompt          TEXT    NOT NULL,
  negative_prompt TEXT,
  seed            INTEGER,
  model           TEXT,
  preset          TEXT,
  width           INTEGER,
  height          INTEGER,
  steps           INTEGER,
  guidance        REAL,
  sampler         TEXT,
  scheduler       TEXT,
  provider_params TEXT,
  workflow_template TEXT,
  provider_status TEXT    NOT NULL DEFAULT 'pending',
  output_path     TEXT,
  output_verified INTEGER NOT NULL DEFAULT 0,
  error_type      TEXT,
  error_message   TEXT,
  parent_id       INTEGER REFERENCES image_jobs(id),
  created_at      TEXT    NOT NULL,
  started_at      TEXT,
  completed_at    TEXT
);
