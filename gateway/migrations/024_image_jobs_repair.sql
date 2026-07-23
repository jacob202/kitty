-- IMG-01 reconciliation: repair job identity, lifecycle, and metadata.
--
-- Adds a Kitty-owned provider-neutral job_id (UUID) as the public identity.
-- The existing INTEGER PRIMARY KEY id remains the internal SQLite surrogate
-- for backward compatibility with rows created by the 023 migration.
--
-- Adds timestamps and metadata columns required by the accepted contract that
-- were missing from 023. Existing rows are backfilled.
--
-- Old column names (engine, kind, provider_status, model, preset, completed_at,
-- error_type, error_message, provider_params, workflow_template) remain in the
-- schema for backward compatibility with existing data. New code writes to them
-- with corrected lifecycle values.

-- Kitty-owned public job identity (UUID, provider-neutral).
-- Backfilled below for rows created by migration 023.
ALTER TABLE image_jobs ADD COLUMN job_id TEXT NOT NULL DEFAULT '';

-- Lifecycle timestamps required by the accepted contract.
ALTER TABLE image_jobs ADD COLUMN updated_at TEXT;
ALTER TABLE image_jobs ADD COLUMN submitted_at TEXT;
ALTER TABLE image_jobs ADD COLUMN finished_at TEXT;

-- Failure and diagnostics metadata.
ALTER TABLE image_jobs ADD COLUMN normalized_error TEXT;
ALTER TABLE image_jobs ADD COLUMN provider_diagnostics_json TEXT;

-- Artifact and reproducibility metadata.
ALTER TABLE image_jobs ADD COLUMN artifact_id TEXT;
ALTER TABLE image_jobs ADD COLUMN workflow_hash TEXT;

-- Backfill job_id for existing rows.
UPDATE image_jobs SET job_id = 'job_' || lower(hex(randomblob(16))) WHERE job_id = '';

-- Backfill updated_at for existing rows.
UPDATE image_jobs SET updated_at = COALESCE(started_at, completed_at, created_at) WHERE updated_at IS NULL;

-- Backfill submitted_at for existing rows that have started_at (were submitted).
UPDATE image_jobs SET submitted_at = started_at WHERE submitted_at IS NULL AND started_at IS NOT NULL;

-- Backfill finished_at from completed_at for terminal-status rows.
UPDATE image_jobs SET finished_at = completed_at WHERE finished_at IS NULL AND completed_at IS NOT NULL;
