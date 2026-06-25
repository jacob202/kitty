"""Self-review signals — feed Kitty's soul evolution.

Three logs written to data/kitty/:
- drift_log.jsonl     — does Kitty sound like herself? (SOUL.md rule compliance)
- reaction_log.jsonl  — how did Jacob respond? (reply length, signal type)
- session_arc.jsonl   — did the session help? (energy start vs end)

These feed SOUL_SCRATCHPAD.md. Kitty reads them to understand what's working.
"""
from __future__ import annotations

import json
import logging
import time

logger = logging.getLogger("kitty.self_review")

from gateway.paths import CONFIG_DIR
from gateway.paths import DATA_DIR as _GATEWAY_DATA_DIR

DATA_DIR = _GATEWAY_DATA_DIR / "kitty"
DRIFT_LOG = DATA_DIR / "drift_log.jsonl"
REACTION_LOG = DATA_DIR / "reaction_log.jsonl"
SESSION_ARC_LOG = DATA_DIR / "session_arc.jsonl"
SOUL_SCRATCHPAD = CONFIG_DIR / "SOUL_SCRATCHPAD.md"

# Session gap: 30 minutes of silence = new session
SESSION_TIMEOUT_SECONDS = 1800

# SOUL.md behavioral rules — phrases Kitty must never use
_BANNED_PHRASES = [
    "certainly!",
    "great question",
    "i'd be happy to help",
    "as an ai",
    "i am an ai",
    "i don't have feelings",
    "i cannot",
    "i'm just an ai",
]

# Phrases that suggest unearned agreement
_AGREEMENT_OPENERS = [
    "you're absolutely right",
    "absolutely!",
    "you're right,",
    "i completely agree",
    "that's a great point",
    "great idea",
    "wonderful",
]

# Reaction signal types (inferred from Jacob's message content)
_CORRECTION_SIGNALS = ["no,", "that's wrong", "actually,", "not quite", "incorrect", "you missed"]
_REDIRECT_SIGNALS = ["anyway,", "forget that", "never mind", "different question", "moving on"]


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _append(path: Path, record: dict) -> None:
    _ensure_dir()
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# T17 — Kitty drift tracking
# ---------------------------------------------------------------------------

def log_drift(kitty_response: str) -> dict:
    """Check Kitty's response against SOUL.md behavioral rules. Log result."""
    text = kitty_response.lower()

    violations = []
    for phrase in _BANNED_PHRASES:
        if phrase in text:
            violations.append(f"banned_phrase: {phrase!r}")
    for opener in _AGREEMENT_OPENERS:
        if text.startswith(opener):
            violations.append(f"unearned_agreement: {opener!r}")

    record = {
        "ts": time.time(),
        "pass": len(violations) == 0,
        "violations": violations,
        "response_length": len(kitty_response),
    }
    _append(DRIFT_LOG, record)
    if violations:
        logger.warning("soul drift detected: %s", violations)
    return record


# ---------------------------------------------------------------------------
# T18 — Jacob reaction quality
# ---------------------------------------------------------------------------

def _classify_signal(message: str) -> str:
    text = message.lower()
    if any(s in text for s in _CORRECTION_SIGNALS):
        return "correction"
    if any(s in text for s in _REDIRECT_SIGNALS):
        return "redirect"
    if len(message) < 20:
        return "short"
    if len(message) > 200:
        return "deep_engagement"
    return "engagement"


def log_reaction(jacob_message: str, prev_kitty_length: int | None = None) -> dict:
    """Log Jacob's reply as a signal about the previous Kitty response."""
    record = {
        "ts": time.time(),
        "jacob_length": len(jacob_message),
        "prev_kitty_length": prev_kitty_length,
        "signal": _classify_signal(jacob_message),
    }
    _append(REACTION_LOG, record)
    return record


# ---------------------------------------------------------------------------
# T19 — Session arc tracking
# ---------------------------------------------------------------------------

_session_state: dict = {}


def _get_session_id() -> str:
    """Return current session ID, starting a new one after SESSION_TIMEOUT_SECONDS."""
    now = time.time()
    last = _session_state.get("last_ts", 0)
    if now - last > SESSION_TIMEOUT_SECONDS:
        _session_state["id"] = f"session_{int(now)}"
        _session_state["start_ts"] = now
        _session_state["message_count"] = 0
        _session_state["start_length"] = None
    _session_state["last_ts"] = now
    return _session_state["id"]


def _energy_proxy(message: str) -> float:
    """Rough energy signal: longer + more punctuation = more engaged."""
    return len(message) + message.count("!") * 5 + message.count("?") * 3


def log_session_arc(jacob_message: str, kitty_response: str) -> None:
    """Track session energy from start to end. Writes arc record on session close."""
    sid = _get_session_id()
    count = _session_state.get("message_count", 0)
    energy = _energy_proxy(jacob_message)

    if count == 0:
        _session_state["start_energy"] = energy
        _session_state["start_length"] = len(jacob_message)

    _session_state["message_count"] = count + 1
    _session_state["last_energy"] = energy
    _session_state["last_length"] = len(jacob_message)

    # Write arc snapshot every 5 messages (not just at session end, which we can't detect)
    if _session_state["message_count"] % 5 == 0:
        record = {
            "ts": time.time(),
            "session_id": sid,
            "message_count": _session_state["message_count"],
            "start_energy": _session_state.get("start_energy", 0),
            "current_energy": energy,
            "delta": energy - _session_state.get("start_energy", energy),
        }
        _append(SESSION_ARC_LOG, record)


def _append_scratchpad(note: str) -> None:
    """Append a timestamped note to SOUL_SCRATCHPAD.md."""
    import datetime
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    SOUL_SCRATCHPAD.parent.mkdir(parents=True, exist_ok=True)
    with SOUL_SCRATCHPAD.open("a") as f:
        f.write(f"\n---\n*{ts}*\n{note}\n")


def record_interaction(
    jacob_message: str,
    kitty_response: str,
    prev_kitty_length: int | None = None,
) -> None:
    """Single call to log all three signals after an interaction. Fire and forget."""
    drift_record = None
    try:
        drift_record = log_drift(kitty_response)
    except Exception:
        logger.warning("drift log failed", exc_info=True)
    try:
        log_reaction(jacob_message, prev_kitty_length)
    except Exception:
        logger.warning("reaction log failed", exc_info=True)
    try:
        log_session_arc(jacob_message, kitty_response)
    except Exception:
        logger.warning("session arc log failed", exc_info=True)
    try:
        if drift_record and not drift_record["pass"]:
            violations = ", ".join(drift_record["violations"])
            _append_scratchpad(
                f"Soul drift detected — {violations}. "
                f"Response was {drift_record['response_length']} chars."
            )
    except Exception:
        logger.warning("scratchpad write failed", exc_info=True)
