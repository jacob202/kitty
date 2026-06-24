"""Monitors endpoint for Kitty UI — thin FastAPI wrapper."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gateway import monitors

router = APIRouter(tags=["monitors"])


@router.get("/monitors")
async def get_monitors() -> dict:
    """Get all active monitors."""
    return {"watches": monitors.list_monitors()}


@router.get("/monitor/create")
async def create_monitor(url: str, interval: int = 300) -> dict:
    """Create a new monitor."""
    return monitors.create_monitor(url, interval_minutes=interval)


@router.delete("/monitor/{monitor_id}")
async def delete_monitor(monitor_id: str) -> dict:
    """Delete a monitor."""
    if not monitors.delete_monitor(monitor_id):
        raise HTTPException(status_code=404, detail="Monitor not found")
    return {"deleted": monitor_id}


@router.get("/monitor/{monitor_id}/check")
async def check_monitor(monitor_id: str) -> dict:
    """Manually check a monitor now."""
    try:
        return await monitors.check_monitor(monitor_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc) or "Monitor not found") from exc
