-- 013 — Memory Weave (temporal knowledge graph).
--
-- Ported from memory/memory_weave.py (the abandoned src/* architecture).
-- Re-homed onto gateway/storage_router + memory_graph per the salvage
-- dig verdict. The MemoryWeave tracks facts with provenance, confidence
-- decay, and conflict resolution so Kitty stops re-trying approaches
-- that failed yesterday.
--
-- See docs/plans/chore-master-fix-and-deepen.md and the salvage dig
-- verdict in ~/Projects/kitty-salvage/README.md.
--
-- Source schema (data/memory_weave.db, old src/):
--   edges — knowledge graph facts with confidence + source
--   events — failures, corrections, tool outcomes
--   reliability_windows — per-resource success/failure over time
--   conversation_logs — chat patterns for offline analysis

CREATE TABLE IF NOT EXISTS weave_edges (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    entity             TEXT NOT NULL,
    relation           TEXT NOT NULL,
    value              TEXT NOT NULL,
    confidence         REAL DEFAULT 0.5,
    source             TEXT NOT NULL,
    source_type        TEXT DEFAULT 'unknown',
    timestamp          TEXT NOT NULL,
    last_verified      TEXT,
    deprecated         INTEGER DEFAULT 0,
    deprecated_by      INTEGER,
    deprecated_reason  TEXT,
    UNIQUE(entity, relation, source)
);

CREATE INDEX IF NOT EXISTS idx_weave_edges_entity
    ON weave_edges(entity);
CREATE INDEX IF NOT EXISTS idx_weave_edges_relation
    ON weave_edges(relation);
CREATE INDEX IF NOT EXISTS idx_weave_edges_timestamp
    ON weave_edges(timestamp);

CREATE TABLE IF NOT EXISTS weave_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,
    entity      TEXT,
    description TEXT NOT NULL,
    severity    TEXT DEFAULT 'info',
    timestamp   TEXT NOT NULL,
    metadata    TEXT
);

CREATE INDEX IF NOT EXISTS idx_weave_events_type
    ON weave_events(event_type);
CREATE INDEX IF NOT EXISTS idx_weave_events_timestamp
    ON weave_events(timestamp);

CREATE TABLE IF NOT EXISTS weave_reliability_windows (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    resource      TEXT NOT NULL,
    reliability   TEXT DEFAULT 'unknown',
    window_start  TEXT,
    window_end    TEXT,
    failure_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    last_updated  TEXT
);

CREATE INDEX IF NOT EXISTS idx_weave_reliability_resource
    ON weave_reliability_windows(resource);

CREATE TABLE IF NOT EXISTS weave_conversation_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    annotated   INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_weave_logs_timestamp
    ON weave_conversation_logs(timestamp);
