"""Capture endpoints — file/PDF/screenshot -> inbox -> knowledge pipeline."""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from gateway.paths import DATA_DIR, INBOX_FILE

logger = logging.getLogger("kitty.routes.capture")

router = APIRouter(tags=["capture"])

MAX_CAPTURE_BYTES = 50 * 1024 * 1024
CAPTURES_DIR = DATA_DIR / "captures"

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp", ".gif"}


class CapturePathRequest(BaseModel):
    """Body for POST /capture/file when providing a local filesystem path."""

    path: str = Field(..., min_length=1)


class CaptureResponse(BaseModel):
    capture_id: str
    status: str
    message: str


def _ensure_dirs() -> None:
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)


def _extension_for_mime(mime: str | None) -> str:
    return {
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "text/markdown": ".md",
        "text/x-markdown": ".md",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime or "", "")


def _is_allowed_file(filename: str, mime: str | None) -> bool:
    suffix = Path(filename).suffix.lower()
    if suffix in ALLOWED_EXTENSIONS:
        return True
    if mime in ALLOWED_MIME_TYPES:
        return True
    return False


def _write_inbox_event(
    *,
    capture_id: str,
    source_path: str,
    status: str,
    capture_type: str,
) -> None:
    _ensure_dirs()
    event = {
        "capture_id": capture_id,
        "type": capture_type,
        "source_path": source_path,
        "status": status,
        "timestamp": time.time(),
    }
    with INBOX_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _index_capture(capture_id: str, file_path: Path) -> None:
    """Background task: send the captured file through the knowledge pipeline."""
    try:
        import asyncio

        from gateway import knowledge
        from gateway.sse import broadcaster

        result = asyncio.run(
            knowledge.ingest(
                file_path=file_path,
                source_label=file_path.name,
            )
        )
        logger.info(
            "Capture %s indexed: status=%s source=%s",
            capture_id,
            result.status,
            result.source,
        )
        broadcaster.broadcast("knowledge_updated")
    except Exception as exc:
        logger.error("Capture %s indexing failed: %s", capture_id, exc)


@router.post("/capture/file", response_model=CaptureResponse)
async def post_capture_file(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    path: Optional[str] = Form(None),
) -> CaptureResponse:
    """Capture a file (multipart upload) or local path and queue it for indexing."""
    if file is None and not path:
        raise HTTPException(
            status_code=400, detail="provide either a multipart 'file' or a 'path'"
        )
    if file is not None and path:
        raise HTTPException(
            status_code=400, detail="provide only one of 'file' or 'path'"
        )

    capture_id = str(uuid.uuid4())[:12]

    if file is not None:
        filename = file.filename or "capture"
        mime = file.content_type
        if not _is_allowed_file(filename, mime):
            raise HTTPException(
                status_code=415,
                detail=f"unsupported file type: {filename} ({mime or 'unknown mime'})",
            )

        _ensure_dirs()
        ext = Path(filename).suffix.lower() or _extension_for_mime(mime)
        dest = CAPTURES_DIR / f"{capture_id}_{Path(filename).stem}{ext}"

        written = 0
        try:
            with dest.open("wb") as out:
                while chunk := await file.read(64 * 1024):
                    written += len(chunk)
                    if written > MAX_CAPTURE_BYTES:
                        out.close()
                        dest.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=413,
                            detail=f"file exceeds {MAX_CAPTURE_BYTES} bytes",
                        )
                    out.write(chunk)
        finally:
            await file.close()

        source_path = str(dest)
        capture_type = "file_upload"
    else:
        assert path is not None
        source = Path(path).expanduser()
        if not source.exists():
            raise HTTPException(status_code=404, detail=f"file not found: {source}")
        if not source.is_file():
            raise HTTPException(status_code=400, detail=f"not a file: {source}")
        if source.stat().st_size > MAX_CAPTURE_BYTES:
            raise HTTPException(
                status_code=413, detail=f"file exceeds {MAX_CAPTURE_BYTES} bytes"
            )
        if not _is_allowed_file(source.name, None):
            raise HTTPException(
                status_code=415, detail=f"unsupported file type: {source.name}"
            )
        source_path = str(source)
        capture_type = "local_path"

    _write_inbox_event(
        capture_id=capture_id,
        source_path=source_path,
        status="queued",
        capture_type=capture_type,
    )

    background_tasks.add_task(_index_capture, capture_id, Path(source_path))

    return CaptureResponse(
        capture_id=capture_id,
        status="queued",
        message=f"Capture queued for indexing: {Path(source_path).name}",
    )
