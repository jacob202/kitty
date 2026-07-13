-- Thread-scoped objective: lets a user bind a goal to a conversation.
ALTER TABLE chat_conversations ADD COLUMN objective TEXT DEFAULT NULL;
