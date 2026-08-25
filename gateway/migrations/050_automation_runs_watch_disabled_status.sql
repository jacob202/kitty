-- 050 — widen automation_runs.status to allow 'watch_disabled' (RC-09).
-- A web-monitor sweep can snapshot a watch, then spend real time (HTTP
-- round trips, an inter-watch delay) before dispatching its result. If the
-- watch was disabled or deleted in that window, the run must record that
-- honestly instead of either firing anyway or being forced into an
-- unrelated status. SQLite has no ALTER-the-CHECK, so rebuild the table.
CREATE TABLE automation_runs_new (
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
        'source_unavailable', 'condition_false', 'policy_refused', 'watch_disabled'
    )),
    duration_ms     INTEGER,
    result_pointer  TEXT,
    error           TEXT,
    policy_json     TEXT,
    payload_json    TEXT,
    created_at      REAL NOT NULL
);

INSERT INTO automation_runs_new
    SELECT id, automation_id, action, trigger_kind, trigger_ref, schedule_id,
           due_at, started_at, completed_at, status, duration_ms,
           result_pointer, error, policy_json, payload_json, created_at
    FROM automation_runs;

DROP TABLE automation_runs;
ALTER TABLE automation_runs_new RENAME TO automation_runs;

CREATE INDEX IF NOT EXISTS idx_automation_runs_identity
    ON automation_runs (automation_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_automation_runs_status
    ON automation_runs (status, started_at DESC);
