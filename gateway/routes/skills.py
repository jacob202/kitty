"""Skill routes.

Split from the former routes/extended.py on 2026-09-16 so each route module
owns one domain (architecture claim: "Routes should remain thin").
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["skills"])


# --- Skill endpoints ---


@router.get("/skills")
async def skills_list(q: Optional[str] = None):
    from gateway.skill_registry import discover, search

    if q:
        return {"skills": search(q)}
    return {"skills": discover()}


@router.get("/skill/{name}")
async def skill_get(name: str):
    from gateway.skill_registry import get

    skill = get(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {name}")
    return skill


class SkillInvokeRequest(BaseModel):
    context: Optional[str] = None


@router.post("/skill/{name}/invoke")
async def skill_invoke(name: str, payload: SkillInvokeRequest = SkillInvokeRequest()):
    from gateway.skill_registry import invoke

    result = invoke(name, context=payload.context)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
