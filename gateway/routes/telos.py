"""TELOS user-identity endpoints — inspect and fill Jacob's profile sections."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gateway import user_context

router = APIRouter(tags=["telos"])


class SectionUpdate(BaseModel):
    content: str


@router.get("/telos")
async def telos_status():
    """Report which TELOS sections are filled vs still empty/template."""
    missing = set(user_context.missing_sections())
    sections = {name: (name not in missing) for name in user_context.get_section_names()}
    return {"sections": sections, "missing": sorted(missing)}


@router.post("/telos/{section}")
async def telos_save(section: str, body: SectionUpdate):
    """Write a TELOS section (e.g. MISSION, GOALS). Activates it in context."""
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="content required")
    if not user_context.update_section(section, body.content):
        raise HTTPException(status_code=400, detail=f"unknown section: {section}")
    return {"saved": section, "missing": user_context.missing_sections()}
