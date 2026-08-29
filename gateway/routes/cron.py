"""Cron schedule management routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(tags=["cron"])


class ScheduleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=200)
    schedule_type: str = Field(default="daily")
    schedule_value: str = Field(default="07:00")
    timezone: str | None = Field(default=None, max_length=100)


def _validate_timezone(timezone: str | None) -> dict:
    """Return metadata for a schedule, rejecting an unknown IANA zone."""
    if timezone is None:
        return {}
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=422, detail=f"Unknown timezone: {timezone}")
    return {"timezone": timezone}


@router.get("/cron/schedules")
async def cron_list_schedules():
    from gateway.cron import list_schedules

    return {"schedules": list_schedules()}


@router.get("/cron/actions")
async def cron_list_actions():
    from gateway.cron import get_actions

    return {"actions": get_actions()}


@router.get("/cron/runs")
async def cron_list_runs(
    automation_id: str | None = None,
    action: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    from gateway.automation_runs import list_runs

    return {"runs": list_runs(automation_id=automation_id, action=action, limit=limit)}


@router.get("/cron/schedule/{sid}/status")
async def cron_schedule_status(sid: str):
    from gateway.automation_runs import list_runs
    from gateway.cron import explain_schedule, list_schedules

    schedule_row = next((row for row in list_schedules() if row["id"] == sid), None)
    if schedule_row is None:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {sid}")
    runs = list_runs(automation_id=sid, limit=1)
    return {
        "schedule": schedule_row,
        "execution": explain_schedule(schedule_row),
        "latest_run": runs[0] if runs else None,
    }


@router.post("/cron/schedule")
async def cron_create_schedule(payload: ScheduleRequest):
    from gateway.cron import schedule

    sid = schedule(
        name=payload.name,
        action=payload.action,
        schedule_type=payload.schedule_type,
        schedule_value=payload.schedule_value,
        metadata=_validate_timezone(payload.timezone),
    )
    return {"id": sid}


@router.delete("/cron/schedule/{sid}")
async def cron_delete_schedule(sid: str):
    from gateway.cron import remove

    ok = remove(sid)
    return {"ok": ok}


@router.patch("/cron/schedule/{sid}")
async def cron_update_schedule(sid: str, payload: ScheduleRequest):
    from gateway import undo_journal

    try:
        undo_journal.update_automation_with_undo(
            sid,
            payload.name,
            payload.action,
            payload.schedule_type,
            payload.schedule_value,
            metadata=_validate_timezone(payload.timezone),
        )
    except undo_journal.UndoNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {sid}") from exc
    return {"ok": True}


@router.post("/cron/schedule/{sid}/toggle")
async def cron_toggle_schedule(sid: str):
    from gateway import cron, undo_journal

    try:
        undo_journal.toggle_automation_with_undo(sid)
    except undo_journal.UndoNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {sid}") from exc
    current = next((row for row in cron.list_schedules() if row.get("id") == sid), None)
    if current is None:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {sid}")
    return {"ok": bool(current.get("enabled"))}
