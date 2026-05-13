"""Context Compactor — smart conversation summarization to prevent context overflow.

Port of free-code's COMPACTION_REMINDERS pattern. Detects when the context
window is filling up, generates a compressed summary of conversation history,
and injects it back as a system message.

Public API:
  should_compact(messages, max_tokens) -> bool
  compact(messages) -> list[dict]     Compress message history
  estimate_tokens(text) -> int        Rough token count
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("kitty.context_compactor")

DEFAULT_MAX_TOKENS: int = 8000
COMPACT_THRESHOLD: float = 0.8  # compact at 80% of max

# Messages to always keep (system prompt + last N turns)
KEEP_SYSTEM: bool = True
KEEP_LAST_N: int = 4  # keep the last 4 messages (2 turns)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list[dict]) -> int:
    """Estimate total tokens across all messages."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    total += estimate_tokens(part["text"])
    return total


def should_compact(
    messages: list[dict],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> bool:
    """Check if message history should be compacted."""
    if len(messages) <= KEEP_LAST_N + 2:
        return False  # not enough to compact

    estimated = estimate_messages_tokens(messages)
    return estimated >= max_tokens * COMPACT_THRESHOLD


def compact(messages: list[dict]) -> list[dict]:
    """Compress message history into a compact form.

    Strategy:
    - Keep the system message
    - Summarize middle messages into a single system note
    - Keep the last N messages intact
    """
    if len(messages) <= KEEP_LAST_N + 2:
        return messages

    system = messages[0] if messages[0].get("role") == "system" else None
    start = 1 if system else 0

    if len(messages) - start <= KEEP_LAST_N:
        return messages

    middle = messages[start:-KEEP_LAST_N]
    recent = messages[-KEEP_LAST_N:]
    if system:
        recent = [system] + recent

    # Generate summary of middle messages
    summary = _generate_summary(middle)

    # Build compacted list
    compacted = []
    if system:
        system_content = system.get("content", "")
        compacted.append({
            "role": "system",
            "content": f"{system_content}\n\n[Earlier conversation summary: {summary}]",
        })
    else:
        compacted.append({
            "role": "system",
            "content": f"[Earlier conversation summary: {summary}]",
        })

    compacted.extend(recent[-KEEP_LAST_N:] if system else recent)
    return compacted


def _generate_summary(messages: list[dict]) -> str:
    """Generate a brief summary of middle conversation messages."""
    user_msgs = []
    assistant_msgs = []

    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip():
            if msg.get("role") == "user":
                user_msgs.append(content[:200])
            elif msg.get("role") == "assistant":
                assistant_msgs.append(content[:200])

    parts = []
    if user_msgs:
        topics = "; ".join(user_msgs[:5])
        parts.append(f"User discussed: {topics}")
    if assistant_msgs:
        parts.append(f"Assistant helped with {len(assistant_msgs)} responses")

    if not parts:
        return f"{len(messages)} messages exchanged"

    return ". ".join(parts) + f". ({len(messages)} total messages compacted)"


def get_compaction_notice(messages_before: int, messages_after: int, tokens_saved: int) -> str:
    """Return a user-facing notice about compaction."""
    return (
        f"Context compacted: {messages_before} messages → {messages_after} "
        f"(~{tokens_saved} tokens freed). Key points preserved."
    )
