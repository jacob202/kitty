-- P2 (docs/packets/002): inbox triage.
-- One row per triaged inbox entry. inbox_id is UNIQUE so a re-run skips
-- entries already classified (idempotent passes). Triage never mutates the
-- inbox itself (D4: capture stays dumb, append-only) — results live only
-- here. `drop` is a bucket, not a deletion: dropped entries stay queryable.
CREATE TABLE IF NOT EXISTS inbox_triage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbox_id TEXT NOT NULL UNIQUE,
    ts REAL NOT NULL,
    bucket TEXT NOT NULL,          -- now|scheduled|someday|reference|needs_jacob|drop
    confidence REAL NOT NULL,
    rationale TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inbox_triage_bucket ON inbox_triage (bucket);
