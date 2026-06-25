"""Weekly pattern mirror — surfaces behavioral themes from recent gateway traces."""
from __future__ import annotations

import json
import logging
import time
from collections import Counter

from gateway.paths import DATA_DIR, LOG_FILE

logger = logging.getLogger("kitty.honcho")

SIGNAL_CACHE = DATA_DIR / "honcho_weekly.json"

_FALLBACK_EMPTY = (
    "Not enough data yet — keep chatting with Kitty and check back next week."
)
_FALLBACK_ERROR = "Kitty couldn't quite find the words this week — but she's watching."


def get_recent_traces(days: int = 7) -> list[dict]:
    """Read gateway_trace.jsonl line-by-line and return entries from the last N days."""
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


def summarize_patterns(traces: list[dict]) -> str:
    """Call DeepSeek Flash to synthesize behavioral patterns from trace data."""
    if not traces:
        return _FALLBACK_EMPTY
    from gateway.llm_client import call_llm

    domain_counts = Counter(t.get("domain_classified", "unknown") for t in traces)
    domain_summary = "\n".join(
        f"- {d}: {c} conversations" for d, c in domain_counts.most_common()
    )
    recent_requests = "\n".join(
        f"- {t.get('user_request', '')[:80]}" for t in traces[-10:]
    )

    prompt = f"""You are Kitty, a warm personal AI. You're writing Jacob's weekly pattern mirror.

Based on his last {len(traces)} conversations this week:

Domain distribution:
{domain_summary}

Recent requests (sample):
{recent_requests}

Write a 3-sentence weekly observation in Kitty's warm, tabby-cat voice.
- Sentence 1: Name the dominant pattern or theme you notice.
- Sentence 2: Offer one gentle, specific insight (a loop, a win, or a shift).
- Sentence 3: One grounding nudge — short, kind, not advice-y.

Write only the 3 sentences. No preamble, no labels."""

    try:
        return call_llm(
            model="kitty-default",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.7,
            timeout=30,
            operation="honcho.weekly_mirror",
        )
    except Exception as e:
        logger.warning("Pattern synthesis failed: %s", e)
        return _FALLBACK_ERROR


def get_weekly_mirror(days: int = 7, use_cache: bool = True) -> dict:
    """Generate weekly pattern mirror. Returns HonchoSignal-compatible dict."""
    from contracts.honcho_signal import HonchoSignal

    if use_cache and SIGNAL_CACHE.exists():
        try:
            cached = json.loads(SIGNAL_CACHE.read_text())
            if time.time() - cached.get("_cached_at", 0) < 23 * 3600:
                return {k: v for k, v in cached.items() if not k.startswith("_")}
        except Exception:
            pass

    traces = get_recent_traces(days=days)
    observation = summarize_patterns(traces)

    signal = HonchoSignal(
        source_session_id="weekly_mirror",
        signal_type="weekly_observation",
        intensity=0.7,
        observation=observation,
        metadata={"trace_count": len(traces), "days": days},
    )
    result = signal.model_dump(mode="json")

    try:
        SIGNAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
        SIGNAL_CACHE.write_text(json.dumps({**result, "_cached_at": time.time()}, default=str))
    except Exception as e:
        logger.warning("Cache write failed: %s", e)

    return result
