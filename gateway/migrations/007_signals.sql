-- P1 (docs/packets/001): signals + state snapshots.
-- signals: one append table for connector/system events. Connectors emit,
-- consumers (triage, state composer, brief) read. dedupe_key is UNIQUE so
-- a re-polling connector cannot double-emit; NULL keys are exempt (SQLite
-- treats NULLs as distinct), for one-off internal signals.
-- state_snapshots: persisted output of state_composer.compose_now, the
-- baseline for the mechanical "what changed" diff.
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    dedupe_key TEXT UNIQUE,
    processed_at REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals (ts);

CREATE TABLE IF NOT EXISTS state_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    snapshot TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
