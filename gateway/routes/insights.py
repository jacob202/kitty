"""Insights endpoint for Kitty UI — surfaced from dream/consolidation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gateway.memory_consolidation import get_last_run_info
from gateway.routes.dream import dismiss_dream_insight, load_dream_insights

router = APIRouter(tags=["insights"])


@router.get("/insights")
async def get_insights(limit: int = 10):
    """Get recent insights from the real dream insight store."""
    return {"insights": load_dream_insights(limit=limit)}


@router.get("/dream/insights")
async def get_dream_insights(limit: int = 10):
    """Alias for /insights for backward compatibility."""
    return await get_insights(limit=limit)


@router.post("/insight/{insight_id}/dismiss")
async def dismiss_insight(insight_id: str):
    """Dismiss an insight."""
    if not dismiss_dream_insight(insight_id):
        raise HTTPException(status_code=404, detail="Insight not found")
    return {"dismissed": insight_id}


@router.post("/dream/trigger")
async def trigger_dream():
    """Trigger a dream/consolidation cycle.

    TODO(jacob): wire to the real nightly_dream background task once the
    /dream/trigger route in gateway.routes.dream is the canonical entry point.
    """
    return {"status": "not_implemented", "message": "Dream trigger not wired yet"}


@router.get("/dream/status")
async def dream_status():
    """Get dream/consolidation status."""
    status = get_last_run_info()
    status["insights_count"] = len(load_dream_insights(limit=0))
    return status
