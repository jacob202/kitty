-- KPA-02a: normalized chat lifecycle ledger beside the legacy chat blob.
CREATE TABLE IF NOT EXISTS chat_conversations (
    id TEXT PRIMARY KEY,
    project_id INTEGER,
    title TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_turns (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES chat_conversations(id),
    project_id INTEGER,
    sequence INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'interrupted', 'cancelled')),
    manifest_revision TEXT NOT NULL,
    created_at REAL NOT NULL,
    completed_at REAL,
    error TEXT,
    UNIQUE (conversation_id, sequence)
);

CREATE TABLE IF NOT EXISTS chat_attempts (
    id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL REFERENCES chat_turns(id),
    attempt_number INTEGER NOT NULL,
    requested_model TEXT NOT NULL,
    resolved_model TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'interrupted', 'cancelled')),
    manifest_revision TEXT NOT NULL,
    started_at REAL NOT NULL,
    completed_at REAL,
    error TEXT,
    UNIQUE (turn_id, attempt_number)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL REFERENCES chat_turns(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('complete', 'partial', 'failed', 'interrupted')),
    source_message_id TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_turns_conversation
    ON chat_turns (conversation_id, sequence);
CREATE INDEX IF NOT EXISTS idx_chat_attempts_turn
    ON chat_attempts (turn_id, attempt_number);
CREATE INDEX IF NOT EXISTS idx_chat_messages_turn
    ON chat_messages (turn_id, created_at);
