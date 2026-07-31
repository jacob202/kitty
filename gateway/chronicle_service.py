"""Pure session-history analysis for the chronicle feature.

All functions here are side-effect-free: they accept raw chat dicts and
return structured data.  No FastAPI or storage dependencies live in this
module — that makes the logic independently testable and reusable.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _extract_words(text: str) -> list[str]:
    """Return lowercase alphabetic words of three or more characters."""
    return re.findall(r"[a-z]{3,}", text.lower())


_STOP_WORDS = frozenset(
    [
        "the", "and", "for", "that", "this", "with", "can", "you",
        "are", "was", "have", "not", "but", "your", "all", "from",
        "its", "out", "has", "get", "how", "about", "what", "just",
        "when", "who", "use", "would", "like", "also", "into", "some",
        "will", "been", "did", "they", "then", "there", "than",
        "more", "any", "one", "our", "said", "her", "his",
    ]
)


def top_topics(chats: list[dict]) -> list[str]:
    """Return the top three recurring content words across all chat titles."""
    word_counts: Counter[str] = Counter()
    for chat in chats:
        title = chat.get("title") or ""
        for word in _extract_words(title):
            if word not in _STOP_WORDS:
                word_counts[word] += 1
    return [w for w, _ in word_counts.most_common(3)]


def hourly_distribution(chats: list[dict]) -> dict[int, int]:
    """Return a mapping of hour-of-day → number of chats started that hour."""
    hours: dict[int, int] = defaultdict(int)
    for chat in chats:
        created_raw = chat.get("createdAt") or chat.get("created_at")
        if not created_raw:
            continue
        try:
            if isinstance(created_raw, (int, float)):
                dt = datetime.fromtimestamp(created_raw, tz=timezone.utc)
            else:
                dt = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
            hours[dt.hour] += 1
        except (ValueError, OSError):
            continue
    return dict(hours)


def session_lengths(chats: list[dict]) -> list[int]:
    """Return a list of message counts per chat session."""
    return [
        len(c.get("messages") or [])
        for c in chats
        if isinstance(c.get("messages"), list)
    ]


def model_usage(chats: list[dict]) -> dict[str, int]:
    """Return a tally of chat counts per model (top five)."""
    counts: Counter[str] = Counter()
    for chat in chats:
        model = chat.get("model") or "unknown"
        counts[model] += 1
    return dict(counts.most_common(5))


def messages_count(chats: list[dict]) -> int:
    return sum(len(c.get("messages") or []) for c in chats)


# ---------------------------------------------------------------------------
# Tip generators — each returns a string tip or None
# ---------------------------------------------------------------------------

def _tip_volume(chat_count: int, message_count: int) -> str | None:
    if chat_count == 0:
        return "Start your first session — Kitty learns from every conversation."
    if chat_count < 5:
        return (
            "You're just getting started. The more you chat, the better Kitty "
            "understands your working style."
        )
    if message_count > 200:
        return (
            f"You've exchanged {message_count} messages across {chat_count} sessions — "
            "great engagement! Consider using /journal to capture the insights you "
            "keep coming back to."
        )
    return None


def _tip_session_length(lengths: list[int]) -> str | None:
    if not lengths:
        return None
    avg = sum(lengths) / len(lengths)
    short_sessions = sum(1 for l in lengths if l <= 2)
    if short_sessions / len(lengths) > 0.5:
        return (
            "Many of your sessions are short exchanges. Try opening a longer thread "
            "when working through a problem — context builds up and Kitty's replies "
            "improve with more turns in the same conversation."
        )
    if avg > 20:
        return (
            f"Your average session runs about {avg:.0f} messages. Long threads are "
            "great for depth, but a fresh chat can give Kitty a cleaner context window "
            "when you switch topics."
        )
    return None


def _tip_peak_hour(hourly: dict[int, int]) -> str | None:
    if not hourly:
        return None
    peak_hour = max(hourly, key=lambda h: hourly[h])
    if hourly[peak_hour] < 2:
        return None
    period = "morning" if peak_hour < 12 else ("afternoon" if peak_hour < 18 else "evening")
    return (
        f"You tend to be most active around {peak_hour:02d}:00 ({period}). "
        "Scheduling a standing brief with Kitty at that time can help prime your day."
    )


def _tip_topics(topics: list[str]) -> str | None:
    if not topics:
        return None
    topic_str = ", ".join(topics)
    return (
        f"Your recurring themes are: {topic_str}. "
        "You can capture standing knowledge about these by adding memories with "
        "/memory, so Kitty surfaces the right context automatically."
    )


def _tip_model(model_counts: dict[str, int]) -> str | None:
    if len(model_counts) <= 1:
        return (
            "You're using a single model for everything. Try assigning a faster model "
            "for quick questions in your settings — it saves time and cost."
        )
    return None


def _tip_journaling(chats: list[dict]) -> str | None:
    has_objective = any(c.get("objective") for c in chats)
    if not has_objective and len(chats) >= 3:
        return (
            "None of your sessions have a thread goal set. Use the thread goal field "
            "(the flag icon in the chat header) to anchor longer conversations and "
            "help Kitty stay focused."
        )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze(chats: list[dict]) -> dict[str, Any]:
    """Derive usage signals from *chats* and return tips + a summary.

    This is the single entry-point the HTTP handler should call.  It is
    intentionally free of side-effects so it can be called from tests
    with arbitrary fixture data.

    Returns::

        {
          "tip_count": int,
          "tips": [str, ...],
          "summary": {
              "session_count": int,
              "message_count": int,
              "top_topics": [str, ...],
              "peak_hour": int | None,
              "model_spread": int,
          },
        }
    """
    chat_count = len(chats)
    msg_count = messages_count(chats)
    lengths = session_lengths(chats)
    hourly = hourly_distribution(chats)
    topics = top_topics(chats)
    model_counts = model_usage(chats)

    candidates: list[str] = []
    for tip in [
        _tip_volume(chat_count, msg_count),
        _tip_session_length(lengths),
        _tip_peak_hour(hourly),
        _tip_topics(topics),
        _tip_model(model_counts),
        _tip_journaling(chats),
    ]:
        if tip is not None:
            candidates.append(tip)

    return {
        "tip_count": len(candidates),
        "tips": candidates,
        "summary": {
            "session_count": chat_count,
            "message_count": msg_count,
            "top_topics": topics,
            "peak_hour": max(hourly, key=lambda h: hourly[h]) if hourly else None,
            "model_spread": len(model_counts),
        },
    }
