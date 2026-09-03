"""Read-only artifact registry endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from gateway import artifact_store

router = APIRouter(tags=["artifacts"])

MAX_TEXT_PREVIEW_BYTES = 2 * 1024 * 1024


@router.get("/artifacts")
def get_artifacts(
    project_id: int | None = None,
    conversation_id: str | None = None,
    kind: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    include_archived: bool = False,
) -> dict:
    try:
        return {
            "artifacts": artifact_store.list_artifacts(
                project_id=project_id,
                conversation_id=conversation_id,
                kind=kind,
                limit=limit,
                include_archived=include_archived,
            )
        }
    except artifact_store.ArtifactError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc



@router.patch("/artifacts/{artifact_id}/archive")
async def archive_artifact(artifact_id: str, request: Request) -> dict:
    """Reversibly archive or restore an artifact from normal Library results."""
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    if not isinstance(body, dict) or not isinstance(body.get("archived"), bool):
        raise HTTPException(status_code=400, detail="archived must be a boolean")
    try:
        return artifact_store.set_archived(artifact_id, body["archived"])
    except artifact_store.ArtifactError as exc:
        message = str(exc)
        status = 404 if "does not exist" in message else 409
        raise HTTPException(status_code=status, detail=message) from exc


_TEXT_PREVIEW_MEDIA_TYPES = {"text/markdown", "text/plain", "text/x-markdown"}

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

    current_hash, current_size = artifact_store._hash_file(path)
    registered_hash = str(artifact.get("content_hash") or "")
    registered_size = artifact.get("size_bytes")
    if current_hash != registered_hash or current_size != registered_size:
        raise HTTPException(
            status_code=409,
            detail=f"artifact {artifact_id} changed on disk; refresh or re-import it before previewing",
        )
    if media_type in _TEXT_PREVIEW_MEDIA_TYPES and current_size > MAX_TEXT_PREVIEW_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"artifact {artifact_id} is too large to preview as text",
        )
    return artifact, path


@router.get("/artifacts/{artifact_id:path}/content")
def get_artifact_content(artifact_id: str) -> FileResponse:
    artifact, path = _preview_artifact(artifact_id)
    return FileResponse(path, media_type=str(artifact["media_type"]))


@router.get("/artifacts/{artifact_id:path}")
def get_artifact(artifact_id: str) -> dict:
    artifact = artifact_store.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"artifact {artifact_id} does not exist")
    return artifact
