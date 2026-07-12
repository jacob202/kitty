"""Monitors endpoint for Kitty UI — thin FastAPI wrapper."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gateway import monitors

router = APIRouter(tags=["monitors"])


@router.get("/monitors")
async def get_monitors() -> dict:
    """Get all active monitors."""
    return {"watches": monitors.list_monitors()}


@router.post("/monitor/create")
async def create_monitor(payload: dict) -> dict:
    """Create a new monitor."""
    return monitors.create_monitor(
        payload["url"],
        label=payload.get("label"),
        interval_minutes=payload.get("interval", 300),
    )


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
