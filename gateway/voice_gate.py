"""Voice Gate — pre-response filter enforcing SOUL.md compliance before user sees output.

Two layers:
- filter(response_text) -> cleaned_text: Strip banned phrases, return clean + drift report.
- check(text) -> VoiceGateResult: Inspect without modifying (for streaming or logging).

The gate runs BEFORE any response reaches the user. If drift is detected, the
response is cleaned and the incident is logged to self_review for pattern tracking.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("kitty.voice_gate")

# --- Configuration ---

# Banned phrases — any match strips the phrase and surrounding context
_BANNED_PHRASES: list[str] = [
    "certainly!",
    "great question",
    "i'd be happy to help",
    "as an ai",
    "i am an ai",
    "i don't have feelings",
    "i cannot",
    "i'm just an ai",
    "how can i assist you",
    "let me assist with that",
]

# Unearned agreement openers — phrases that start with these are flagged
_AGREEMENT_OPENERS: list[str] = [
    "you're absolutely right",
    "absolutely!",
    "you're right,",
    "i completely agree",
    "that's a great point",
    "great idea",
    "wonderful",
]

# Apology / hedge patterns to flag
_HEDGE_PATTERNS: list[str] = [
    "i apologize",
    "i'm sorry",
    "some might say",
    "it could be argued",
    "i would suggest",
]

# Over-enthusiasm: !!! or multiple emoji-like patterns
_OVER_ENTHUSIASM = re.compile(r"!!!|🎉|🔥|💯")


@dataclass
class VoiceGateResult:
    """Outcome of a voice gate check."""
    passed: bool
    original: str
    cleaned: str
    violations: list[str] = field(default_factory=list)
    severity: str = "none"  # none, mild, moderate, severe


def check(text: str) -> VoiceGateResult:
    """Inspect text for SOUL.md violations. Returns result without modifying."""
    violations: list[str] = []
    lower = text.lower().strip()

    for phrase in _BANNED_PHRASES:
        if phrase in lower:
            violations.append(f"banned_phrase: {phrase!r}")

    for opener in _AGREEMENT_OPENERS:
        if lower.startswith(opener):
            violations.append(f"unearned_agreement: {opener!r}")

    for hedge in _HEDGE_PATTERNS:
        if hedge in lower:
            violations.append(f"hedge: {hedge!r}")

    if _OVER_ENTHUSIASM.search(text):
        violations.append("over_enthusiasm")

    severity = "none"
    if violations:
        severity = "mild" if len(violations) <= 1 else "moderate" if len(violations) <= 3 else "severe"

    return VoiceGateResult(
        passed=len(violations) == 0,
        original=text,
        cleaned=text,
        violations=violations,
        severity=severity,
    )


def filter_response(text: str) -> VoiceGateResult:
    """Clean a response before sending to user. Strip banned phrases, log drift."""
    result = check(text)
    if result.passed:
        return result

    cleaned = text

    # Strip banned phrases — replace with nothing, clean up double spaces
    for phrase in _BANNED_PHRASES:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        cleaned = pattern.sub("", cleaned)

    # Strip over-enthusiasm punctuation
    cleaned = _OVER_ENTHUSIASM.sub("", cleaned)

    # Clean up artifacts: double spaces, leading commas, empty lines
    cleaned = re.sub(r"  +", " ", cleaned)
    cleaned = re.sub(r"^[,\s]+", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    
    # Strip lonely punctuation at the end (e.g., a '?' left over from 'How can I assist you?')
    cleaned = re.sub(r"\s+[?.!,]+$", "", cleaned)
    
    cleaned = cleaned.strip()

    # If we stripped everything, fall back to original (better than empty)
    if not cleaned:
        cleaned = text

    result.cleaned = cleaned
    result.passed = cleaned == text

    # Log to self_review
    try:
        from gateway.self_review import log_drift
        log_drift(text)
    except Exception:
        logger.warning("voice_gate: failed to log drift", exc_info=True)

    logger.warning("voice_gate: filtered %d violation(s): %s", len(result.violations), result.violations)
    return result


# --- Correction nudge — appended to system prompt when drift accumulates ---

_drift_count: int = 0
_DRIFT_THRESHOLD: int = 3  # after this many drifts in a session, nudge


def get_drift_nudge() -> Optional[str]:
    """Return a correction nudge if drift threshold has been exceeded this session.
    
    Call this when building the system prompt. If Kitty has drifted 3+ times,
    append a reminder to stay in character.
    """
    global _drift_count
    if _drift_count >= _DRIFT_THRESHOLD:
        return (
            "\n\n[SYSTEM NOTE: You've drifted from your voice a few times this session. "
            "Re-read SOUL.md rules. No 'Certainly!', no corporate-speak, no unearned agreement. "
            "Be the friend who's actually paying attention.]"
        )
    return None


def record_drift() -> None:
    """Increment the session drift counter. Call after filtering a response."""
    global _drift_count
    _drift_count += 1


def reset_drift_counter() -> None:
    """Reset drift counter (e.g. on new session)."""
    global _drift_count
    _drift_count = 0
