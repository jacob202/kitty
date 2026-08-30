-- Bind one-shot approvals to the exact proposed action identity.
ALTER TABLE actions ADD COLUMN approval_fingerprint TEXT;
