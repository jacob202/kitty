"""Prompt templates endpoint — thin FastAPI wrapper."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from gateway import prompts

router = APIRouter(tags=["prompts"])


@router.get("/prompts")
async def get_prompts(category: Optional[str] = None) -> dict:
    """Get prompt templates, optionally filtered by category."""
    return {"templates": prompts.list_templates(category)}
