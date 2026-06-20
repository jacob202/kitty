"""Journal system — Kitty as interviewer, entry emerges from conversation.

Two modes:
- Ambient: every /ask is logged; no friction
- Intentional: Jacob triggers it, Kitty conducts a themed interview
"""

from __future__ import annotations

import json
import logging
import random
import time
import tempfile
from pathlib import Path
from typing import Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.journal")

JOURNAL_LOG = DATA_DIR / "journal_entries.jsonl"


def save_journal_entry(
    entry: str, theme: str | None = None, session_id: str | None = None
) -> dict:
    record = {"ts": time.time(), "theme": theme, "entry": entry}
    if session_id:
        record["session_id"] = session_id
    JOURNAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL_LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record


THEMES = ["recovery", "work", "mood", "relationships", "body", "creative", "reflection"]

# Kitty's interviewer persona — curious journalist, not therapist
INTERVIEW_SYSTEM_PROMPT = """\
You are conducting a journal interview with Jacob. Your job is to be a curious,
attentive interviewer — not a therapist. You are not trying to fix anything.

Rules:
- Ask ONE question at a time. Only ever one.
- Start casual and specific. Not "how are you feeling today."
- Reference things you know about Jacob when you can.
- Follow threads. If he mentions something interesting, go there first.
- Never announce you're journaling or interviewing. Just talk.
- When the conversation has enough material (typically 6–10 exchanges), close naturally."""

# Synthesis prompt — turns transcript into a first-person entry in Jacob's voice
SYNTHESIS_PROMPT = """\
You have just conducted a journal interview with Jacob.
Synthesize the conversation into a journal entry written from his perspective.

Rules:
- Write AS Jacob, first person, his voice and phrasing.
- Capture specifics he actually said — not summaries or paraphrases.
- Keep his exact wording where it's vivid.
- One to three paragraphs, no headers, no bullet points.
- End where the conversation ended. No forced resolution.
- Do not add insights he didn't express himself.
- Do not editorialize."""

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


def build_interview_system_prompt(
    base_soul_prompt: str, theme: Optional[str] = None
) -> str:
    theme_line = f"\n\nFocus area for this session: {theme}." if theme else ""
    return f"{base_soul_prompt}\n\n{INTERVIEW_SYSTEM_PROMPT}{theme_line}"


def build_synthesis_prompt() -> str:
    return SYNTHESIS_PROMPT


def delete_journal_message(session_id: str, message_id: str) -> bool:
    """Delete a specific message from the journal by session_id and message_id.

    Journal entries are stored as JSONL lines with fields: ts, theme, entry.
    Since JSONL has no native delete, we rewrite the file excluding the target entry.
    The message_id is compared against the 'ts' field (stored as the message timestamp).
    """
    if not JOURNAL_LOG.exists():
        return False

    target_ts = None
    try:
        target_ts = float(message_id)
    except (ValueError, TypeError):
        logger.warning("Invalid message_id for journal delete: %s", message_id)
        return False

    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(dir=JOURNAL_LOG.parent, suffix=".jsonl.tmp")
        found = False
        with open(JOURNAL_LOG, "r") as src, open(tmp_fd, "w") as dst:
            for line in src:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    dst.write(line + "\n")
                    continue
                record_session_id = record.get("session_id")
                if record_session_id and str(record_session_id) != session_id:
                    dst.write(line + "\n")
                    continue

                if float(record.get("ts", 0)) == target_ts:
                    found = True
                    continue
                dst.write(line + "\n")

        if not found:
            return False

        # Atomic replace
        with open(tmp_path, "r") as tmp_src:
            content = tmp_src.read()
        with open(JOURNAL_LOG, "w") as final_dst:
            final_dst.write(content)

        logger.info("Journal message deleted: session=%s ts=%s", session_id, message_id)
        return True

    except Exception as e:
        logger.warning("Journal delete failed (non-fatal): %s", e)
        return False
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink(missing_ok=True)


def search_entries(query: str, limit: int = 5) -> list[dict]:
    """Keyword search over journal entries for memory_graph / search."""
    try:
        if not JOURNAL_LOG.exists():
            return []
        terms = query.lower().split()
        matches: list[dict] = []
        with JOURNAL_LOG.open("r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entry_text = entry.get("entry", "").lower()
                score = sum(1 for t in terms if t in entry_text)
                if score > 0:
                    entry["_score"] = score
                    matches.append(entry)
        matches.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return matches[:limit]
    except Exception as e:
        logger.warning("Journal search failed: %s", e)
        return []


def recent_entries(days: int = 14, limit: int = 20) -> list[dict]:
    """Return the most recent journal entries within the last `days` days.

    Used by the brief-context-shaping theme detector. Newest first.
    Returns [] if the journal is empty, the log file is missing, or any
    read error occurs. Failures are logged but never raised — the brief
    is best-effort, and the caller treats [] as "no themes detected."
    """
    try:
        if not JOURNAL_LOG.exists():
            return []
        cutoff = time.time() - (days * 86400)
        entries: list[dict] = []
        with JOURNAL_LOG.open("r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = entry.get("ts", 0)
                if ts >= cutoff:
                    entries.append(entry)
        entries.sort(key=lambda e: e.get("ts", 0), reverse=True)
        return entries[:limit]
    except Exception as e:
        logger.warning("Journal recent-entries failed: %s", e)
        return []
