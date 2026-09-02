-- KF-UNDO-02: Add undo_journal_id receipt to actions table for todo.create undo capability.
-- The column is nullable so existing rows migrate with NULL.
-- Idempotent: the migration runner (db.py:migrate) tracks applied migrations in
-- schema_migrations, so this SQL executes at most once per database. The CREATE INDEX
-- uses IF NOT EXISTS for extra safety if the file is ever run outside the runner.

ALTER TABLE actions ADD COLUMN undo_journal_id TEXT;

CREATE INDEX IF NOT EXISTS idx_actions_undo_journal_id ON actions (undo_journal_id);
