"""Longitudinal Pattern Tracking — multi-timeframe behavioral analysis.

Builds on honcho.py for weekly mirrors, extends to monthly/quarterly/annual
perspectives. Detects productivity cycles, mood seasons, recurring frustrations.

Public API:
  analyze(days) -> dict    Analyze patterns over N days
  weekly() -> dict         Weekly pattern summary
  annual_review() -> dict  Year-over-year perspective
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter
from datetime import datetime

from gateway.paths import DATA_DIR, LOG_FILE

logger = logging.getLogger("kitty.patterns")

PATTERN_CACHE = DATA_DIR / "pattern_analysis.json"


def _load_traces(days: int = 90) -> list[dict]:
    """Load gateway traces from the last N days."""
    if not LOG_FILE.exists():
        return []
    cutoff = time.time() - days * 86400
    traces = []
    with LOG_FILE.open("r", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("timestamp", 0) >= cutoff:
                    traces.append(entry)
            except json.JSONDecodeError:
                continue
    return traces


def analyze(days: int = 90) -> dict:
    """Analyze patterns over the specified number of days."""
    traces = _load_traces(days)
    if not traces:
        return {"period_days": days, "total_interactions": 0, "note": "Not enough data yet"}

    domains = Counter(t.get("domain_classified", "soul") for t in traces)
    total = len(traces)
    avg_elapsed = sum(t.get("elapsed_ms", 0) for t in traces) / max(total, 1)

    # Time-of-day distribution
    hours = Counter()
    for t in traces:
        ts = t.get("timestamp", 0)
        if ts:
            hour = datetime.fromtimestamp(ts).hour
            hours[hour] += 1

    peak_hour = hours.most_common(1)[0][0] if hours else 0

    # Day-of-week
    days_of_week = Counter()
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for t in traces:
        ts = t.get("timestamp", 0)
        if ts:
            dow = datetime.fromtimestamp(ts).weekday()
            days_of_week[day_names[dow]] += 1

    # Weekly trend
    weeks: dict[str, int] = {}
    for t in traces:
        ts = t.get("timestamp", 0)
        if ts:
            week_key = datetime.fromtimestamp(ts).strftime("%Y-W%W")
            weeks[week_key] = weeks.get(week_key, 0) + 1

    weekly_trend = sorted(weeks.items())[-12:]  # last 12 weeks
    trend_direction = "stable"
    if len(weekly_trend) >= 4:
        first_half = sum(c for _, c in weekly_trend[:len(weekly_trend)//2])
        second_half = sum(c for _, c in weekly_trend[len(weekly_trend)//2:])
        if second_half > first_half * 1.2:
            trend_direction = "increasing"
        elif second_half < first_half * 0.8:
            trend_direction = "decreasing"

    return {
        "period_days": days,
        "total_interactions": total,
        "avg_response_ms": round(avg_elapsed, 0),
        "top_domains": domains.most_common(5),
        "peak_hour": peak_hour,
        "busiest_day": days_of_week.most_common(1)[0] if days_of_week else ("unknown", 0),
        "weekly_trend": dict(weekly_trend[-8:]),
        "trend_direction": trend_direction,
        "day_distribution": dict(days_of_week),
        "hour_distribution": dict(sorted(hours.items())),
    }


def weekly() -> dict:
    """Get this week's pattern summary."""
    return analyze(days=7)


def annual_review() -> dict:
    """Generate a year-over-year perspective."""
    result = analyze(days=365)

    # Add journal insights if available
    try:
        from gateway.journal import JOURNAL_LOG
        if JOURNAL_LOG.exists():
            entries = []
            cutoff = time.time() - 365 * 86400
            with JOURNAL_LOG.open("r") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get("ts", 0) >= cutoff:
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue
            themes = Counter(e.get("theme") for e in entries if e.get("theme"))
            result["journal_themes"] = themes.most_common(10)
            result["total_journal_entries"] = len(entries)
    except Exception:
        logger.debug("annual_review: journal read failed", exc_info=True)

    # Add memory stats
    try:
        from gateway.memory import list_memories
        memories = list_memories(limit=0)  # get count
        result["total_memories"] = len(memories) if isinstance(memories, list) else 0
    except Exception:
        logger.debug("annual_review: memory read failed", exc_info=True)

    return result


def get_insight_text(days: int = 30) -> str:
    """Return a human-readable insight string for context injection."""
    data = analyze(days)
    if data.get("total_interactions", 0) == 0:
        return ""

    lines = ["## Your Patterns"]
    lines.append(f"Last {days} days: {data['total_interactions']} interactions, avg {data['avg_response_ms']}ms response")

    top = data.get("top_domains", [])
    if top:
        domain_str = ", ".join(f"{d} ({c})" for d, c in top[:3])
        lines.append(f"Top domains: {domain_str}")

    if data.get("trend_direction") != "stable":
        lines.append(f"Trend: {data['trend_direction']}")

    peak = data.get("peak_hour", 0)
    busy = data.get("busiest_day", ("", 0))
    lines.append(f"Peak activity: {peak}:00, busiest on {busy[0]}")

    return "\n".join(lines)
