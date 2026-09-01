"""Gateway routes for durable shared agent workspaces."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field

from gateway import agent_workspace

router = APIRouter(tags=["agent-workspaces"])


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    objective: str | None = Field(default=None, max_length=6_000)


class WorkspaceTurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=agent_workspace.MAX_MESSAGE_LENGTH)
    user_id: str = Field(default="jacob", min_length=1, max_length=200)


class GlobalMessageRequest(BaseModel):
    sender_id: str = Field(min_length=1, max_length=200)
    recipient_id: str | None = Field(default=None, min_length=1, max_length=200)
    message_kind: Literal["prompt", "plan", "handoff", "review", "result", "status"] = (
        "status"
    )
    content: str = Field(min_length=1, max_length=agent_workspace.MAX_MESSAGE_LENGTH)
    parent_message_id: str | None = Field(default=None, min_length=1, max_length=200)


class GlobalReceiptRequest(BaseModel):
    participant_id: str = Field(min_length=1, max_length=200)
    state: Literal["seen", "acknowledged"]


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


@router.post("/agent-workspaces/{workspace_id}/turns", status_code=status.HTTP_202_ACCEPTED)
def start_turn(
    workspace_id: str,
    request: WorkspaceTurnRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    try:
        turn = agent_workspace.start_turn(
            workspace_id,
            request.message,
            user_id=request.user_id,
        )
    except agent_workspace.AgentWorkspaceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except agent_workspace.AgentWorkspaceError as exc:
        status_code = 404 if "does not exist" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    background_tasks.add_task(agent_workspace.run_persisted_turn, workspace_id, turn["id"])
    return {"status": "running", "workspace_id": workspace_id, "turn": turn}


def _global_error_status(exc: agent_workspace.AgentWorkspaceError) -> int:
    detail = str(exc)
    if "does not belong" in detail or "does not exist" in detail:
        return 404
    return 400


@router.post("/agent-room/global/ensure")
def ensure_global_room() -> dict:
    try:
        return agent_workspace.ensure_global_workspace()
    except agent_workspace.AgentWorkspaceError as exc:
        raise HTTPException(status_code=_global_error_status(exc), detail=str(exc)) from exc


@router.get("/agent-room/global")
def get_global_room() -> dict:
    try:
        return agent_workspace.ensure_global_workspace()
    except agent_workspace.AgentWorkspaceError as exc:
        raise HTTPException(status_code=_global_error_status(exc), detail=str(exc)) from exc


@router.get("/agent-room/global/messages")
def get_global_messages(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    try:
        agent_workspace.ensure_global_workspace()
        return {"messages": agent_workspace.list_messages(agent_workspace.GLOBAL_WORKSPACE_ID, limit=limit)}
    except agent_workspace.AgentWorkspaceError as exc:
        raise HTTPException(status_code=_global_error_status(exc), detail=str(exc)) from exc

@router.post("/agent-room/global/messages", status_code=status.HTTP_201_CREATED)
def post_global_message(request: GlobalMessageRequest) -> dict:
    try:
        return agent_workspace.post_global_message(
            sender_id=request.sender_id,
            recipient_id=request.recipient_id,
            content=request.content,
            message_kind=request.message_kind,
            parent_message_id=request.parent_message_id,
        )
    except agent_workspace.AgentWorkspaceError as exc:
        raise HTTPException(status_code=_global_error_status(exc), detail=str(exc)) from exc


@router.get("/agent-room/global/inbox/{participant_id}")
def get_global_inbox(
    participant_id: str,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    try:
        return {
            "messages": agent_workspace.list_inbox(
                participant_id, unread_only=unread_only, limit=limit
            )
        }
    except agent_workspace.AgentWorkspaceError as exc:
        raise HTTPException(status_code=_global_error_status(exc), detail=str(exc)) from exc

@router.get("/agent-room/global/threads/{message_id}")
def get_global_thread(
    message_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    try:
        return {"messages": agent_workspace.list_thread(message_id, limit=limit)}
    except agent_workspace.AgentWorkspaceError as exc:
        raise HTTPException(status_code=_global_error_status(exc), detail=str(exc)) from exc


@router.post("/agent-room/global/messages/{message_id}/receipts")
def update_global_receipt(message_id: str, request: GlobalReceiptRequest) -> dict:
    try:
        return agent_workspace.record_receipt(
            message_id,
            request.participant_id,
            request.state,
        )
    except agent_workspace.AgentWorkspaceError as exc:
        raise HTTPException(status_code=_global_error_status(exc), detail=str(exc)) from exc
