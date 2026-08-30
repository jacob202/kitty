-- CR-05b: persist per-reply memory evidence (the CR-04 trailer) in the
-- ledger so restart recovery keeps the "kitty remembered" block.
ALTER TABLE chat_messages ADD COLUMN memory_items TEXT;
