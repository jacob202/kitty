-- Shared agent workspace: durable rooms, named agents, messages, and events.
CREATE TABLE IF NOT EXISTS agent_workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    objective TEXT,
    status TEXT NOT NULL CHECK (status IN ('active', 'paused', 'closed')),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_workspace_agents (
    workspace_id TEXT NOT NULL REFERENCES agent_workspaces(id),
    agent_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    model TEXT,
    status TEXT NOT NULL CHECK (status IN ('available', 'paused', 'retired')),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (workspace_id, agent_id)
);

CREATE TABLE IF NOT EXISTS agent_workspace_messages (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES agent_workspaces(id),
    parent_message_id TEXT REFERENCES agent_workspace_messages(id),
    sender_kind TEXT NOT NULL CHECK (sender_kind IN ('user', 'agent', 'system')),
    sender_id TEXT NOT NULL,
    recipient_id TEXT,
    message_kind TEXT NOT NULL CHECK (
        message_kind IN ('prompt', 'plan', 'handoff', 'review', 'result', 'status')
    ),
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_workspace_events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES agent_workspaces(id),
    type TEXT NOT NULL,
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('user', 'agent', 'system')),
    actor_id TEXT NOT NULL,
    message_id TEXT REFERENCES agent_workspace_messages(id),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_workspace_messages_order
    ON agent_workspace_messages (workspace_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_agent_workspace_events_order
    ON agent_workspace_events (workspace_id, created_at, id);
