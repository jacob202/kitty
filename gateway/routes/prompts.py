"""Prompt templates endpoint — thin FastAPI wrapper."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from gateway import prompts

from pydantic import BaseModel


class PromptTemplateItem(BaseModel):
    id: str
    name: str
    content: str


class PromptsResponse(BaseModel):
    templates: list[PromptTemplateItem]


router = APIRouter(tags=["prompts"])


@router.get("/prompts", response_model=PromptsResponse)
async def get_prompts() -> PromptsResponse:
    """Get prompt templates, optionally filtered by category."""
    return {"templates": prompts.list_templates(category)}
