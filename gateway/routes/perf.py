"""Performance stats and metrics endpoint — thin FastAPI wrapper."""

from __future__ import annotations

from fastapi import APIRouter

from gateway import perf

router = APIRouter(tags=["perf"])


@router.get("/perf/stats")
async def get_perf_stats(window_hours: int = 24) -> dict:
    """Get performance statistics for the last N hours, with per-tier aggregates."""
    base = perf.get_perf_stats(window_hours=window_hours)
    base["per_tier"] = perf.get_per_tier_stats(window_hours=window_hours)
    return base


@router.get("/perf/recent")
async def get_recent_stats(limit: int = 50) -> dict:
    """Get recent performance stats."""
    return perf.get_recent_stats(limit=limit)
