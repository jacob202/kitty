CREATE TABLE IF NOT EXISTS idea_mine_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    source_ref TEXT,
    user_review TEXT NOT NULL DEFAULT 'unreviewed',
    exported_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_idea_mine_object_type
    ON idea_mine_items (object_type);
CREATE INDEX IF NOT EXISTS idx_idea_mine_user_review
    ON idea_mine_items (user_review);
