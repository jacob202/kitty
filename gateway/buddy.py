"""Buddy state — Kitty's persistent mood, energy, and session counters.

The UI polls GET /mood to get the current state instead of guessing from
message text. State survives across requests in memory and is snapshotted
to data/kitty/buddy_state.json on every write so it survives restarts.

Mood transitions:
  idle       — base state, no recent activity
  thinking   — set when a request starts
  success    — set when a response completes cleanly
  confused   — set when an error or drift violation occurs
  searching  — set when context retrieval is in progress
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Literal

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.buddy")

KittyMood = Literal["idle", "thinking", "success", "confused", "searching"]

_STATE_FILE = DATA_DIR / "kitty" / "buddy_state.json"

_state: dict = {
    "mood": "idle",
    "energy": 100,          # 0–100; drains with errors, recovers with rest
    "session_turns": 0,     # message pairs this session
    "total_turns": 0,       # lifetime turns
    "last_active_ts": 0.0,
    "drift_count": 0,
}

_SESSION_IDLE_SECONDS = 1800  # 30 min silence = reset session counters


def _load() -> None:
    try:
        if _STATE_FILE.exists():
            saved = json.loads(_STATE_FILE.read_text())
            _state.update(saved)
            _state["mood"] = "idle"  # always start calm on restart
    except Exception:
        pass


def _save() -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(_state))
    except Exception as exc:
        logger.debug("buddy state save failed: %s", exc)


_load()


def get_state() -> dict:
    return dict(_state)


def set_mood(mood: KittyMood) -> None:
    _state["mood"] = mood
    _state["last_active_ts"] = time.time()
    _save()


def on_request_start() -> None:
    """Call when a chat/ask request begins."""
    now = time.time()
    if now - _state["last_active_ts"] > _SESSION_IDLE_SECONDS:
        _state["session_turns"] = 0
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
    _state["mood"] = "confused"
    _state["energy"] = max(0, _state["energy"] - 5)
    _state["drift_count"] += 1
    _state["last_active_ts"] = time.time()
    _save()


def on_context_fetch() -> None:
    """Call while memory/knowledge retrieval is running."""
    _state["mood"] = "searching"
    _state["last_active_ts"] = time.time()
    _save()
