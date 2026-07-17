"""Live-state enrichment appended after memory_graph unified context.

Phase 2 deepening (per
``docs/superpowers/specs/2026-06-24-gateway-deepening-program-design.md``):
the assembler owns the read path. This module exposes two surfaces:

- :func:`run_enrichments` — the orchestrator-friendly entry point. Runs
  every enrichment in :data:`DEFAULT_ENRICHMENTS` against ``message``,
  catches per-source failures, and returns ``(blocks, warnings)``.
  Each warning is a human-readable string the assembler surfaces on the
  ``ContextBundle``. Failures are no longer silent (line 118 of the
  pre-Phase 2 code used ``logger.debug``; that is now ``logger.warning``
  and the warning propagates).

- :func:`enrich_dynamic_context` — legacy single-string return shape,
  kept for backward compatibility with any caller that still imports
  it. New code should use :func:`run_enrichments`.

The voice-gate drift nudge is intentionally absent here — it is a
*response-time* concern, not request-time. It belongs in
``routes/completions.py`` after the LLM reply, not in the context
assembler.
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

# Public alias used by ``gateway.context_assembler``.
DEFAULT_ENRICHMENTS: tuple[EnrichmentFn, ...] = _ENRICHMENTS


async def run_enrichments(
    enrichments: tuple[EnrichmentFn, ...], message: str
) -> tuple[list[str], list[str]]:
    """Run every enrichment in ``enrichments`` against ``message``.

    Returns ``(blocks, warnings)``. ``blocks`` is the list of non-empty
    text blocks (in input order, with ``None`` blocks dropped). Each
    per-source failure produces a warning string of the form
    ``{fn_name}: {exc_type}: {message}``. The assembler copies the
    warnings onto the :class:`ContextBundle`.

    Per-source failures never raise. The orchestrator is the only place
    that decides whether a partial result is fatal.
    """
    blocks: list[str] = []
    warnings: list[str] = []
    coros = [fn(message) for fn in enrichments]
    raw = await asyncio.gather(*coros, return_exceptions=True)
    for fn, res in zip(enrichments, raw):
        if isinstance(res, BaseException):
            logger.warning("enrichment failed: %s: %s", fn.__name__, res)
            warnings.append(f"{fn.__name__}: {type(res).__name__}: {res}")
            continue
        if res:
            blocks.append(res)
    return blocks, warnings


async def enrich_dynamic_context(base: str, message: str) -> str:
    """Append live-state blocks to ``base`` (legacy single-string return).

    Kept for compatibility with ``context_assembler.get_system_prompt``
    and any caller that imports it directly. New code should use
    :func:`run_enrichments` via the assembler.

    The voice-gate drift nudge was removed from this function in Phase 2:
    it is a response-time concern, called by ``routes.completions`` after
    the LLM reply. Keeping it here would couple the request-time read
    path to a response-time helper.
    """
    dynamic_context = base
    blocks, _warnings = await run_enrichments(_ENRICHMENTS, message)
    for block in blocks:
        # Preserve the original join style: weather joined with a single
        # newline, the rest with a blank line.
        join = "\n" if block.startswith("[weather]") or _looks_like_weather_block(block) else "\n\n"
        dynamic_context = _append(dynamic_context, block, join=join)
    return dynamic_context


def _looks_like_weather_block(block: str) -> bool:
    """Best-effort detector: weather enrichments start with city/temp phrasing.

    Used to preserve the legacy newline-join for the weather block. This is
    the only divergence in join style in the legacy function; the assembler
    joins uniformly with ``\\n\\n``.
    """
    lowered = block.lower()
    return "regina" in lowered or "°" in block or lowered.startswith("weather")


# Sync helpers for brief synthesis (same sources as async enrichment blocks)


# Explicit markers surfaced in the brief when a source fails, instead of a
# silent empty section that hides the outage from the user.
_WEATHER_UNAVAILABLE = "⚠ Weather unavailable"
_TODOS_UNAVAILABLE = "⚠ Todos unavailable"
_CALENDAR_UNAVAILABLE = "⚠ Calendar unavailable"


def weather_text_sync() -> str:
    try:
        from gateway.weather import get_weather_text

        return get_weather_text() or ""
    except Exception as exc:
        logger.warning("weather enrichment failed: %s", exc)
        return _WEATHER_UNAVAILABLE


def todos_text_sync() -> str:
    try:
        from gateway.todo_store import get_todos_text

        return get_todos_text() or ""
    except Exception as exc:
        logger.warning("todos enrichment failed: %s", exc)
        return _TODOS_UNAVAILABLE


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
    except Exception as exc:
        logger.warning("calendar enrichment failed: %s", exc)
        return _CALENDAR_UNAVAILABLE
