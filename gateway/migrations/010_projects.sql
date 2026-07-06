-- P6 (docs/packets/021): project registry — the real "project resume."
-- 006/#71 shipped only ./kitty resume, a dev-tool for the kitty repo's own
-- state; this table plus gateway/project_resume.py is what actually tracks
-- Jacob's real-world projects. kind=code projects compose from git;
-- admin/creative projects are the same table with document/journal
-- signals instead of git — that's the proof the model isn't secretly a
-- dev tool.
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,                    -- code|admin|creative
    paths_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'active', -- active|paused|archived
    last_touched REAL,
    summary TEXT NOT NULL DEFAULT '',
    open_questions_json TEXT NOT NULL DEFAULT '[]',
    next_actions_json TEXT NOT NULL DEFAULT '[]',
    delegable_json TEXT NOT NULL DEFAULT '[]',
    links_json TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status);
CREATE INDEX IF NOT EXISTS idx_projects_kind ON projects (kind);
