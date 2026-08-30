CREATE TABLE IF NOT EXISTS image_job_observations (
  job_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  model_id TEXT,
  operation TEXT NOT NULL,
  actual_cost_usd REAL,
  duration_seconds REAL NOT NULL,
  completed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_image_job_observations_estimate
  ON image_job_observations(provider, model_id, operation, completed_at DESC);
