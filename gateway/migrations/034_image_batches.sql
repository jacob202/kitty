CREATE TABLE IF NOT EXISTS image_batches (
  batch_id TEXT PRIMARY KEY,
  session_id TEXT,
  status TEXT NOT NULL,
  count INTEGER NOT NULL,
  request_json TEXT NOT NULL,
  estimate_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS image_batch_items (
  item_id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL REFERENCES image_batches(batch_id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL,
  status TEXT NOT NULL,
  job_id TEXT,
  result_json TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  UNIQUE(batch_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_image_batch_items_queue
  ON image_batch_items(status, created_at, ordinal);
