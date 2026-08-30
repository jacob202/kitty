-- 012 — Move cron schedules from data/cron_schedules.db into kitty.db.
--
-- See docs/phases/PHASE_C3_PLAN.md for the full sequence (C3-0 dry run, C3-1
-- this migration, C3-2 cron.py update, C3-3 live run, C3-4 cleanup
-- after a week of stable operation).
--
-- The table is renamed `schedules` -> `cron_schedules` to avoid future
-- collision in the shared DB. Only gateway/cron.py references this table.
--
-- Source schema (data/cron_schedules.db) for reference:
--   CREATE TABLE schedules (
--       id TEXT PRIMARY KEY,
--       name TEXT NOT NULL,
--       action TEXT NOT NULL,
--       schedule_type TEXT NOT NULL,   -- daily, interval, once
--       schedule_value TEXT NOT NULL,  -- "07:00", "30" (minutes), ISO datetime
--       metadata TEXT DEFAULT '{}',
--       enabled INTEGER DEFAULT 1,
--       last_run REAL DEFAULT 0,
--       created_at REAL
--   );

CREATE TABLE IF NOT EXISTS cron_schedules (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    action         TEXT NOT NULL,
    schedule_type  TEXT NOT NULL,
    schedule_value TEXT NOT NULL,
    metadata       TEXT DEFAULT '{}',
    enabled        INTEGER DEFAULT 1,
    last_run       REAL DEFAULT 0,
    created_at     REAL
);
