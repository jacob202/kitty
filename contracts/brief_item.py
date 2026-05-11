"""Pydantic contract for a morning brief."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class NewsHeadline(BaseModel):
    title: str
    url: str
    snippet: str = ""


class BriefItem(BaseModel):
    date: str
    headlines: list[NewsHeadline] = Field(default_factory=list)
    memory_snippet: str = ""
    intention: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notification_sent: bool = False
    error: Optional[str] = None
