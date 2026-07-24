-- Image Jobs V2: priority queue index.
-- The ALTER TABLE to add priority/retry columns is handled at runtime
-- by image_jobs._ensure_queue_columns so existing tests are not broken.
CREATE INDEX IF NOT EXISTS idx_image_jobs_queue ON image_jobs(priority DESC, created_at ASC)
    WHERE status IN ('created', 'submitted');