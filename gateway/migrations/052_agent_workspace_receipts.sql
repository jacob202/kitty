-- Per-participant delivery receipts for durable agent-workspace messages.
CREATE TABLE IF NOT EXISTS agent_workspace_message_receipts (
    message_id TEXT NOT NULL REFERENCES agent_workspace_messages(id),
    participant_id TEXT NOT NULL,
    seen_at REAL,
    acknowledged_at REAL,
    PRIMARY KEY (message_id, participant_id),
    CHECK (acknowledged_at IS NULL OR seen_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_agent_workspace_receipts_participant
ON agent_workspace_message_receipts (participant_id, seen_at, acknowledged_at, message_id);
