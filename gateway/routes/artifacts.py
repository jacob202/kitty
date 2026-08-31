"""Read-only artifact registry endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

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



_PREVIEW_MEDIA_TYPES = {
    "application/pdf",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/markdown",
    "text/plain",
    "text/x-markdown",
}


def _preview_artifact(artifact_id: str) -> tuple[dict, Path]:
    artifact = artifact_store.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"artifact {artifact_id} does not exist")
    if artifact.get("state") != "ready":
        raise HTTPException(status_code=409, detail=f"artifact {artifact_id} is not ready to preview")
    media_type = str(artifact.get("media_type") or "application/octet-stream").lower()
    if media_type not in _PREVIEW_MEDIA_TYPES:
        raise HTTPException(status_code=415, detail=f"artifact media type {media_type} is not previewable")
    storage_uri = artifact.get("storage_uri")
    if not isinstance(storage_uri, str) or not storage_uri:
        raise HTTPException(status_code=404, detail=f"artifact {artifact_id} is missing from disk")
    path = Path(storage_uri)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"artifact {artifact_id} is missing from disk")
    return artifact, path


@router.get("/artifacts/{artifact_id}/content")
def get_artifact_content(artifact_id: str) -> FileResponse:
    artifact, path = _preview_artifact(artifact_id)
    return FileResponse(path, media_type=str(artifact["media_type"]))


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str) -> dict:
    artifact = artifact_store.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"artifact {artifact_id} does not exist")
    return artifact
