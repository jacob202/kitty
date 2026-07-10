-- KPA-02c: link durable artifacts to the user message that attached them.
ALTER TABLE chat_messages ADD COLUMN artifact_ids TEXT NOT NULL DEFAULT '[]';
