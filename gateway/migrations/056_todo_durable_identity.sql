-- P4: a chosen action has to survive the list being regenerated around it.
-- `progress_note` records where the user stopped without completing the item;
-- `project_id` associates it with the project it belongs to.
ALTER TABLE todos ADD COLUMN progress_note TEXT;
ALTER TABLE todos ADD COLUMN project_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_todos_project ON todos (project_id, sort_order);
