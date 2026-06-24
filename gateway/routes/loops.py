"""Loops endpoint for Kitty UI — thin FastAPI wrapper."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gateway import loops

router = APIRouter(tags=["loops"])


@router.get("/loops")
async def get_loops() -> dict:
    """Get all active loops."""
    return {"loops": loops.list_loops()}


@router.post("/loops")
async def create_loop(loop: dict) -> dict:
    """Create a new loop."""
    return loops.create_loop(loop)


@router.post("/loop/{loop_id}/toggle")
async def toggle_loop(loop_id: str) -> dict:
    """Toggle a loop on/off."""
    updated = loops.toggle_loop(loop_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Loop not found")
    return updated


@router.delete("/loop/{loop_id}")
async def delete_loop(loop_id: str) -> dict:
    """Delete a loop."""
    if not loops.delete_loop(loop_id):
        raise HTTPException(status_code=404, detail="Loop not found")
    return {"deleted": loop_id}
