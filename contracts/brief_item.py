"""Pydantic contract for a morning brief."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class NewsHeadline(BaseModel):
    title: str
    url: str
    snippet: str = ""
    body: str = ""  # optional clean article text (trafilatura extract)


class BriefItem(BaseModel):
    date: str
    headlines: list[NewsHeadline] = Field(default_factory=list)
    memory_snippet: str = ""
    intention: str = ""
    # 3–5 LLM-generated bullets summarizing what's interesting in today's
    # headlines. Only populated when BRIEF_ENRICH_ARTICLES=1 supplies the
    # article bodies the model needs.
    summary_bullets: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notification_sent: bool = False
    error: Optional[str] = None
