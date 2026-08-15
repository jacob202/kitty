-- Durable execution state for shared-agent room turns. Builder proposals remain
-- room messages; KittyBuilder remains the only engineering execution authority.
CREATE TABLE IF NOT EXISTS agent_workspace_turns (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES agent_workspaces(id),
    user_message_id TEXT NOT NULL REFERENCES agent_workspace_messages(id),
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'interrupted')),
    active_agent_id TEXT,
    error_type TEXT,
    error_message TEXT,
    started_at REAL NOT NULL,
    finished_at REAL
);

CREATE INDEX IF NOT EXISTS idx_agent_workspace_turns_order
    ON agent_workspace_turns (workspace_id, started_at DESC, id DESC);

-- The room has one serial handoff chain, so only one executor may own a room
-- at a time. Terminal turns remain unlimited durable history.
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_workspace_one_running_turn
    ON agent_workspace_turns (workspace_id)
    WHERE status = 'running';
