"""Performance stats and metrics — owned substrate for the perf endpoint.

Why this module exists (Phase 3 of the gateway deepening program):
the route used to swallow every I/O error with a bare
``except Exception: pass``, hiding real disk-write failures. The new
module validates inputs, writes through ``paths.py``, and raises on
failure so the route layer cannot mask a broken log.

The wire shape of every endpoint that used to live in
``routes/perf.py`` is unchanged. The route is now a thin
request-parsing / response-shaping wrapper around these functions.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

from gateway.cron import list_schedules
from gateway.paths import DATA_DIR, KITTY_TOKEN_LOG_FILE

logger = logging.getLogger("kitty.perf")

PERF_LOG = DATA_DIR / "perf_stats.jsonl"


def _validate_stat(stat: Any) -> dict:
    if not isinstance(stat, dict):
        raise TypeError(f"perf stat must be a dict, got {type(stat).__name__}")
    return stat


def log_perf_stat(stat: dict) -> None:
    """Append one performance stat to ``PERF_LOG``.

    Raises on any I/O failure.
    """
    record = _validate_stat(stat)
    PERF_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record["timestamp"] = time.time()
    with PERF_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_window(window_hours: int) -> list[dict]:
    """Return perf stats from the last ``window_hours`` hours."""
    if not PERF_LOG.exists():
        return []
    cutoff = time.time() - (window_hours * 3600)
    rows: list[dict] = []
    with PERF_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            if entry.get("timestamp", 0) > cutoff:
                rows.append(entry)
    return rows


def get_perf_stats(window_hours: int = 24) -> dict:
    """Aggregate counts, latency, and token usage for the last N hours.

    Empty when no data has been written. Never returns mock data.
    """
    if not isinstance(window_hours, int) or window_hours <= 0:
        raise ValueError(f"window_hours must be a positive int, got {window_hours!r}")

    schedules = list_schedules()
    stats = _read_window(window_hours)

    latencies = [s.get("latency_ms", 0) for s in stats if "latency_ms" in s]
    token_usages = [s.get("tokens", 0) for s in stats if "tokens" in s]

    return {
        "window_hours": window_hours,
        "total_requests": len(stats),
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
        "max_latency_ms": max(latencies) if latencies else 0,
        "min_latency_ms": min(latencies) if latencies else 0,
        "total_tokens": sum(token_usages),
        "avg_tokens": sum(token_usages) / len(token_usages) if token_usages else 0,
        "active_schedules": len([s for s in schedules if s.get("enabled")]),
        "schedules": schedules,
    }


def get_recent_stats(limit: int = 50) -> dict:
    """Return the most recent ``limit`` perf stats (newest first).

    Empty when no data has been written. Never returns mock data.
    """
    if not isinstance(limit, int) or limit <= 0:
        raise ValueError(f"limit must be a positive int, got {limit!r}")
    if not PERF_LOG.exists():
        return {"stats": [], "count": 0}

    stats: list[dict] = []
    with PERF_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict):
                stats.append(entry)

    recent = list(reversed(stats[-limit:]))
    return {"stats": recent, "count": len(recent)}


def _parse_ts(raw: object) -> float:
    """Coerce a JSON token-log ``ts`` field to seconds since epoch."""
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw).timestamp()
        except (ValueError, TypeError):
            return 0.0
    return 0.0


def get_per_tier_stats(window_hours: int = 24) -> dict[str, dict[str, int]]:
    """Aggregate token-usage rows by tier from the JSONL token log.

    Returns a dict keyed by tier name with count, prompt tokens, and
    completion tokens. Empty dict when no tier-tagged data exists.
    """
    if not KITTY_TOKEN_LOG_FILE.exists():
        return {}

    cutoff = time.time() - (window_hours * 3600)
    per_tier: dict[str, dict[str, int]] = {}

    with KITTY_TOKEN_LOG_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if _parse_ts(row.get("ts")) < cutoff:
                continue

            metadata = row.get("metadata")
            if not isinstance(metadata, dict):
                continue
            tier = metadata.get("tier")
            if not isinstance(tier, str) or not tier:
                continue

            usage = row.get("usage")
            if not isinstance(usage, dict):
                continue
            prompt = usage.get("prompt_tokens", 0)
            completion = usage.get("completion_tokens", 0)

            if tier not in per_tier:
                per_tier[tier] = {"count": 0, "prompt_tokens": 0, "completion_tokens": 0}
            per_tier[tier]["count"] += 1
            per_tier[tier]["prompt_tokens"] += prompt
            per_tier[tier]["completion_tokens"] += completion

    return per_tier
