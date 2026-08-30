"""Dream / memory consolidation routes — thin FastAPI wrapper."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from gateway import dream_insights

router = APIRouter(tags=["dream"])


@router.get("/dream/status")
async def dream_status() -> dict:
    return dream_insights.dream_status()


@router.post("/dream/trigger")
async def dream_trigger(background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(dream_insights.trigger_dream)
    return {"queued": True}


@router.get("/dream/insights")
async def dream_insights_endpoint() -> dict:
    return {"insights": dream_insights.load_dream_insights()}
