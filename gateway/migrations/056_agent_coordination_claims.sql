CREATE TABLE IF NOT EXISTS agent_coordination_claims (
    claim_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    lane_id TEXT NOT NULL,
    base_sha TEXT NOT NULL,
    branch TEXT NOT NULL,
    worktree_path TEXT NOT NULL,
    paths_json TEXT NOT NULL,
    resources_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    heartbeat_at REAL NOT NULL,
    lease_expires_at REAL NOT NULL,
    released_at REAL
);
CREATE INDEX IF NOT EXISTS idx_agent_coordination_claims_active
    ON agent_coordination_claims (released_at, lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_agent_coordination_claims_worktree
    ON agent_coordination_claims (worktree_path, released_at, lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_agent_coordination_claims_session
    ON agent_coordination_claims (session_id, released_at, lease_expires_at);
