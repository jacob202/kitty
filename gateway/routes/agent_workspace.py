"""Gateway routes for durable shared agent workspaces."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from gateway import agent_workspace

router = APIRouter(tags=["agent-workspaces"])


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    objective: str | None = Field(default=None, max_length=6_000)


class WorkspaceTurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=agent_workspace.MAX_MESSAGE_LENGTH)
    user_id: str = Field(default="jacob", min_length=1, max_length=200)


@router.post("/agent-workspaces", status_code=status.HTTP_201_CREATED)
def create_workspace(request: CreateWorkspaceRequest) -> dict:
    try:
        return agent_workspace.create_workspace(
            name=request.name,
            objective=request.objective,
        )
    except agent_workspace.AgentWorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/agent-workspaces/{workspace_id}")
def get_workspace(workspace_id: str) -> dict:
    try:
        return agent_workspace.get_workspace(workspace_id)
    except agent_workspace.AgentWorkspaceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/agent-workspaces/{workspace_id}/messages")
def get_messages(
    workspace_id: str,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict:
    try:
        return {"messages": agent_workspace.list_messages(workspace_id, limit=limit)}
    except agent_workspace.AgentWorkspaceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/agent-workspaces/{workspace_id}/turns")
async def run_turn(workspace_id: str, request: WorkspaceTurnRequest) -> dict:
    try:
        return await asyncio.to_thread(
            agent_workspace.run_turn,
            workspace_id,
            request.message,
            user_id=request.user_id,
        )
    except agent_workspace.AgentWorkspaceError as exc:
        status_code = 404 if "does not exist" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
