-- P4: the one action the user explicitly chose for this project.
-- Distinct from projects.next_actions_json (mechanical top-3) and from
-- project_next_steps (the LLM's curated pick, replaced on every generate).
-- Regenerating either of those must never disturb this.
ALTER TABLE projects ADD COLUMN selected_todo_id INTEGER;
