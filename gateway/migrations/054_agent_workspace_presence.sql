-- Session-level presence for the global agent room.
-- Each row is a durable session that a participant explicitly manages
-- via checkin, heartbeat, and checkout. Presence state is computed
-- from heartbeat age (PRESENCE_TTL ~120s), not stored as a column.
CREATE TABLE IF NOT EXISTS agent_workspace_presence_sessions (
    session_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    runtime TEXT,
    role TEXT,
    lane_id TEXT,
    exact_ref TEXT,
    summary TEXT,
    declared_status TEXT,
    started_at REAL NOT NULL,
    heartbeat_at REAL NOT NULL,
    ended_at REAL,
    PRIMARY KEY (session_id),
    UNIQUE (session_id, participant_id)
);

CREATE INDEX IF NOT EXISTS idx_presence_sessions_participant
    ON agent_workspace_presence_sessions (participant_id, ended_at, heartbeat_at);