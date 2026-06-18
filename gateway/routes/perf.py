"""Performance stats and metrics endpoint."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import APIRouter

from gateway.paths import DATA_DIR

router = APIRouter(tags=["perf"])

PERF_LOG = DATA_DIR / "perf_stats.jsonl"


def log_perf_stat(stat: Dict[str, Any]) -> None:
    """Log a performance stat to the perf log."""
    try:
        PERF_LOG.parent.mkdir(parents=True, exist_ok=True)
        stat["timestamp"] = time.time()
        with open(PERF_LOG, "a") as f:
            f.write(json.dumps(stat) + "\n")
    except Exception:
        pass


@router.get("/perf/stats")
async def get_perf_stats(window_hours: int = 24) -> Dict[str, Any]:
    """Get performance statistics for the last N hours."""
    from gateway.cron import list_schedules
    
    # Get cron status
    schedules = list_schedules()
    
    # Read recent perf logs
    stats: List[Dict[str, Any]] = []
    if PERF_LOG.exists():
        cutoff = time.time() - (window_hours * 3600)
        try:
            with open(PERF_LOG, "r") as f:
                for line in f:
                    try:
                        stat = json.loads(line.strip())
                        if stat.get("timestamp", 0) > cutoff:
                            stats.append(stat)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception:
            pass
    
    # Calculate aggregates
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


@router.get("/perf/recent")
async def get_recent_stats(limit: int = 50) -> Dict[str, Any]:
    """Get recent performance stats."""
    stats: List[Dict[str, Any]] = []
    if PERF_LOG.exists():
        try:
            with open(PERF_LOG, "r") as f:
                lines = f.readlines()
                for line in reversed(lines[-limit:]):
                    try:
                        stats.append(json.loads(line.strip()))
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception:
            pass
    
    return {"stats": stats[:limit], "count": len(stats)}
