"""Insights endpoint for Kitty UI — surfaced from dream/consolidation."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["insights"])

# In-memory insights (would come from dream/consolidation in production)
_insights: list[dict] = []


@router.get("/insights")
async def get_insights(limit: int = 10):
    """Get recent insights."""
    # Try to get insights from dream module if available
    try:
        from gateway.dream import get_recent_insights
        insights = get_recent_insights(limit=limit)
        return {"insights": insights}
    except (ImportError, AttributeError):
        # Fallback to in-memory
        return {"insights": _insights[:limit]}


@router.get("/dream/insights")
async def get_dream_insights(limit: int = 10):
    """Alias for /insights for backward compatibility."""
    return await get_insights(limit=limit)


@router.post("/insight/{insight_id}/dismiss")
async def dismiss_insight(insight_id: str):
    """Dismiss an insight."""
    global _insights
    _insights = [i for i in _insights if i.get("id") != insight_id]
    return {"dismissed": insight_id}


@router.post("/dream/trigger")
async def trigger_dream():
    """Trigger a dream/consolidation cycle."""
    try:
        from gateway.dream import trigger_consolidation
        await trigger_consolidation()
        return {"status": "consolidation triggered"}
    except (ImportError, AttributeError):
        # Simulate for now
        _insights.append({
            "id": f"insight_{len(_insights) + 1}",
            "text": "Consolidation cycle complete",
            "timestamp": __import__("time").time(),
        })
        return {"status": "simulated"}


@router.get("/dream/status")
async def dream_status():
    """Get dream/consolidation status."""
    return {
        "status": "idle",
        "last_run": None,
        "next_run": None,
        "insights_count": len(_insights),
    }
