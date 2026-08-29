-- 049 — Undo/Restore journal (Packet 09). Append-only audit trail of reversible
-- user-visible mutations so "undo" can create a new valid state without
-- rewriting history (history reads A -> B -> A as three states, not one edit).

CREATE TABLE IF NOT EXISTS undo_journal (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    undone INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_undo_journal_entity
    ON undo_journal (entity_type, entity_id, created_at DESC);
