"""Loops endpoint for Kitty UI — background task loops.

Backed by gateway.cron so the UI surface shows real scheduled tasks instead of
hard-coded demo rows.
"""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, HTTPException

from gateway import cron

router = APIRouter(tags=["loops"])


def _generate_id(name: str) -> str:
    return name.lower().replace(" ", "-")


def _schedule_to_loop(s: dict) -> dict:
    """Map a cron schedule row to the loop shape expected by the UI."""
    metadata = json.loads(s.get("metadata") or "{}")
    interval_minutes = metadata.get("interval_minutes")
    if interval_minutes is None and s.get("schedule_type") == "interval":
        try:
            interval_minutes = int(s.get("schedule_value", 0))
        except ValueError:
            interval_minutes = 0

    enabled = bool(s.get("enabled", 1))
    return {
        "loop_id": s.get("id"),
        "name": s.get("name"),
        "description": metadata.get("description"),
        "status": "running" if enabled else "paused",
        "interval_minutes": interval_minutes or 60,
        "last_run": s.get("last_run") or None,
        "last_result": metadata.get("last_result"),
        "created_at": s.get("created_at") or time.time(),
        "updated_at": s.get("last_run") or s.get("created_at") or time.time(),
    }


@router.get("/loops")
async def get_loops():
    """Get all active loops from the real cron schedule store."""
    return {"loops": [_schedule_to_loop(s) for s in cron.list_schedules()]}


@router.post("/loops")
async def create_loop(loop: dict):
    """Create a new loop as a cron schedule."""
    interval_minutes = loop.get("interval_minutes", 60)
    metadata = {
        "description": loop.get("description"),
        "interval_minutes": interval_minutes,
    }
    sid = cron.schedule(
        name=loop.get("name", "Unnamed"),
        action=loop.get("action", "noop"),
        schedule_type="interval",
        schedule_value=str(interval_minutes),
        metadata=metadata,
    )
    return {
        "loop_id": sid,
        "name": loop.get("name", "Unnamed"),
        "description": loop.get("description"),
        "status": "running",
        "interval_minutes": interval_minutes,
        "created_at": time.time(),
        "updated_at": time.time(),
    }


@router.post("/loop/{loop_id}/toggle")
async def toggle_loop(loop_id: str):
    """Toggle a loop on/off."""
    new_state = cron.toggle(loop_id)
    if new_state is None:
        raise HTTPException(status_code=404, detail="Loop not found")

    for s in cron.list_schedules():
        if s.get("id") == loop_id:
            return _schedule_to_loop(s)
    raise HTTPException(status_code=404, detail="Loop not found")


@router.delete("/loop/{loop_id}")
async def delete_loop(loop_id: str):
    """Delete a loop."""
    if not cron.remove(loop_id):
        raise HTTPException(status_code=404, detail="Loop not found")
    return {"deleted": loop_id}
