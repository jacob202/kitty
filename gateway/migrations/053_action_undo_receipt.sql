-- KF-UNDO-02: Add undo_journal_id receipt to actions table for todo.create undo capability.
-- The column is nullable so existing rows migrate with NULL and the migration is idempotent.

ALTER TABLE actions ADD COLUMN undo_journal_id TEXT;

CREATE INDEX IF NOT EXISTS idx_actions_undo_journal_id ON actions (undo_journal_id);