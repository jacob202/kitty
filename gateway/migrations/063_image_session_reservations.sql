-- Round-2 review finding 1: a single session-wide `reserved_spend_usd` total
-- cannot tell an abandoned reservation (caller crashed before dispatch) from a
-- paid BFL job that is still in provider polling -- which may legitimately run
-- for 900s, longer than any session-wide TTL, and a TTL sweep against the
-- session clock zeroed its live exposure. Settling by amount had the same
-- blind spot: one attempt could consume another attempt's reservation.
--
-- Each reservation is now its own row: identity, owning session and job,
-- amount, lifecycle state, and heartbeat timestamps. The session column
-- remains as the materialized sum of live rows.

CREATE TABLE IF NOT EXISTS image_session_reservations (
    reservation_id TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL,
    job_id         TEXT,
    cost_usd       REAL NOT NULL,
    state          TEXT NOT NULL DEFAULT 'reserved'
        CHECK (state IN ('reserved', 'settled', 'released', 'abandoned')),
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_image_session_reservations_session
    ON image_session_reservations (session_id, state);

