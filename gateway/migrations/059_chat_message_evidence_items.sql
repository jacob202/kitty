-- Persist the exact source evidence receipts delivered with an assistant reply.
-- Kept separate from memory_items because source citations are not deletable memories.
ALTER TABLE chat_messages ADD COLUMN evidence_items TEXT;
