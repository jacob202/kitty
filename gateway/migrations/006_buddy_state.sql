-- Phase C: buddy_state table.
-- Single-row store for Kitty's persistent mood state.
-- Columns mirror gateway/buddy.py _state dict keys.
-- The CHECK (id = 1) constraint enforces exactly one row.
CREATE TABLE IF NOT EXISTS buddy_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    mood TEXT NOT NULL DEFAULT 'idle',
    energy INTEGER NOT NULL DEFAULT 100,
    session_turns INTEGER NOT NULL DEFAULT 0,
    total_turns INTEGER NOT NULL DEFAULT 0,
    last_active_ts REAL NOT NULL DEFAULT 0.0,
    drift_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
