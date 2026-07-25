"""Life Awareness — calendar-aware, do-not-disturb, proactive life-first companion.

Public API:
  today_summary() -> dict              Today's events + life steps + free blocks
  yesterday_recap() -> dict            What happened yesterday (journal + signals + tasks)
  evening_reflection() -> dict         Day-in-review with tomorrow's nudge
  morning_proactive() -> dict          Today's proactive suggestions (life steps first)
  do_not_disturb_status() -> dict      In-meeting check with next-free info
  current_meeting() -> dict | None     The calendar event happening now, if any
  emit_life_signal(kind, payload)      Emit a life-awareness signal
  am_in_a_meeting() -> bool            Simple boolean check
  meeting_block_text() -> str | None   Context enrichment text for DND
  generate_evening_reflection_text() -> str  LLM-generated reflection
  generate_proactive_text() -> str     LLM-generated proactive text
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("kitty.life_awareness")

LIFE_SIGNAL_SOURCE = "life_awareness"
MORNING_BRIEF_EMITTED = "morning_brief_emitted"
EVENING_REFLECTION_EMITTED = "evening_reflection_emitted"
MEETING_DETECTED = "meeting_detected"
MEETING_ENDED = "meeting_ended"
PROACTIVE_SUGGESTION = "proactive_suggestion"
PROACTIVE_DISMISSED = "proactive_dismissed"

_YESTERDAY_CACHE: dict[str, Any] | None = None
_PROACTIVE_CACHE: dict[str, Any] | None = None
_REFLECTION_CACHE: dict[str, Any] | None = None
_DND_CACHE: dict[str, Any] | None = None


def _today_start_end() -> tuple[float, float]:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp()
    end = start + 86400
    return start, end


def _yesterday_start_end() -> tuple[float, float]:
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    start = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc).timestamp()
    end = start + 86400
    return start, end


def _parse_event_time(ts_str: str, _date_ref: str | None = None) -> float:
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.timestamp()
    except (ValueError, TypeError):
        pass
    try:
        from dateutil import parser as dateparser
        return dateparser.parse(ts_str).timestamp()
    except Exception:
        return time.time()


def today_events() -> list[dict]:
    from gateway.calendar_integration import get_today, is_available
    if not is_available():
        return []
    raw = get_today()
    events: list[dict] = []
    for ev in raw:
        events.append({
            "title": ev.get("title", ""),
            "start": ev.get("start", ""),
            "end": ev.get("end", ""),
        })
    return events


def _is_in_meeting(events: list[dict]) -> bool:
    now = time.time()
    for ev in events:
        start_ts = _parse_event_time(ev.get("start", ""))
        end_ts = _parse_event_time(ev.get("end", ""))
        if start_ts <= now <= end_ts:
            return True
    return False


def am_in_a_meeting() -> bool:
    return _is_in_meeting(today_events())


def current_meeting() -> dict | None:
    events = today_events()
    now = time.time()
    for ev in events:
        start_ts = _parse_event_time(ev.get("start", ""))
        end_ts = _parse_event_time(ev.get("end", ""))
        if start_ts <= now <= end_ts:
            return ev
    return None


def next_free_block(events: list[dict] | None = None) -> dict | None:
    evts = events if events is not None else today_events()
    now = time.time()
    for ev in evts:
        end_ts = _parse_event_time(ev.get("end", ""))
        if end_ts > now:
            return {"after": ev.get("title", ""), "free_at": ev.get("end", "")}
    return None


def do_not_disturb_status() -> dict:
    global _DND_CACHE
    if _DND_CACHE is not None:
        return _DND_CACHE
    events = today_events()
    in_meeting = _is_in_meeting(events)
    current = None
    next_free = None
    if in_meeting:
        current = current_meeting()
        next_free = next_free_block(events)
    status = {
        "do_not_disturb": in_meeting,
        "in_meeting": in_meeting,
        "current_meeting": current,
        "next_free": next_free,
        "event_count": len(events),
        "checked_at": time.time(),
    }
    _DND_CACHE = status
    return status


def invalidate_dnd_cache() -> None:
    global _DND_CACHE
    _DND_CACHE = None


def meeting_block_text() -> str | None:
    status = do_not_disturb_status()
    if not status["in_meeting"]:
        return None
    meeting = status.get("current_meeting") or {}
    title = meeting.get("title", "a meeting")
    nf = status.get("next_free")
    free_at = nf.get("free_at", "later") if nf else "later"
    return (
        f"[DO NOT DISTURB — Jacob is in: {title}]\n"
        f"Respond concisely. Do not suggest actions, do not offer follow-ups, "
        f"do not ask questions. Answer the question directly and stop. "
        f"Next free: {free_at}"
    )


def yesterday_recap() -> dict:
    global _YESTERDAY_CACHE
    if _YESTERDAY_CACHE is not None:
        return _YESTERDAY_CACHE
    y_start, y_end = _yesterday_start_end()
    signals = _yesterday_signals(y_start, y_end)
    journal_entries = _yesterday_journal(y_start, y_end)
    recap = {
        "date": datetime.fromtimestamp(y_start, tz=timezone.utc).strftime("%Y-%m-%d"),
        "signal_count": len(signals),
        "journal_count": len(journal_entries),
        "signals": signals[:10],
        "journal_entries": journal_entries[:5],
        "has_data": bool(signals or journal_entries),
    }
    _YESTERDAY_CACHE = recap
    return recap


def _yesterday_signals(y_start: float, y_end: float) -> list[dict]:
    try:
        from gateway.stores.signal import list_recent
        recent = list_recent(limit=100)
        return [s for s in recent if y_start <= s.get("ts", 0) <= y_end]
    except Exception as exc:
        logger.warning("yesterday_signals failed: %s", exc)
        return []


def _yesterday_journal(y_start: float, y_end: float) -> list[dict]:
    try:
        from gateway.journal import recent_entries
        entries = recent_entries(days=2, limit=50)
        return [e for e in entries if y_start <= e.get("ts", 0) <= y_end]
    except Exception as exc:
        logger.warning("yesterday_journal failed: %s", exc)
        return []


def _yesterday_completed_tasks(y_start: float, y_end: float) -> list[dict]:
    try:
        from gateway.stores.signal import list_recent
        recent = list_recent(limit=200)
        task_signals = [
            s for s in recent
            if s.get("kind") in ("task_completed", "action_completed", "todo_done")
            and y_start <= s.get("ts", 0) <= y_end
        ]
        return task_signals[:10]
    except Exception:
        return []


def _life_project_steps_today() -> list[dict]:
    try:
        from gateway import next_step
        steps = next_step.select_steps(limit=5)
        return [s for s in steps]
    except Exception as exc:
        logger.warning("life_project_steps_today failed: %s", exc)
        return []


def morning_proactive() -> dict:
    global _PROACTIVE_CACHE
    if _PROACTIVE_CACHE is not None:
        return _PROACTIVE_CACHE
    events = today_events()
    steps = _life_project_steps_today()
    recap = yesterday_recap()
    now = datetime.now(timezone.utc).isoformat()
    result = {
        "now": now,
        "event_count": len(events),
        "events": events[:10],
        "life_steps": steps,
        "yesterday": {
            "signal_count": recap.get("signal_count", 0),
            "journal_count": recap.get("journal_count", 0),
            "has_data": recap.get("has_data", False),
        },
        "proactive_suggestions": _build_proactive_suggestions(events, steps, recap),
    }
    _PROACTIVE_CACHE = result
    return result


def _build_proactive_suggestions(events: list[dict], steps: list[dict], recap: dict) -> list[dict]:
    suggestions: list[dict] = []
    if steps:
        for s in steps[:2]:
            suggestions.append({
                "kind": "life_step",
                "priority": "high",
                "text": f"{s.get('project_name', '')}: {s.get('step', '')}",
                "why": s.get("why", ""),
                "project_id": s.get("project_id"),
            })
    in_meeting = _is_in_meeting(events)
    if in_meeting:
        suggestions.append({
            "kind": "focus_block",
            "priority": "medium",
            "text": "You're in a meeting until the next free block",
        })
    if events and not in_meeting:
        next_event = min(events, key=lambda e: _parse_event_time(e.get("start", "")))
        suggestions.append({
            "kind": "upcoming_event",
            "priority": "medium",
            "text": f"Next: {next_event.get('title', '')} at {next_event.get('start', '')}",
        })
    if recap.get("journal_count", 0) > 0:
        suggestions.append({
            "kind": "journal_reflection",
            "priority": "low",
            "text": f"You wrote {recap['journal_count']} journal entries yesterday",
        })
    return suggestions


def generate_evening_reflection_text() -> str:
    events = today_events()
    yesterday_recap()
    steps = _life_project_steps_today()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    data_parts: list[str] = [f"Date: {now}"]
    if events:
        event_lines = "\n".join(f"- {e.get('start', '')}: {e.get('title', '')}" for e in events[:8])
        data_parts.append(f"Today's events:\n{event_lines}")
    else:
        data_parts.append("No calendar events today")
    if steps:
        step_lines = "\n".join(f"- {s.get('project_name', '')}: {s.get('step', '')}" for s in steps[:3])
        data_parts.append(f"Active steps:\n{step_lines}")
    data_block = "\n\n".join(data_parts)
    prompt = (
        f"Write a short evening reflection for Jacob. Here is today's data:\n\n"
        f"{data_block}\n\n"
        f"Write 2-3 sentences that feel like a calm, honest companion winding down the day. "
        f"Mention what happened today on the calendar, note one thing from his active steps, "
        f"and suggest one thing to think about for tomorrow. "
        f"No bullet points. No headers. No 'Great question!'. Contractions. Speak Canadian."
    )
    try:
        from gateway.llm_client import call_llm
        return call_llm(
            [{"role": "user", "content": prompt}],
            model="kitty-default",
            max_tokens=300,
            temperature=0.5,
            operation="life.evening_reflection",
        )
    except Exception as exc:
        logger.warning("evening reflection LLM failed: %s", exc)
        return _fallback_reflection(events, steps)


def _fallback_reflection(events: list[dict], steps: list[dict]) -> str:
    parts: list[str] = ["Evening check-in."]
    if events:
        titles = [e.get("title", "") for e in events[:3]]
        parts.append(f"Today had {len(events)} events: {' | '.join(titles)}.")
    if steps:
        names = [s.get("project_name", "") for s in steps[:2]]
        parts.append(f"Active on: {', '.join(names)}.")
    parts.append("Rest well.")
    return " ".join(parts)


def generate_proactive_text() -> str:
    events = today_events()
    steps = _life_project_steps_today()
    recap = yesterday_recap()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    data_parts: list[str] = [f"Date: {now}"]
    if events:
        event_lines = "\n".join(f"- {e.get('start', '')}: {e.get('title', '')}" for e in events[:8])
        data_parts.append(f"Today's events:\n{event_lines}")
    if steps:
        step_lines = "\n".join(f"- {s.get('project_name', '')}: {s.get('step', '')}" for s in steps[:3])
        data_parts.append(f"Life steps:\n{step_lines}")
    if recap.get("has_data"):
        data_parts.append(f"Yesterday: {recap['signal_count']} events, {recap['journal_count']} journal entries")
    data_block = "\n\n".join(data_parts)
    prompt = (
        f"Write a short proactive morning note for Jacob. Here is today's data:\n\n"
        f"{data_block}\n\n"
        f"Write 2-3 sentences: lead with the most important life step or calendar event, "
        f"mention what happened yesterday if relevant, and end with a warm one-liner. "
        f"No bullet points. No headers. Contractions. Speak Canadian."
    )
    try:
        from gateway.llm_client import call_llm
        return call_llm(
            [{"role": "user", "content": prompt}],
            model="kitty-default",
            max_tokens=300,
            temperature=0.5,
            operation="life.morning_proactive",
        )
    except Exception as exc:
        logger.warning("proactive text LLM failed: %s", exc)
        return _fallback_proactive(events, steps)


def _fallback_proactive(events: list[dict], steps: list[dict]) -> str:
    parts: list[str] = ["Good morning."]
    if steps:
        s = steps[0]
        parts.append(f"Your first life step: {s.get('project_name', '')} — {s.get('step', '')}.")
    if events:
        parts.append(f"You have {len(events)} calendar events today.")
    parts.append("Let's make it count.")
    return " ".join(parts)


def evening_reflection() -> dict:
    global _REFLECTION_CACHE
    if _REFLECTION_CACHE is not None:
        return _REFLECTION_CACHE
    events = today_events()
    steps = _life_project_steps_today()
    text = generate_evening_reflection_text()
    now = datetime.now(timezone.utc).isoformat()
    result = {
        "now": now,
        "event_count": len(events),
        "events": events[:10],
        "life_steps": steps,
        "reflection": text,
    }
    _REFLECTION_CACHE = result
    return result


def emit_life_signal(kind: str, payload: dict | None = None) -> dict | None:
    try:
        from gateway.stores.signal import emit
        return emit(
            source=LIFE_SIGNAL_SOURCE,
            kind=kind,
            payload=payload or {},
            dedupe_key=f"life_{kind}_{int(time.time() // 60)}",
        )
    except Exception as exc:
        logger.warning("emit_life_signal failed: %s", exc)
        return None


def invalidate_caches() -> None:
    global _YESTERDAY_CACHE, _PROACTIVE_CACHE, _REFLECTION_CACHE, _DND_CACHE
    _YESTERDAY_CACHE = None
    _PROACTIVE_CACHE = None
    _REFLECTION_CACHE = None
    _DND_CACHE = None


def today_summary() -> dict:
    events = today_events()
    in_meeting = _is_in_meeting(events)
    steps = _life_project_steps_today()
    return {
        "now": datetime.now(timezone.utc).isoformat(),
        "event_count": len(events),
        "events": events[:10],
        "in_meeting": in_meeting,
        "current_meeting": current_meeting() if in_meeting else None,
        "life_steps": steps[:3],
    }
