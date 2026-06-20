-- Phase C B1: journal_entries table.
-- Normalized columns (not a JSON blob) because the journal shape is stable
-- and reads are common (list_entries, count_entries). The data shape comes
-- from gateway/journal.py:save_journal_entry: ts, theme, entry, session_id.
-- The stale data/journal.schema.sql is a prior-design artifact and is
-- intentionally not migrated.
CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    theme TEXT,
    entry TEXT NOT NULL,
    session_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
