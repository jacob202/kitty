"""Session State — unified tracking for Kitty's mood, energy, and drift.

This is a DEEP module that consolidates:
- Buddy's mood/energy tracking (mood, energy, session_turns, total_turns)
- Voice gate's drift counter (session-based drift for nudge generation)
- Request lifecycle hooks (start/success/error)

Callers should use:
- get_state() -> dict: Get current state for UI
- on_request_start(): Call at request start
- on_request_success(): Call on successful response
- on_request_error(): Call on error or drift violation
- get_drift_nudge(): Get nudge text if drift threshold exceeded
- record_drift(): Record a drift violation (for voice gate)

The drift nudge is session-local (resets after 30 min idle).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Literal, Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.session_state")

KittyMood = Literal["idle", "thinking", "success", "confused", "searching"]

_STATE_FILE = DATA_DIR / "kitty" / "session_state.json"
_SESSION_IDLE_SECONDS = 1800  # 30 min silence = reset session counters
_DRIFT_THRESHOLD = 3  # after this many drifts in a session, show nudge

# In-memory state
_state: dict = {
    "mood": "idle",
    "energy": 100,  # 0–100; drains with errors, recovers with rest
    "session_turns": 0,  # message pairs this session
    "total_turns": 0,  # lifetime turns
    "last_active_ts": 0.0,
    "drift_count": 0,  # lifetime drift violations
}

# Session-local drift counter (resets on session end)
_session_drift: int = 0


def _load() -> None:
    """Load persisted state from disk."""
    global _state
    try:
        if _STATE_FILE.exists():
            saved = json.loads(_STATE_FILE.read_text())
            _state.update(saved)
            _state["mood"] = "idle"  # always start calm on restart
    except Exception:
        pass


def _save() -> None:
    """Persist state to disk."""
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(_state))
    except Exception as exc:
        logger.debug("session_state save failed: %s", exc)


def _reset_session_drift() -> None:
    """Reset session-local drift counter."""
    global _session_drift
    _session_drift = 0


# Initialize on module load
_load()


def get_state() -> dict:
    """Get current state for UI display."""
    return dict(_state)


def set_mood(mood: KittyMood) -> None:
    """Set mood directly."""
    _state["mood"] = mood
    _state["last_active_ts"] = time.time()
    _save()


def on_request_start() -> None:
    """Call when a request begins (any endpoint)."""
    global _session_drift
    now = time.time()
    if now - _state["last_active_ts"] > _SESSION_IDLE_SECONDS:
        _state["session_turns"] = 0
        _session_drift = 0
    _state["mood"] = "thinking"
    _state["last_active_ts"] = now
    _save()


def on_request_success() -> None:
    """Call when a response is delivered cleanly."""
    _state["mood"] = "success"
    _state["session_turns"] += 1
    _state["total_turns"] += 1
    _state["energy"] = min(100, _state["energy"] + 1)
    _state["last_active_ts"] = time.time()
    _save()


def on_request_error() -> None:
    """Call on any error or drift violation."""
    global _session_drift
    _state["mood"] = "confused"
    _state["energy"] = max(0, _state["energy"] - 5)
    _state["drift_count"] += 1
    _session_drift += 1
    _state["last_active_ts"] = time.time()
    _save()


def on_context_fetch() -> None:
    """Call while memory/knowledge retrieval is running."""
    _state["mood"] = "searching"
    _state["last_active_ts"] = time.time()
    _save()


def get_drift_nudge() -> Optional[str]:
    """Return a correction nudge if drift threshold has been exceeded this session.

    Call this when building the system prompt. If Kitty has drifted
    3+ times this session, append a reminder to stay in character.
    """
    if _session_drift >= _DRIFT_THRESHOLD:
        return (
            "\n\n[SYSTEM NOTE: You've drifted from your voice a few times this session. "
            "Re-read SOUL.md rules. No 'Certainly!', no corporate-speak, no unearned agreement. "
            "Be the friend who's actually paying attention.]"
        )
    return None


def record_drift() -> None:
    """Record a drift violation (for voice gate)."""
    on_request_error()


def reset_drift_counter() -> None:
    """Reset drift counter (e.g. on new session)."""
    global _session_drift
    _session_drift = 0
    _save()


# --- Legacy compatibility: re-export buddy functions ---
# Existing callers from buddy.py can import these directly


def get_buddy_state() -> dict:
    """Legacy: get_state for buddy compatibility."""
    return get_state()
