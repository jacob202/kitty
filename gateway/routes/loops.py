"""Loops endpoint for Kitty UI — background task loops."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["loops"])

# In-memory loop state (would be persisted in production)
_loops: list[dict] = []


@router.get("/loops")
async def get_loops():
    """Get all active loops."""
    return {"loops": _loops}


@router.post("/loops")
async def create_loop(loop: dict):
    """Create a new loop."""
    loop_id = len(_loops) + 1
    new_loop = {
        "id": loop_id,
        "name": loop.get("name", "Unnamed"),
        "interval": loop.get("interval", 3600),
        "enabled": True,
        **loop,
    }
    _loops.append(new_loop)
    return {"id": loop_id, **new_loop}


@router.post("/loop/{loop_id}/toggle")
async def toggle_loop(loop_id: int):
    """Toggle a loop on/off."""
    for loop in _loops:
        if loop["id"] == loop_id:
            loop["enabled"] = not loop["enabled"]
            return loop
    raise HTTPException(status_code=404, detail="Loop not found")


@router.delete("/loop/{loop_id}")
async def delete_loop(loop_id: int):
    """Delete a loop."""
    global _loops
    _loops = [l for l in _loops if l["id"] != loop_id]
    return {"deleted": loop_id}
