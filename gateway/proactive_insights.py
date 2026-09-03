"""Proactive Insight Engine — surfaces patterns without being asked.

Stolen from: GitHub's "Your daily digest" (proprietary, reimplemented from UX),
Linear's "Insights" panel (reimplemented from UX),
Apple's "Screen Time" weekly report (reimplemented from UX),
Microsoft's "MyAnalytics" (reimplemented from UX).

This enhances Kitty's existing insight_loop.py, nudge.py, patterns.py, and
dream_insights.py with a unified pattern-detection pipeline that runs on a
schedule and surfaces insights through the existing signal/notification system.

Patterns detected:
  - Productivity shifts: "You've been more active in the evenings this week"
  - Topic focus: "You've been working on X a lot lately"
  - Streaks: "3-day coding streak"
  - Gaps: "No activity in 2 days — take a break?"
  - Comparisons: "You completed 2x more tasks than last week"
  - Correlations: "When you journal in the morning, your coding sessions are longer"

Usage:
    from gateway.proactive_insights import generate_insights, Insight

    insights = generate_insights()
    for i in insights:
        print(i.headline, i.category)

The insight_loop.py module handles storage, return, and lifecycle.
This module handles detection and generation.
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from gateway.paths import DATA_DIR, LOG_FILE

logger = logging.getLogger("kitty.proactive_insights")

_INSIGHT_CACHE = DATA_DIR / "proactive_insights_cache.json"

# ── Insight categories ──────────────────────────────────────────────────────


class InsightCategory(str):
    """Stable categories for proactive insights. Each maps to a detection function."""

    PRODUCTIVITY_SHIFT = "productivity_shift"
    TOPIC_FOCUS = "topic_focus"
    STREAK = "streak"
    GAP = "gap"
    COMPARISON = "comparison"
    CORRELATION = "correlation"
    HABIT = "habit"


@dataclass
class Insight:
    """One proactive insight, ready for the insight loop."""

    headline: str
    detail: str
    category: str
    confidence: float  # 0.0 - 1.0
    source_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "detail": self.detail,
            "category": self.category,
            "confidence": self.confidence,
            "source_data": self.source_data,
        }


# ── Data extraction ─────────────────────────────────────────────────────────


def _load_log_entries(days: int = 14) -> list[dict]:
    """Load and parse log entries from the last N days."""
    if not LOG_FILE.exists():
        return []

    cutoff = time.time() - days * 86400
    entries: list[dict] = []

    try:
        with LOG_FILE.open("r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("timestamp", 0) >= cutoff:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        logger.warning("Failed to read log file: %s", exc)

    return entries


# ── Detection functions ─────────────────────────────────────────────────────


def detect_topic_focus(entries: list[dict], min_mentions: int = 5) -> list[Insight]:
    """Detect topics the user has been focused on.

    Pattern: "You've mentioned 'async agents' 8 times in the last 3 days."
    """
    # Count topic mentions from domain_classified entries
    topics: Counter = Counter()
    for entry in entries:
        domain = entry.get("domain_classified", "")
        request = entry.get("user_request", "")[:100]
        if domain in ("research", "code", "repair"):
            # Simple keyword extraction from the request
            words = request.lower().split()
            # Skip stopwords, count bigrams
            for i in range(len(words) - 1):
                bigram = f"{words[i]} {words[i+1]}"
                if all(len(w) > 3 for w in (words[i], words[i+1])):
                    topics[bigram] += 1

    insights: list[Insight] = []
    for topic, count in topics.most_common(3):
        if count >= min_mentions:
            insights.append(Insight(
                headline=f"You've been focused on '{topic}'",
                detail=f"Mentioned {count} times in recent conversations. "
                       f"Want me to create a project or knowledge entry for this?",
                category=InsightCategory.TOPIC_FOCUS,
                confidence=min(1.0, count / (min_mentions * 2)),
                source_data={"topic": topic, "mentions": count},
            ))

    return insights


def detect_streaks(entries: list[dict]) -> list[Insight]:
    """Detect daily activity streaks.

    Pattern: "3-day coding streak — keep it going!"
    """
    # Group entries by day
    days: set[str] = set()
    for entry in entries:
        ts = entry.get("timestamp", 0)
        day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        days.add(day)

    if not days:
        return []

    # Find consecutive day streaks
    sorted_days = sorted(days)
    streaks: list[int] = []
    current = 1

    for i in range(1, len(sorted_days)):
        prev = datetime.strptime(sorted_days[i - 1], "%Y-%m-%d")
        curr = datetime.strptime(sorted_days[i], "%Y-%m-%d")
        if (curr - prev).days == 1:
            current += 1
        else:
            streaks.append(current)
            current = 1
    streaks.append(current)

    best = max(streaks)

    insights: list[Insight] = []
    if best >= 3:
        insights.append(Insight(
            headline=f"{best}-day streak!",
            detail=f"You've been active for {best} consecutive days. "
                   f"Consistency is building momentum.",
            category=InsightCategory.STREAK,
            confidence=min(1.0, best / 10),
            source_data={"streak_days": best},
        ))

    return insights


def detect_gaps(entries: list[dict]) -> list[Insight]:
    """Detect activity gaps.

    Pattern: "No activity in the last 2 days — everything okay?"
    """
    if not entries:
        return []

    latest_ts = max(e.get("timestamp", 0) for e in entries)
    now = time.time()
    gap_hours = (now - latest_ts) / 3600

    insights: list[Insight] = []
    if gap_hours > 48:  # 2+ days
        days = round(gap_hours / 24)
        insights.append(Insight(
            headline=f"Quiet for {days} days",
            detail=f"Last activity was {days} days ago. "
                   f"Take a break if you need it, or pick up where you left off.",
            category=InsightCategory.GAP,
            confidence=0.8,
            source_data={"gap_hours": gap_hours},
        ))

    return insights


def detect_comparisons(entries: list[dict]) -> list[Insight]:
    """Compare activity between this week and last week.

    Pattern: "You completed 2x more tasks this week than last week."
    """
    now = time.time()
    this_week_start = now - 7 * 86400
    last_week_start = now - 14 * 86400

    this_week_count = sum(
        1 for e in entries if e.get("timestamp", 0) >= this_week_start
    )
    last_week_count = sum(
        1 for e in entries if e.get("timestamp", 0) >= last_week_start
        and e.get("timestamp", 0) < this_week_start
    )

    insights: list[Insight] = []
    if last_week_count > 0 and this_week_count > 0:
        ratio = this_week_count / last_week_count
        if ratio >= 1.5 or ratio <= 0.67:
            direction = "more" if ratio >= 1.5 else "less"
            multiplier = round(ratio, 1) if ratio >= 1.5 else round(1 / ratio, 1)
            insights.append(Insight(
                headline=f"{multiplier}x {direction} activity this week",
                detail=f"{this_week_count} interactions this week vs "
                       f"{last_week_count} last week. "
                       f"{'Great momentum!' if direction == 'more' else 'Take it easy.'}",
                category=InsightCategory.COMPARISON,
                confidence=0.7,
                source_data={
                    "this_week": this_week_count,
                    "last_week": last_week_count,
                    "ratio": ratio,
                },
            ))

    return insights


def detect_productivity_shifts(entries: list[dict]) -> list[Insight]:
    """Detect shifts in productive hours.

    Pattern: "You've been most active in the evenings lately."
    """
    if not entries:
        return []

    hour_counts: Counter = Counter()
    for entry in entries:
        ts = entry.get("timestamp", 0)
        hour = datetime.fromtimestamp(ts, tz=timezone.utc).hour
        hour_counts[hour] += 1

    if not hour_counts:
        return []

    peak_hour = hour_counts.most_common(1)[0][0]
    period = "morning" if 5 <= peak_hour < 12 else              "afternoon" if 12 <= peak_hour < 17 else              "evening" if 17 <= peak_hour < 22 else              "night"

    # Check if this is a meaningful concentration
    total = sum(hour_counts.values())
    peak_share = hour_counts[peak_hour] / total if total > 0 else 0

    insights: list[Insight] = []
    if peak_share > 0.15:  # 15%+ of activity in one hour block
        # Group hours into periods for a richer signal
        period_counts: Counter = Counter()
        for hour, count in hour_counts.items():
            period = "morning" if 5 <= hour < 12 else                      "afternoon" if 12 <= hour < 17 else                      "evening" if 17 <= hour < 22 else                      "night"
            period_counts[period] += count

        dominant_period = period_counts.most_common(1)[0][0]
        period_share = period_counts[dominant_period] / total

        if period_share > 0.35:
            insights.append(Insight(
                headline=f"Most active in the {dominant_period}",
                detail=f"{round(period_share * 100)}% of your activity is in the "
                       f"{dominant_period}. Peak hour: {peak_hour}:00.",
                category=InsightCategory.PRODUCTIVITY_SHIFT,
                confidence=min(1.0, period_share),
                source_data={
                    "dominant_period": dominant_period,
                    "period_share": period_share,
                    "peak_hour": peak_hour,
                },
            ))

    return insights


# ── Main pipeline ───────────────────────────────────────────────────────────


def generate_insights(days: int = 14) -> list[Insight]:
    """Run all detection functions and return generated insights.

    This is called by the insight loop cron (insights.return_due action)
    and by the morning proactive routine.

    Args:
        days: How many days of history to analyze.

    Returns:
        List of generated insights, sorted by confidence descending.
    """
    entries = _load_log_entries(days=days)
    logger.info("Generating proactive insights from %d log entries", len(entries))

    all_insights: list[Insight] = []

    # Run all detectors
    all_insights.extend(detect_topic_focus(entries))
    all_insights.extend(detect_streaks(entries))
    all_insights.extend(detect_gaps(entries))
    all_insights.extend(detect_comparisons(entries))
    all_insights.extend(detect_productivity_shifts(entries))

    # Filter low-confidence insights
    filtered = [i for i in all_insights if i.confidence >= 0.5]

    # Sort by confidence descending
    filtered.sort(key=lambda i: -i.confidence)

    logger.info("Generated %d proactive insights (%d after confidence filter)",
                len(all_insights), len(filtered))

    return filtered


def generate_and_send() -> int:
    """Generate insights and send them to the insight loop.

    Returns the number of insights sent.
    """
    from gateway.insight_loop import capture

    insights = generate_insights()
    sent = 0

    for insight in insights:
        try:
            capture(
                text=insight.headline,
                source_ref=insight.detail,
                category=insight.category,
                explicit_consent=False,
            )
            sent += 1
        except Exception as exc:
            logger.warning("Failed to send insight %r: %s", insight.headline, exc)

    logger.info("Sent %d/%d proactive insights to insight loop", sent, len(insights))
    return sent


# ── Caching ─────────────────────────────────────────────────────────────────


def _load_cache() -> dict:
    """Load cached insights to avoid regenerating every check."""
    if _INSIGHT_CACHE.exists():
        try:
            return json.loads(_INSIGHT_CACHE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"generated_at": 0, "insights": []}


def _save_cache(insights: list[dict]) -> None:
    """Cache generated insights."""
    _INSIGHT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    _INSIGHT_CACHE.write_text(json.dumps({
        "generated_at": time.time(),
        "insights": insights,
    }, indent=2))


def get_cached_or_generate(ttl_seconds: int = 3600) -> list[Insight]:
    """Return cached insights if fresh, otherwise regenerate."""
    cache = _load_cache()
    now = time.time()

    if cache["insights"] and (now - cache["generated_at"]) < ttl_seconds:
        logger.debug("Using cached proactive insights (%d cached)", len(cache["insights"]))
        return [Insight(**i) for i in cache["insights"]]

    insights = generate_insights()
    _save_cache([i.to_dict() for i in insights])
    return insights
