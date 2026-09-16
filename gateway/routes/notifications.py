"""Notification routes.

Split from the former routes/extended.py on 2026-09-16 so each route module
owns one domain (architecture claim: "Routes should remain thin").
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["notifications"])


# --- Notification endpoints ---


class NotifyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    title: str = "Kitty"
    url: Optional[str] = None


@router.post("/notify")
async def notify_send(payload: NotifyRequest):
    from gateway.notify import send

    success = send(payload.message, title=payload.title, url=payload.url)
    return {"sent": success}


@router.post("/notify/test")
async def notify_test():
    from gateway.notify import is_configured, send

    if not is_configured():
        return {
            "configured": False,
            "message": "Set PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN in .env",
        }
    success = send("Kitty notification system is working.", title="Kitty Test")
    return {"configured": True, "sent": success}
