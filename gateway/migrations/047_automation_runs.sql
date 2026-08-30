-- 047 — Durable Automation Run evidence for issue #550.
-- Domain state remains in domain-owned tables; this records execution truth only.
CREATE TABLE IF NOT EXISTS automation_runs (
    id              TEXT PRIMARY KEY,
    automation_id   TEXT NOT NULL,
    action          TEXT NOT NULL,
    trigger_kind    TEXT NOT NULL CHECK (trigger_kind IN ('time', 'monitor', 'signal', 'manual')),
    trigger_ref     TEXT,
    schedule_id     TEXT,
    due_at          REAL,
    started_at      REAL NOT NULL,
    completed_at    REAL,
    status          TEXT NOT NULL CHECK (status IN (
        'running', 'completed', 'failed', 'interrupted', 'action_unavailable',
        'source_unavailable', 'condition_false', 'policy_refused'
    )),
    duration_ms     INTEGER,
    result_pointer  TEXT,
    error           TEXT,
    policy_json     TEXT,
    created_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_automation_runs_identity
    ON automation_runs (automation_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_automation_runs_status
    ON automation_runs (status, started_at DESC);
