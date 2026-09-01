-- FTS5 full-text search index for chat messages.
-- The virtual table mirrors the chat_messages table so we can do
-- fast keyword search across all conversations.
-- Triggers keep the FTS index in sync with chat_messages inserts/updates/deletes.
-- Tokenizer: porter stemmer + unicode61 for English + unicode support.
CREATE VIRTUAL TABLE IF NOT EXISTS chat_messages_fts USING fts5(
    message_id UNINDEXED,
    conversation_id UNINDEXED,
    content,
    role UNINDEXED,
    created_at UNINDEXED,
    tokenize='porter unicode61'
);

-- Triggers to keep FTS index in sync

CREATE TRIGGER IF NOT EXISTS chat_messages_fts_insert AFTER INSERT ON chat_messages
BEGIN
    INSERT INTO chat_messages_fts (message_id, conversation_id, content, role, created_at)
    VALUES (
        new.id,
        (SELECT conversation_id FROM chat_turns WHERE id = new.turn_id),
        new.content,
        new.role,
        new.created_at
    );
END;

CREATE TRIGGER IF NOT EXISTS chat_messages_fts_delete AFTER DELETE ON chat_messages
BEGIN
    INSERT INTO chat_messages_fts (chat_messages_fts, message_id, conversation_id, content, role, created_at)
    VALUES ('delete', old.id, '', '', '', '');
END;

CREATE TRIGGER IF NOT EXISTS chat_messages_fts_update AFTER UPDATE ON chat_messages
BEGIN
    INSERT INTO chat_messages_fts (chat_messages_fts, message_id, conversation_id, content, role, created_at)
    VALUES ('delete', old.id, '', '', '', '');
    INSERT INTO chat_messages_fts (message_id, conversation_id, content, role, created_at)
    VALUES (
        new.id,
        (SELECT conversation_id FROM chat_turns WHERE id = new.turn_id),
        new.content,
        new.role,
        new.created_at
    );
END;
