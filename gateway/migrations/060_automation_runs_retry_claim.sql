-- 060 — Durable single-flight lineage for manual automation retries.
-- The parent claim blocks overlapping retries; retry_of_run_id lets terminal
-- child completion release that claim without coupling cleanup to one route.
ALTER TABLE automation_runs ADD COLUMN retry_claimed_at REAL;
ALTER TABLE automation_runs ADD COLUMN retry_of_run_id TEXT;
