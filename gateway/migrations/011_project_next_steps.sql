-- P4 (docs/packets/016): the single curated "B" per project. Separate
-- from projects.next_actions_json (021, mechanical top-3, no LLM) — this
-- table is the one-step-only, LLM-curated pick with its own lifecycle.
-- One row per project; a new generate() call replaces it in place, it
-- does not accumulate history.
CREATE TABLE IF NOT EXISTS project_next_steps (
    project_id INTEGER PRIMARY KEY REFERENCES projects(id),
    step TEXT NOT NULL,
    why TEXT NOT NULL,
    recent_win TEXT NOT NULL DEFAULT '',
    delegable INTEGER NOT NULL DEFAULT 0,
    generated_at REAL NOT NULL
);
