"""Thin Gateway HTTP surface for durable Mission-owned state."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from gateway import memory_mission

router = APIRouter(tags=["missions"])
_SUPERVISOR_ID = "kitty"


class CreateMissionRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=8_000)
    definition_of_done: list[str] = Field(min_length=1)


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2_000)


def _translate(exc: memory_mission.MissionError) -> HTTPException:
    if isinstance(exc, memory_mission.MissionNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


@router.post("/missions", status_code=status.HTTP_201_CREATED)
def create_mission(body: CreateMissionRequest) -> dict:
    try:
        return memory_mission.ensure_mission(
            mission_id=f"mission_{uuid.uuid4().hex}",
            objective=body.objective,
            definition_of_done=body.definition_of_done,
            supervisor_id=_SUPERVISOR_ID,
            db_path=memory_mission.MISSION_DB_FILE,
        )
    except memory_mission.MissionError as exc:
        raise _translate(exc) from exc


@router.get("/missions")
def list_missions() -> dict:
    return {"missions": memory_mission.list_missions(db_path=memory_mission.MISSION_DB_FILE)}


@router.get("/missions/by-origin")
def missions_by_origin(conversation_id: str | None = None, project_id: int | None = None) -> dict:
    """Find the work a chat or project delegated, without any browser state.

    This is the server-owned recovery path: a new browser, a cleared cache, or
    a phone can all ask what a conversation started and get the same answer.
    """
    if conversation_id:
        return {
            "missions": memory_mission.missions_for_conversation(
                conversation_id, db_path=memory_mission.MISSION_DB_FILE
            )
        }
    if project_id is not None:
        return {
            "missions": memory_mission.missions_for_project(
                project_id, db_path=memory_mission.MISSION_DB_FILE
            )
        }
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="name a conversation_id or a project_id",
    )


@router.get("/missions/{mission_id}")
def get_mission(mission_id: str) -> dict:
    try:
        return memory_mission.get_mission(mission_id, db_path=memory_mission.MISSION_DB_FILE)
    except memory_mission.MissionError as exc:
        raise _translate(exc) from exc


@router.post("/missions/{mission_id}/pause")
def pause_mission(mission_id: str, body: ReasonRequest) -> dict:
    try:
        return memory_mission.pause_mission(
            mission_id, reason=body.reason, db_path=memory_mission.MISSION_DB_FILE
        )
    except memory_mission.MissionError as exc:
        raise _translate(exc) from exc


@router.post("/missions/{mission_id}/resume")
def resume_mission(mission_id: str) -> dict:
    try:
        return memory_mission.resume_mission(mission_id, db_path=memory_mission.MISSION_DB_FILE)
    except memory_mission.MissionError as exc:
        raise _translate(exc) from exc


@router.post("/missions/{mission_id}/stop")
def stop_mission(mission_id: str, body: ReasonRequest) -> dict:
    try:
        return memory_mission.stop_mission(
            mission_id, reason=body.reason, db_path=memory_mission.MISSION_DB_FILE
        )
    except memory_mission.MissionError as exc:
        raise _translate(exc) from exc
