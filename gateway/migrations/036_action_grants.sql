-- Issue #554: scoped user grants evaluated at the action execution boundary.
--
-- The signed action_tiers.json stays the baseline authority (which kinds exist,
-- which are disabled, the minimum approval floor). This table records what the
-- *user* has additionally decided: allow / ask / deny, bound to a scope, with
-- optional expiry, session binding and spend ceiling.
--
-- A grant can authorize an action the baseline would have asked about. It can
-- never make a disabled kind, a missing executor, or a domain refusal valid.

CREATE TABLE IF NOT EXISTS action_grants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    capability TEXT NOT NULL,          -- action kind, e.g. calendar.event.create
    decision TEXT NOT NULL,            -- allow|ask|deny
    scope_type TEXT NOT NULL,          -- global|project|repo|site|integration|
                                       -- mcp_server|skill|tool|provider|automation|session
    scope_id TEXT NOT NULL DEFAULT '', -- '' for global; otherwise the scope's id/value
    session_id TEXT,                   -- non-null binds the grant to one session
    granted_tier TEXT NOT NULL,        -- risk tier the user saw when granting
    expires_at REAL,                   -- epoch seconds; NULL = no expiry
    budget_limit_usd REAL,             -- NULL = no spend ceiling
    budget_spent_usd REAL NOT NULL DEFAULT 0,
    reason TEXT NOT NULL,              -- the preview the user was shown
    created_by TEXT NOT NULL DEFAULT 'user',
    revoked_at REAL
);

CREATE INDEX IF NOT EXISTS idx_action_grants_lookup
    ON action_grants (capability, scope_type, scope_id);

-- A proposal has to say what it is scoped to, or a scoped grant has nothing to
-- match against. Existing rows default to the global scope, which is what they
-- effectively were before this column existed.
ALTER TABLE actions ADD COLUMN scope_type TEXT NOT NULL DEFAULT 'global';
ALTER TABLE actions ADD COLUMN scope_id TEXT NOT NULL DEFAULT '';

-- Which session proposed this. A grant bound to one session only authorizes
-- actions from that session; without this column such a grant could never
-- match an action-queue row and the session bound would be decorative.
ALTER TABLE actions ADD COLUMN session_id TEXT;

-- Declared cost of the side effect, when the proposer knows it. NULL means
-- unknown, and a budget-limited grant refuses to authorize an unknown cost
-- rather than spending against a ceiling it cannot check.
ALTER TABLE actions ADD COLUMN estimated_cost_usd REAL;
