-- 046 — governed explicit memories in the existing Kitty database.
-- Critical user-confirmed memories must remain durable without Mem0/Ollama.
CREATE TABLE IF NOT EXISTS explicit_memories (
    id              TEXT PRIMARY KEY,
    memory_key      TEXT,
    namespace       TEXT NOT NULL DEFAULT 'facts',
    text            TEXT NOT NULL,
    source_kind     TEXT NOT NULL DEFAULT 'user_explicit',
    source_ref      TEXT,
    sensitivity     TEXT NOT NULL DEFAULT 'normal',
    pinned          INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'active',
    superseded_by   TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    forgotten_at    TEXT,
    CHECK (status IN ('active', 'superseded', 'forgotten', 'archived', 'blocked')),
    FOREIGN KEY (superseded_by) REFERENCES explicit_memories(id)
);

CREATE INDEX IF NOT EXISTS idx_explicit_memories_status
    ON explicit_memories(status, namespace, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_explicit_memories_key
    ON explicit_memories(memory_key);
CREATE UNIQUE INDEX IF NOT EXISTS idx_explicit_memories_one_active_key
    ON explicit_memories(memory_key)
    WHERE memory_key IS NOT NULL AND status = 'active';
