"""Insights endpoint for Kitty UI — surfaced from dream/consolidation."""

from __future__ import annotations

import time
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["insights"])

# In-memory insights (would come from dream/consolidation in production)
_insights: list[dict] = [
    {
        "insight_id": "pattern-morning-weather",
        "kind": "pattern",
        "title": "You often ask about weather in the morning",
        "detail": "Detected 5 morning weather queries this week",
        "source": "pattern detection",
        "confidence": 0.92,
        "created_at": int(time.time()) - 3600,
    },
    {
        "insight_id": "suggestion-daily-loop",
        "kind": "suggestion",
        "title": "Set up a daily weather loop",
        "detail": "Automate your morning weather check",
        "source": "recommendation engine",
        "confidence": 0.85,
        "created_at": int(time.time()) - 7200,
        "actions": [
            {"label": "Create Loop", "action_id": "create-loop-weather"},
            {"label": "Dismiss", "action_id": "dismiss"},
        ],
    },
    {
        "insight_id": "milestone-100-chats",
        "kind": "milestone",
        "title": "100 chats reached!",
        "detail": "You've had 100 conversations with Kitty",
        "source": "usage tracker",
        "confidence": 1.0,
        "created_at": int(time.time()) - 86400,
    },
]


@router.get("/insights")
async def get_insights(limit: int = 10):
    """Get recent insights."""
    # Try to get insights from dream module if available
    try:
        from gateway.dream import get_recent_insights
        insights = get_recent_insights(limit=limit)
        return {"insights": insights}
    except (ImportError, AttributeError):
        # Fallback to in-memory mock data
        sorted_insights = sorted(_insights, key=lambda x: x["created_at"], reverse=True)
        return {"insights": sorted_insights[:limit]}


@router.get("/dream/insights")
async def get_dream_insights(limit: int = 10):
    """Alias for /insights for backward compatibility."""
    return await get_insights(limit=limit)


@router.post("/insight/{insight_id}/dismiss")
async def dismiss_insight(insight_id: str):
    """Dismiss an insight."""
    global _insights
    initial_len = len(_insights)
    _insights = [i for i in _insights if i.get("insight_id") != insight_id]
    if len(_insights) == initial_len:
        raise HTTPException(status_code=404, detail="Insight not found")
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
            "insight_id": f"insight_{int(time.time())}",
            "kind": "suggestion",
            "title": "Consolidation cycle complete",
            "detail": "New insights have been generated from your recent activity",
            "source": "system",
            "confidence": 1.0,
            "created_at": int(time.time()),
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
