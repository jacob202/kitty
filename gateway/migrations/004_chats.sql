-- Phase C C1: chats table.
-- Chat payloads are stored as a JSON blob keyed by id. This keeps the
-- route API shape-agnostic — clients send any chat object and we store
-- it whole, mirroring how app_settings.value stores arbitrary config.
-- The id matches the value the /chats route uses for upsert and delete.
CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
