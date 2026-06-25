"""Monitors endpoint for Kitty UI — web/page monitors."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["monitors"])

# In-memory monitor state
_monitors: list[dict] = []


@router.get("/monitors")
async def get_monitors():
    """Get all active monitors."""
    # Try to get from web_monitor module
    try:
        from gateway.web_monitor import list_watches
        watches = list_watches()
        return {"watches": watches}
    except (ImportError, AttributeError):
        return {"watches": _monitors}


@router.get("/monitor/create")
async def create_monitor(url: str, interval: int = 300):
    """Create a new monitor."""
    monitor_id = len(_monitors) + 1
    new_monitor = {
        "watch_id": monitor_id,
        "url": url,
        "interval": interval,
        "enabled": True,
        "last_checked": None,
        "status": "pending",
    }
    _monitors.append(new_monitor)

    # Try to register with web_monitor
    try:
        from gateway.web_monitor import add_watch
        new_monitor["watch_id"] = add_watch(url, interval_minutes=interval)
        return new_monitor
    except (ImportError, AttributeError):
        return new_monitor


@router.delete("/monitor/{monitor_id}")
async def delete_monitor(monitor_id: str):
    """Delete a monitor."""
    global _monitors
    _monitors = [m for m in _monitors if m.get("watch_id") != monitor_id]

    try:
        from gateway.web_monitor import remove_watch
        remove_watch(monitor_id)
    except (ImportError, AttributeError):
        pass

    return {"deleted": monitor_id}


@router.get("/monitor/{monitor_id}/check")
async def check_monitor(monitor_id: str):
    """Manually check a monitor now."""
    try:
        from gateway.web_monitor import check_now
        result = await check_now(monitor_id)
        return result
    except (ImportError, AttributeError, HTTPException):
        raise HTTPException(status_code=404, detail="Monitor not found or check failed")
