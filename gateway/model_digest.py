# gateway/model_digest.py
"""AI Model Digest — read stored model-change events for the morning brief."""
import logging
import sqlite3

from gateway.db import apply_pragmas
from gateway.paths import MODEL_DIGEST_DB

logger = logging.getLogger("kitty.model_digest")

DB_PATH = MODEL_DIGEST_DB


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    apply_pragmas(conn)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS digest_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            logged_at TEXT,
            event_type TEXT,
            model_id TEXT,
            details TEXT
        )
    """)
    conn.commit()
    return conn


class ModelDigestError(RuntimeError):
    """Raised when the model-digest SQLite store cannot be read or written."""


def _load_recent_events(limit: int = 10) -> list[dict]:
    """Load the most recent digest events from SQLite.

    Fails loud: a store error raises ModelDigestError instead of silently
    returning an empty list, so the morning brief can report the outage
    honestly rather than appearing to have "no model news".
    """
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM digest_log ORDER BY logged_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as exc:
        raise ModelDigestError(f"could not load recent digest events: {exc}") from exc


def get_model_digest_section(limit: int = 3) -> str:
    """Returns a brief text block of recent model changes for the morning brief.

    A store outage is reported as an explicit "unavailable" note rather than
    a silently empty section.
    """
    try:
        events = _load_recent_events(limit=limit)
    except ModelDigestError as exc:
        logger.error("Model digest section unavailable: %s", exc)
        return "## Model News\n- \u26a0 model news unavailable"
    if not events:
        return ""
    lines = ["## Model News"]
    for e in events:
        icon = {"new_model": "\u2726", "price_drop": "\u2193", "price_increase": "\u2191"}.get(e["event_type"], "\u2022")
        lines.append(f"- {icon} {e['details']}")
    return "\n".join(lines)
