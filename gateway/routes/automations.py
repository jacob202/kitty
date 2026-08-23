"""Automation execution and lifecycle status routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from gateway import automation_actions
from gateway.automation_supervisor import supervisor

router = APIRouter(tags=["automations"])


class ManualRunRequest(BaseModel):
    """Caller-supplied action input; authority stays server-owned."""

    model_config = ConfigDict(extra="forbid")

    automation_id: str = Field(min_length=1, max_length=200)
    trigger_ref: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/automations/actions/{action_name}/run")
async def run_manual_action(action_name: str, payload: ManualRunRequest):
    run = await automation_actions.run_action(
        action_name,
        trigger_kind="manual",
        automation_id=payload.automation_id,
        trigger_ref=payload.trigger_ref,
        payload=payload.payload,
    )
    return {"run": run}


@router.get("/automations/runs")
async def automation_runs(
    automation_id: str | None = None,
    action: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    from gateway.automation_runs import list_runs

    return {"runs": list_runs(automation_id=automation_id, action=action, limit=limit)}


@router.get("/automations/status")
async def automation_status():
    return {
        "actions": automation_actions.get_actions(),
        "services": supervisor.snapshot(),
    }


@router.get("/automations/schedules/{schedule_id}/why")
async def schedule_why(schedule_id: str):
    from dataclasses import asdict

    from gateway.why_not import WhyNotFound, explain_schedule

    try:
        return {"explanation": asdict(explain_schedule(schedule_id))}
    except WhyNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/automations/{action}/why")
async def automation_why(action: str):
    from dataclasses import asdict

    from gateway.why_not import explain_action

    return {"explanation": asdict(explain_action(action))}
