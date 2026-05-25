"""Cron schedule management routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["cron"])


class ScheduleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=200)
    schedule_type: str = Field(default="daily")
    schedule_value: str = Field(default="07:00")


@router.get("/cron/schedules")
async def cron_list_schedules():
    from gateway.cron import list_schedules

    return {"schedules": list_schedules()}


@router.get("/cron/actions")
async def cron_list_actions():
    from gateway.cron import get_actions

    return {"actions": get_actions()}


@router.post("/cron/schedule")
async def cron_create_schedule(payload: ScheduleRequest):
    from gateway.cron import schedule

    sid = schedule(
        name=payload.name,
        action=payload.action,
        schedule_type=payload.schedule_type,
        schedule_value=payload.schedule_value,
    )
    return {"id": sid}


@router.delete("/cron/schedule/{sid}")
async def cron_delete_schedule(sid: str):
    from gateway.cron import remove

    ok = remove(sid)
    return {"ok": ok}


@router.post("/cron/schedule/{sid}/toggle")
async def cron_toggle_schedule(sid: str):
    from gateway.cron import toggle

    result = toggle(sid)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {sid}")
    return {"ok": result}
