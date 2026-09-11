-- Assignment-scoped continuity for the existing Global Agent Room.
-- NULL preserves all pre-existing and unscoped room messages unchanged.
ALTER TABLE agent_workspace_messages ADD COLUMN scope_key TEXT;

CREATE INDEX IF NOT EXISTS idx_agent_workspace_messages_scope
    ON agent_workspace_messages (workspace_id, scope_key, created_at, id);
