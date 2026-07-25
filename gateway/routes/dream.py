"""Dream / memory consolidation routes — thin FastAPI wrapper."""


from __future__ import annotations
from pydantic import BaseModel

from fastapi import APIRouter, BackgroundTasks

from gateway import dream_insights

class DreamDreamStatusResponse(BaseModel):
    model_config = {"extra": "allow"}


class DreamDreamTriggerResponse(BaseModel):
    model_config = {"extra": "allow"}


class DreamDreamInsightsResponse(BaseModel):
    model_config = {"extra": "allow"}



router = APIRouter(tags=["dream"])


@router.get("/dream/status", response_model=DreamDreamStatusResponse)
async def dream_status() -> dict:
    return dream_insights.dream_status()


@router.post("/dream/trigger", response_model=DreamDreamTriggerResponse)
async def dream_trigger(background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(dream_insights.trigger_dream)
    return {"queued": True}


@router.get("/dream/insights", response_model=DreamDreamInsightsResponse)
async def dream_insights_endpoint() -> dict:
    return {"insights": dream_insights.load_dream_insights()}
