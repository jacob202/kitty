"""Loops endpoint for Kitty UI — background task loops."""

from __future__ import annotations

import time
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["loops"])

# In-memory loop state (would be persisted in production)
_loops: list[dict] = [
    {
        "loop_id": "daily-brief",
        "name": "Daily Brief",
        "description": "Generates morning brief at 7am",
        "status": "running",
        "interval_minutes": 1440,
        "last_run": int(time.time()) - 3600,
        "last_result": "Brief generated successfully",
        "created_at": int(time.time()) - 86400,
        "updated_at": int(time.time()) - 3600,
    },
    {
        "loop_id": "search-index",
        "name": "Search Index",
        "description": "Updates search index every 15 minutes",
        "status": "running",
        "interval_minutes": 15,
        "last_run": int(time.time()) - 900,
        "created_at": int(time.time()) - 7200,
        "updated_at": int(time.time()) - 900,
    },
    {
        "loop_id": "memory-consolidation",
        "name": "Memory Consolidation",
        "description": "Consolidates memories during off-peak hours",
        "status": "paused",
        "interval_minutes": 360,
        "created_at": int(time.time()) - 172800,
        "updated_at": int(time.time()) - 86400,
    },
]


def _generate_id(name: str) -> str:
    return name.lower().replace(" ", "-")


@router.get("/loops")
async def get_loops():
    """Get all active loops."""
    return {"loops": _loops}


@router.post("/loops")
async def create_loop(loop: dict):
    """Create a new loop."""
    loop_id = _generate_id(loop.get("name", f"Loop {len(_loops) + 1}"))
    new_loop = {
        "loop_id": loop_id,
        "name": loop.get("name", "Unnamed"),
        "description": loop.get("description"),
        "status": "idle",
        "interval_minutes": loop.get("interval_minutes", 60),
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    _loops.append(new_loop)
    return new_loop


@router.post("/loop/{loop_id}/toggle")
async def toggle_loop(loop_id: str):
    """Toggle a loop on/off."""
    for loop in _loops:
        if loop["loop_id"] == loop_id:
            if loop["status"] == "running":
                loop["status"] = "paused"
            elif loop["status"] == "paused":
                loop["status"] = "running"
            loop["updated_at"] = int(time.time())
            return loop
    raise HTTPException(status_code=404, detail="Loop not found")


@router.delete("/loop/{loop_id}")
async def delete_loop(loop_id: str):
    """Delete a loop."""
    global _loops
    initial_len = len(_loops)
    _loops = [l for l in _loops if l["loop_id"] != loop_id]
    if len(_loops) == initial_len:
        raise HTTPException(status_code=404, detail="Loop not found")
    return {"deleted": loop_id}
