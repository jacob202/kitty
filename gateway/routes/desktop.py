"""Desktop-specific Phase 1 endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gateway.desktop_store import append_text_capture, desktop_status, read_inbox

class DesktopDesktopStatusResponse(BaseModel):
    model_config = {"extra": "allow"}


class DesktopDesktopInboxResponse(BaseModel):
    model_config = {"extra": "allow"}


class DesktopDesktopCaptureResponse(BaseModel):
    model_config = {"extra": "allow"}



router = APIRouter(tags=["desktop"])


class DesktopCaptureRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    source: str = "desktop_quick_capture"
    type: Literal["text", "voice_note", "photo", "file", "distress_signal"] = "text"
    project: str | None = None
    tags: list[str] = Field(default_factory=list)


@router.get("/desktop/status", response_model=DesktopDesktopStatusResponse)
async def get_desktop_status():
    return desktop_status()


@router.get("/desktop/inbox", response_model=DesktopDesktopInboxResponse)
async def get_desktop_inbox(limit: int = 20):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    return {"entries": read_inbox(limit=limit)}


@router.post("/desktop/capture", response_model=DesktopDesktopCaptureResponse)
async def post_desktop_capture(payload: DesktopCaptureRequest):
    entry = append_text_capture(
        text=payload.text,
        source=payload.source,
        capture_type=payload.type,
        project=payload.project,
        tags=payload.tags,
    )
    return {"ok": True, "entry": entry}
