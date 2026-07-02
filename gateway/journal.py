"""Journal system — Kitty as interviewer, entry emerges from conversation.

Two modes:
- Ambient: every /ask is logged; no friction
- Intentional: Jacob triggers it, Kitty conducts a themed interview
"""

from __future__ import annotations

import logging
import random
import time
from typing import Optional

from gateway import journal_store
from gateway.paths import DATA_DIR
from gateway.prompts import JOURNAL_INTERVIEW_PROMPT, JOURNAL_SYNTHESIS_PROMPT

logger = logging.getLogger("kitty.journal")

# DEPRECATED: legacy read-only path for the JSONL fallback. SQLite
# (kitty.db / journal_entries table, via journal_store) is the canonical
# substrate. Retained only so the one-time legacy import in
# journal_store._import_legacy_journal_once can find its source file.
# New code MUST go through journal_store. Will be removed once Phase C
# retirement completes.
JOURNAL_LOG = DATA_DIR / "journal_entries.jsonl"


def save_journal_entry(entry: str, theme: str | None = None, session_id: str | None = None) -> dict:
    """Append a journal entry via journal_store. Kept for callers; see journal_store.append_entry."""
    return journal_store.append_entry(
        ts=time.time(),
        entry=entry,
        theme=theme,
        session_id=session_id,
    )


THEMES = ["recovery", "work", "mood", "relationships", "body", "creative", "reflection"]

_OPENERS: dict[str, list[str]] = {
    "recovery": [
        "How's the sleep been lately?",
        "What did your body feel like when you woke up this morning?",
        "When did you last feel genuinely rested?",
    ],
    "work": [
        "What are you actually working on right now — like the real thing, not the official answer?",
        "What's the thing on your list that keeps sliding?",
        "What did you build or figure out today?",
    ],
    "mood": [
        "What's the texture of today been like?",
        "When did you last feel really good? Not great, just... solid.",
        "What's been on your mind that you haven't said out loud yet?",
    ],
    "relationships": [
        "Who have you actually connected with lately?",
        "Is there someone you've been meaning to reach out to?",
        "What's the most interesting conversation you've had this week?",
    ],
    "body": [
        "How's the physical stuff going — gym, food, sleep, any of it?",
        "When did you last feel really in your body?",
        "What does your energy feel like right now, honestly?",
    ],
    "creative": [
        "What's something you made or started lately that you actually liked?",
        "What's an idea you've been sitting on?",
        "What would you build if it didn't have to be useful?",
    ],
    "reflection": [
        "What's something that happened recently that you're still thinking about?",
        "What surprised you about yourself this week?",
        "If this week had a title, what would it be?",
    ],
}

_PROMPTS: dict[str, list[str]] = {
    "recovery": [
        "Write about the last time you felt genuinely well-rested.",
        "Describe a day when your body and mind were working together.",
        "What does recovery actually look like for you?",
    ],
    "work": [
        "What are you building and why does it matter to you right now?",
        "Describe the best working session you've had in the past month.",
        "What would you work on if no one was watching?",
    ],
    "mood": [
        "What color is today? Explain it.",
        "Write about a small moment from the past week that stuck.",
        "What are you avoiding thinking about, and why?",
    ],
    "relationships": [
        "Write about someone who changed how you see something.",
        "Describe a conversation you keep returning to.",
        "Who are you becoming in relation to the people around you?",
    ],
    "body": [
        "Write about what your body has been telling you.",
        "When did you last feel strong? Describe it.",
        "What does taking care of yourself actually mean right now?",
    ],
    "creative": [
        "Describe something you made that surprised you.",
        "Write about an idea you're afraid to commit to.",
        "What would you create with no constraints?",
    ],
    "reflection": [
        "What's the most important thing you learned about yourself this month?",
        "Write a letter to yourself six months ago.",
        "What are you in the middle of that you'll look back on?",
    ],
}

_JOURNAL_TRIGGERS = [
    "journal",
    "interview me",
    "let's talk",
    "lets talk",
    "check in",
    "debrief",
    "how am i doing",
    "ask me",
    "tell me about my week",
    "end of day",
]


def is_journal_trigger(message: str) -> bool:
    text = message.lower().strip()
    return any(t in text for t in _JOURNAL_TRIGGERS)


def get_opener(theme: Optional[str] = None) -> str:
    if theme and theme in _OPENERS:
        return random.choice(_OPENERS[theme])
    return random.choice(_OPENERS[random.choice(THEMES)])


def get_random_prompt(theme: Optional[str] = None) -> dict:
    if not theme or theme not in _PROMPTS:
        theme = random.choice(THEMES)
    return {"theme": theme, "prompt": random.choice(_PROMPTS[theme])}


def build_interview_system_prompt(base_soul_prompt: str, theme: Optional[str] = None) -> str:
    theme_line = f"\n\nFocus area for this session: {theme}." if theme else ""
    return f"{base_soul_prompt}\n\n{JOURNAL_INTERVIEW_PROMPT}{theme_line}"


def build_synthesis_prompt() -> str:
    return JOURNAL_SYNTHESIS_PROMPT


def delete_journal_message(session_id: str, message_id: str) -> bool:
    """Delete a specific message from the journal by session_id and message_id.

    The message_id is compared against the entry's 'ts' field. Backed by
    journal_store (kitty.db) since Phase C B.
    """
    try:
        target_ts = float(message_id)
    except (ValueError, TypeError):
        logger.warning("Invalid message_id for journal delete: %s", message_id)
        return False

    deleted = journal_store.delete_entry(ts=target_ts, session_id=session_id)
    if deleted:
        logger.info("Journal message deleted: session=%s ts=%s", session_id, message_id)
    return deleted


def search_entries(query: str, limit: int = 5) -> list[dict]:
    """Keyword search over journal entries for memory_graph / search.

    Backed by journal_store (kitty.db) since Phase C B.
    """
    return journal_store.search(query=query, limit=limit)


def recent_entries(days: int = 14, limit: int = 20) -> list[dict]:
    """Return the most recent journal entries within the last `days` days.

    Used by the brief-context-shaping theme detector. Newest first.
    Returns [] on any read error. Backed by journal_store (kitty.db)
    since Phase C B.
    """
    return journal_store.list_recent(days=days, limit=limit)
