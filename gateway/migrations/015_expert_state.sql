-- 015_expert_state.sql
-- Phase 2 hardening for proactive experts: atomic inbox tracking, snooze, and user feedback.

-- Tracks the atomic state of an inbox entry for a specific expert.
-- Status can be 'new', 'processing', 'triaged', 'error'.
CREATE TABLE IF NOT EXISTS expert_inbox_log (
    expert_id TEXT NOT NULL,
    inbox_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    updated_at REAL NOT NULL,
    PRIMARY KEY (expert_id, inbox_id)
);

CREATE INDEX IF NOT EXISTS idx_expert_inbox_log_status ON expert_inbox_log(status);

-- Tracks when an expert is snoozed until.
CREATE TABLE IF NOT EXISTS expert_snooze (
    expert_id TEXT PRIMARY KEY,
    snooze_until REAL NOT NULL
);

-- Tracks user feedback (dismissals) per topic hash to suppress future notifications.
CREATE TABLE IF NOT EXISTS expert_feedback (
    expert_id TEXT NOT NULL,
    topic_hash TEXT NOT NULL,
    dismissed_count INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL,
    PRIMARY KEY (expert_id, topic_hash)
);
