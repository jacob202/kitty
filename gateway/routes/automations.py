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


@router.post("/automations/runs/{run_id}/retry")
async def retry_automation_run(run_id: str):
    """Re-run a completed run with the same intent but a fresh identity.

    Authorization is re-evaluated against the current grant state; the original
    decision is never reused blindly.
    """
    import time

    from gateway import automation_runs

    original = automation_runs.get_run(run_id)
    if original is None:
        raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    if original["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail=f"run {run_id!r} is still running and cannot be retried",
        )
    retried = automation_runs.retry_run(run_id, started_at=time.time())
    evidence = original.get("policy") or {}
    final_run = await automation_actions.run_action(
        original["action"],
        trigger_kind=original["trigger_kind"],
        automation_id=original["automation_id"],
        trigger_ref=original.get("trigger_ref"),
        schedule_id=original.get("schedule_id"),
        payload=original.get("payload") or {},
        run_id=retried["id"],
        policy_scope_type=evidence.get("scope_type"),
        policy_scope_id=evidence.get("scope_id"),
    )
    return {"run": final_run, "retried_from": run_id}
