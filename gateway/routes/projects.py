"""Project registry + resume endpoints (P6/P4, docs/packets/021 + 016).

Sync handlers on purpose: refresh() blocks on git subprocess calls and an
asyncio.run for the memory search, so FastAPI should run these in its
worker pool, not the event loop (same reasoning as /state and /actions).
"""
from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gateway import next_step, project_resume, project_store
from gateway.push import push_to_jacob

logger = logging.getLogger("kitty.routes.projects")

router = APIRouter(tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    paths: list[str] = Field(default_factory=list)
    links: list = Field(default_factory=list)


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    kind: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1)
    paths: list[str] | None = None
    links: list | None = None


def _handle(fn, *args, **kwargs):
    """Run a store/composer call, translating its typed errors to HTTP status."""
    try:
        return fn(*args, **kwargs)
    except project_store.ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except project_store.ProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects")
def get_projects(status: str | None = None) -> dict:
    return {"projects": project_store.list_projects(status=status)}


@router.post("/projects")
def post_project(payload: CreateProjectRequest) -> dict:
    result = _handle(project_store.create, payload.name, payload.kind, payload.paths, payload.links)
    from gateway.sse import broadcaster
    broadcaster.broadcast("projects_updated")
    return result


@router.patch("/projects/{project_id}")
def patch_project(project_id: int, payload: UpdateProjectRequest) -> dict:
    fields: dict = {}
    if payload.name is not None:
        fields["name"] = payload.name
    if payload.kind is not None:
        fields["kind"] = payload.kind
    if payload.status is not None:
        fields["status"] = payload.status
    if payload.paths is not None:
        fields["paths_json"] = payload.paths
    if payload.links is not None:
        fields["links_json"] = payload.links
    if not fields:
        raise HTTPException(status_code=400, detail="no updatable fields in payload")
    result = _handle(project_store.update_fields, project_id, **fields)
    from gateway.sse import broadcaster
    broadcaster.broadcast("projects_updated")
    return result


@router.delete("/projects/{project_id}")
def delete_project(project_id: int) -> dict:
    _handle(project_store.delete, project_id)
    from gateway.sse import broadcaster
    broadcaster.broadcast("projects_updated")
    return {"status": "deleted", "id": project_id}


@router.post("/projects/{project_id}/refresh")
def post_refresh(project_id: int) -> dict:
    refreshed = _handle(project_resume.refresh, project_id)
    # The state refresh above succeeded; a model failure here must degrade,
    # not 500 the whole call (D9: one broken source never kills the read).
    try:
        step = _handle(next_step.generate, project_id)
    except next_step.NextStepError as exc:
        logger.warning("next_step generation failed for project %s: %s", project_id, exc)
        return {**refreshed, "next_step": {"ok": False, "error": str(exc)}}
    if step["changed"]:
        digest = hashlib.sha256(step["step"].encode("utf-8")).hexdigest()[:12]
        push_to_jacob(
            f"{refreshed['name']}: {step['step']}",
            kind="info",
            title="What's next",
            dedupe_key=f"next-step-{project_id}-{digest}",
        )
    from gateway.sse import broadcaster
    broadcaster.broadcast("projects_updated")
    return {**refreshed, "next_step": {"ok": True, **step}}


@router.get("/projects/{project_id}/resume")
def get_resume(project_id: int) -> dict:
    return _handle(project_resume.resume, project_id)


@router.get("/projects/{project_id}/next")
def get_next(project_id: int) -> dict:
    # 404s if the project itself doesn't exist; a project that exists but
    # has never been refreshed under this packet has genuinely no step —
    # that's also a 404, not a fabricated placeholder.
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"no project with id {project_id}")
    step = next_step.get(project_id)
    if step is None:
        raise HTTPException(status_code=404, detail=f"no next step generated yet for project {project_id}")
    return step
