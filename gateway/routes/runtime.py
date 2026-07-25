"""Authoritative runtime capability manifest."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StrictInt

from gateway import project_context
from gateway.runtime_manifest import compose_manifest

class RuntimeRuntimeManifestResponse(BaseModel):
    model_config = {"extra": "allow"}


class RuntimeContextProjectResponse(BaseModel):
    model_config = {"extra": "allow"}


class RuntimeContextProjectResponse(BaseModel):
    model_config = {"extra": "allow"}



router = APIRouter(tags=["runtime"])


class ActiveProjectRequest(BaseModel):
    project_id: StrictInt


@router.get("/runtime/manifest", response_model=RuntimeRuntimeManifestResponse)
async def get_runtime_manifest(project_id: int | None = None) -> dict:
    """Return a revisioned snapshot of Kitty's observed runtime truth."""
    return await compose_manifest(project_id=project_id)


@router.get("/context/project", response_model=RuntimeContextProjectResponse)
def get_active_project() -> dict:
    """Return the persisted project scope used when requests omit project_id."""
    try:
        return project_context.get_active_project()
    except project_context.ProjectContextError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/context/project", response_model=RuntimeContextProjectResponse)
def put_active_project(payload: ActiveProjectRequest) -> dict:
    """Persist the project scope for subsequent Chat and runtime requests."""
    try:
        return project_context.set_active_project(payload.project_id)
    except project_context.ProjectContextError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
