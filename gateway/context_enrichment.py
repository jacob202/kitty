"""Live-state enrichment appended after memory_graph unified context.

Each source fails silently — optional macOS integrations must not break prompts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

logger = logging.getLogger("kitty.context_enrichment")

EnrichmentFn = Callable[[str], Awaitable[str | None]]


def _append(base: str, block: str, *, join: str = "\n\n") -> str:
    if not block:
        return base
    if base:
        return f"{base}{join}{block}"
    return block


async def _calendar_block(_message: str) -> str | None:
    from gateway.calendar_integration import get_upcoming_text, is_available

    if not is_available():
        return None
    return await asyncio.to_thread(get_upcoming_text, 3)


async def _weather_block(_message: str) -> str | None:
    from gateway.weather import get_weather_text

    return await asyncio.to_thread(get_weather_text)


async def _todos_block(_message: str) -> str | None:
    from gateway.todo_store import get_todos_text

    return get_todos_text()


async def _imessage_block(_message: str) -> str | None:
    from gateway.imessage import get_recent_text, is_available

    if not is_available():
        return None
    return await asyncio.to_thread(get_recent_text, 4)


async def _health_block(_message: str) -> str | None:
    from gateway.health_parser import get_health_text

    return get_health_text()


async def _ambient_block(_message: str) -> str | None:
    from gateway.ambient import get_ambient_text

    return get_ambient_text()


async def _patterns_block(_message: str) -> str | None:
    from gateway.patterns import get_insight_text

    return await asyncio.to_thread(get_insight_text, 30)


async def _learning_block(_message: str) -> str | None:
    from gateway.learning import init_stats

    stats = init_stats()
    level = stats.get("user_level", 1)
    score = stats.get("absorption_score", 0)
    mastered = stats.get("topics_mastered", [])
    if level <= 1 and score <= 0 and not mastered:
        return None
    parts = [f"[Learning] Level {level}, absorption {score}/100"]
    if mastered:
        parts.append(f"mastered: {', '.join(mastered[:5])}")
    return " — ".join(parts)


async def _nudges_block(_message: str) -> str | None:
    from gateway.nudge import get_pending

    pending = get_pending()
    if not pending:
        return None
    lines = "\n".join(f"- {n['message']}" for n in pending[:2])
    return f"[PENDING NUDGES]\n{lines}"


_ENRICHMENTS: tuple[EnrichmentFn, ...] = (
    _calendar_block,
    _weather_block,
    _todos_block,
    _imessage_block,
    _health_block,
    _ambient_block,
    _patterns_block,
    _learning_block,
    _nudges_block,
)


async def enrich_dynamic_context(base: str, message: str) -> str:
    """Append live-state blocks to unified memory_graph context."""
    dynamic_context = base
    for fetch in _ENRICHMENTS:
        try:
            block = await fetch(message)
            if block:
                join = "\n" if fetch is _weather_block else "\n\n"
                dynamic_context = _append(dynamic_context, block, join=join)
        except Exception as exc:
            logger.debug("Enrichment skipped: %s", exc)

    from gateway import voice_gate

    nudge = voice_gate.get_drift_nudge()
    if nudge:
        dynamic_context = (dynamic_context + nudge) if dynamic_context else nudge

    return dynamic_context


# Sync helpers for brief synthesis (same sources as async enrichment blocks)
def weather_text_sync() -> str:
    try:
        from gateway.weather import get_weather_text

        return get_weather_text() or ""
    except Exception:
        return ""


def todos_text_sync() -> str:
    try:
        from gateway.todo_store import get_todos_text

        return get_todos_text() or ""
    except Exception:
        return ""


def calendar_today_text_sync() -> str:
    """Today's calendar events as a formatted string for brief prompts."""
    try:
        from gateway.calendar_integration import get_today, is_available

        if not is_available():
            return ""
        events = get_today()
        if not events:
            return ""
        lines = ["Today's Schedule:"] + [
            f"- {e.get('start', '')}: {e.get('title', '')}" for e in events[:8]
        ]
        return "\n".join(lines)
    except Exception:
        return ""
