-- P3 (docs/packets/003): action queue with enforced tiers.
-- Every external (or state-mutating) effect Kitty takes is a row here first:
-- proposed → (approved|rejected) → executed|failed. No code path may reach an
-- effect without passing through this table. preview is the human-readable
-- "exactly what will happen"; result records the outcome (success text or the
-- exception). risk_tier is enforced in the executor registry, in code, not by
-- convention: T0/T1 may execute from proposed, T2 requires approved.
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_kind TEXT NOT NULL,     -- signal|triage|nudge|chat|manual
    source_id TEXT,
    kind TEXT NOT NULL,            -- e.g. todo.create
    title TEXT NOT NULL,
    preview TEXT NOT NULL,         -- human-readable: exactly what will happen
    payload TEXT NOT NULL DEFAULT '{}',
    risk_tier TEXT NOT NULL,       -- T0|T1|T2 (disabled_v1 kinds cannot exist)
    status TEXT NOT NULL DEFAULT 'proposed',
        -- proposed|approved|rejected|executed|failed
    result TEXT,
    decided_at REAL,
    executed_at REAL
);

CREATE INDEX IF NOT EXISTS idx_actions_status ON actions (status);
