-- KPA-02b: durable artifact metadata for captured files and future outputs.
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    project_id INTEGER,
    kind TEXT NOT NULL,
    media_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('pending', 'ready', 'failed', 'archived')),
    storage_uri TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at REAL NOT NULL,
    created_by TEXT NOT NULL,
    source_ref TEXT,
    conversation_id TEXT,
    work_item_id TEXT,
    run_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_artifacts_project ON artifacts (project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_artifacts_conversation ON artifacts (conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts (kind, created_at);
