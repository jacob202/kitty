"""Monitors endpoint for Kitty UI — thin FastAPI wrapper."""

from __future__ import annotations

from fastapi import APIRouter

from gateway import monitors
from gateway.errors import StorageNotFound, ValidationError

router = APIRouter(tags=["monitors"])


@router.get("/monitors")
async def get_monitors() -> dict:
    """Get all active monitors."""
    return {"watches": monitors.list_monitors()}


@router.post("/monitor/create")
async def create_monitor(payload: dict) -> dict:
    """Create a new monitor."""
    if "url" not in payload:
        raise ValidationError(
            "monitor create request is missing required field 'url'",
            details={"field": "url"},
        )
    try:
        return monitors.create_monitor(
            payload["url"],
            label=payload.get("label"),
            interval_minutes=payload.get("interval", 300),
        )
    except ValueError as exc:
        raise ValidationError(
            f"invalid monitor create request: {exc}",
            details={"operation": "create"},
        ) from exc


@router.delete("/monitor/{monitor_id}")
async def delete_monitor(monitor_id: str) -> dict:
    """Delete a monitor."""
    try:
        deleted = monitors.delete_monitor(monitor_id)
    except ValueError as exc:
        raise ValidationError(
            f"invalid monitor delete request: {exc}",
            details={"monitor_id": monitor_id},
        ) from exc
    if not deleted:
        raise StorageNotFound(
            f"monitor {monitor_id!r} was not found",
            details={"monitor_id": monitor_id},
        )
    return {"deleted": monitor_id}


@router.get("/monitor/{monitor_id}/check")
async def check_monitor(monitor_id: str) -> dict:
    """Manually check a monitor now."""
    try:
        return await monitors.check_monitor(monitor_id)
    except ValueError as exc:
        raise ValidationError(
            f"invalid monitor check request: {exc}",
            details={"monitor_id": monitor_id},
        ) from exc
