"""Agent routes.

Split from the former routes/extended.py on 2026-09-16 so each route module
owns one domain (architecture claim: "Routes should remain thin").
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["agents"])


# --- Agent endpoints ---


class AgentSpawnRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    agent_type: str = "explorer"
    model: Optional[str] = None
    max_iterations: Optional[int] = None
    temperature: Optional[float] = None
    extra_context: Optional[str] = None


@router.post("/agent/spawn")
async def agent_spawn(payload: AgentSpawnRequest):
    from gateway.agent_runner import spawn

    session_id = await spawn(
        goal=payload.goal,
        agent_type=payload.agent_type,
        model=payload.model,
        max_iterations=payload.max_iterations,
        temperature=payload.temperature,
        extra_context=payload.extra_context,
    )
    return {"session_id": session_id, "status": "spawned"}


@router.get("/agent/{session_id}")
async def agent_status(session_id: int):
    from gateway.agent_runner import get_output, get_status
    from gateway.autonomy_state import TERMINAL_STATUSES

    status = get_status(session_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Agent not found")
    if status.get("status") in TERMINAL_STATUSES:
        status["output"] = get_output(session_id)
    return status


@router.get("/agents")
async def agent_list(limit: int = 20):
    from gateway.agent_runner import list_agents

    return {"agents": list_agents(limit=limit)}


@router.post("/agent/{session_id}/stop")
async def agent_stop(session_id: int):
    from gateway.agent_runner import stop

    stopped = stop(session_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="Agent not running")
    return {"session_id": session_id, "status": "cancelled"}
