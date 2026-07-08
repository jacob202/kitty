"""Data access layer for proactive expert state (snooze, inbox lifecycle, feedback)."""

import time
import hashlib
import re

import json
from gateway.paths import KITTY_DB_FILE, EXPERT_STATE_FILE
from gateway import db as kitty_db

def compute_topic_hash(text: str) -> str:
    """Deterministic hash function for topic suppression."""
    from gateway.topic_hash import generate_topic_hash
    return generate_topic_hash("general", text)


def get_snooze_until(expert_id: str) -> float:
    """Return the timestamp this expert is snoozed until, or 0.0 if not snoozed."""
    kitty_db.migrate()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            "SELECT snooze_until FROM expert_snooze WHERE expert_id = ?",
            (expert_id,)
        ).fetchone()
        if row:
            return float(row[0])
        return 0.0


def set_snooze(expert_id: str, duration_seconds: float) -> float:
    """Snooze an expert for `duration_seconds`. Returns the snooze_until timestamp."""
    kitty_db.migrate()
    snooze_until = time.time() + duration_seconds
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO expert_snooze (expert_id, snooze_until)
            VALUES (?, ?)
            ON CONFLICT(expert_id) DO UPDATE SET snooze_until=excluded.snooze_until
            """,
            (expert_id, snooze_until)
        )
        conn.commit()
    return snooze_until


def clear_snooze(expert_id: str) -> None:
    """Clear any active snooze for an expert."""
    kitty_db.migrate()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute("DELETE FROM expert_snooze WHERE expert_id = ?", (expert_id,))
        conn.commit()


def get_dismissed_count(expert_id: str, topic_hash: str) -> int:
    kitty_db.migrate()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            "SELECT dismissed_count FROM expert_feedback WHERE expert_id = ? AND topic_hash = ?",
            (expert_id, topic_hash)
        ).fetchone()
        if row:
            return int(row[0])
        return 0


def increment_dismissed_count(expert_id: str, topic_hash: str) -> int:
    """Increment the dismissal counter for a topic hash and return the new count."""
    kitty_db.migrate()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO expert_feedback (expert_id, topic_hash, dismissed_count, updated_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(expert_id, topic_hash) DO UPDATE SET
                dismissed_count = expert_feedback.dismissed_count + 1,
                updated_at = excluded.updated_at
            """,
            (expert_id, topic_hash, time.time())
        )
        conn.commit()

        row = conn.execute(
            "SELECT dismissed_count FROM expert_feedback WHERE expert_id = ? AND topic_hash = ?",
            (expert_id, topic_hash)
        ).fetchone()
        return int(row[0]) if row else 1


def recover_stuck_inbox_entries(timeout_minutes: int = 10) -> int:
    """Revert any inbox entries stuck in 'processing' back to 'new' if older than timeout."""
    kitty_db.migrate()
    cutoff = time.time() - (timeout_minutes * 60)
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE expert_inbox_log SET status = 'new', updated_at = ? WHERE status = 'processing' AND updated_at < ?",
            (time.time(), cutoff)
        )
        conn.commit()
        return cursor.rowcount


def claim_inbox_entry(expert_id: str, inbox_id: str) -> bool:
    """
    Atomically transition an inbox entry to 'processing'.
    Returns True if successfully claimed, False if already processing, triaged, or error.
    """
    kitty_db.migrate()
    now = time.time()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        # First ensure a row exists
        conn.execute(
            """
            INSERT INTO expert_inbox_log (expert_id, inbox_id, status, updated_at)
            VALUES (?, ?, 'new', ?)
            ON CONFLICT(expert_id, inbox_id) DO NOTHING
            """,
            (expert_id, inbox_id, now)
        )

        # Then attempt to claim it
        cursor = conn.execute(
            """
            UPDATE expert_inbox_log
            SET status = 'processing', updated_at = ?
            WHERE expert_id = ? AND inbox_id = ? AND status = 'new'
            """,
            (now, expert_id, inbox_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def set_inbox_entry_status(expert_id: str, inbox_id: str, status: str) -> None:
    """Update the status of an inbox entry (e.g. to 'triaged' or 'error')."""
    kitty_db.migrate()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            """
            UPDATE expert_inbox_log
            SET status = ?, updated_at = ?
            WHERE expert_id = ? AND inbox_id = ?
            """,
            (status, time.time(), expert_id, inbox_id)
        )
        conn.commit()


def check_cooldown(expert_id: str, topic_hash: str, cooldown_hours: float) -> bool:
    if cooldown_hours <= 0:
        return False
    kitty_db.migrate()
    cutoff = time.time() - (cooldown_hours * 3600)
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            "SELECT updated_at FROM expert_feedback WHERE expert_id = ? AND topic_hash = ?",
            (expert_id, topic_hash)
        ).fetchone()
        if row and float(row[0]) > cutoff:
            return True
        return False


def set_cooldown(expert_id: str, topic_hash: str) -> None:
    kitty_db.migrate()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO expert_feedback (expert_id, topic_hash, dismissed_count, updated_at)
            VALUES (?, ?, 0, ?)
            ON CONFLICT(expert_id, topic_hash) DO UPDATE SET
                updated_at = excluded.updated_at
            """,
            (expert_id, topic_hash, time.time())
        )
        conn.commit()


def is_global_pause() -> bool:
    if not EXPERT_STATE_FILE.exists():
        return False
    try:
        with open(EXPERT_STATE_FILE, "r") as f:
            return json.load(f).get("pause_all", False)
    except json.JSONDecodeError:
        return False


def set_global_pause(paused: bool) -> None:
    EXPERT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {}
    if EXPERT_STATE_FILE.exists():
        try:
            with open(EXPERT_STATE_FILE, "r") as f:
                state = json.load(f)
        except json.JSONDecodeError:
            pass
    state["pause_all"] = paused
    with open(EXPERT_STATE_FILE, "w") as f:
        json.dump(state, f)
