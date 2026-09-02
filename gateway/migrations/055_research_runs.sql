CREATE TABLE IF NOT EXISTS research_runs (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    project_id INTEGER,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    sources_json TEXT NOT NULL DEFAULT '[]',
    summary TEXT,
    artifact_id TEXT,
    error TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    completed_at REAL
);

CREATE INDEX IF NOT EXISTS idx_research_runs_created_at ON research_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_runs_project_id ON research_runs(project_id, created_at DESC);
