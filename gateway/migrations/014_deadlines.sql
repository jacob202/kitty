-- P7 (docs/packets/017): benefits/admin rails — watched deadlines and escalation log.
CREATE TABLE IF NOT EXISTS deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    source TEXT NOT NULL,
    source_id TEXT,
    due_date TEXT NOT NULL,
    obligation TEXT NOT NULL DEFAULT '',
    amount TEXT,
    currency TEXT,
    confidence TEXT NOT NULL DEFAULT 'needs_jacob',
    status TEXT NOT NULL DEFAULT 'open',
    dedupe_key TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    pushed_at REAL
);

CREATE INDEX IF NOT EXISTS idx_deadlines_project_id ON deadlines (project_id);
CREATE INDEX IF NOT EXISTS idx_deadlines_status ON deadlines (status);
CREATE INDEX IF NOT EXISTS idx_deadlines_due_date ON deadlines (due_date);
CREATE INDEX IF NOT EXISTS idx_deadlines_dedupe_key ON deadlines (dedupe_key);

CREATE TABLE IF NOT EXISTS deadline_escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deadline_id INTEGER NOT NULL REFERENCES deadlines(id) ON DELETE CASCADE,
    checkpoint TEXT NOT NULL,
    pushed_at REAL NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_deadline_escalations_deadline_id ON deadline_escalations (deadline_id);
