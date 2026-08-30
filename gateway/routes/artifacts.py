"""Read-only artifact registry endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from gateway import artifact_store

router = APIRouter(tags=["artifacts"])


@router.get("/artifacts")
def get_artifacts(
    project_id: int | None = None,
    conversation_id: str | None = None,
    kind: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    try:
        return {
            "artifacts": artifact_store.list_artifacts(
                project_id=project_id,
                conversation_id=conversation_id,
                kind=kind,
                limit=limit,
            )
        }
    except artifact_store.ArtifactError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str) -> dict:
    artifact = artifact_store.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"artifact {artifact_id} does not exist")
    return artifact
