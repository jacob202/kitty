"""Kitty Tutor HTTP entrypoint."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from gateway import tutor

router = APIRouter(tags=["tutor"])


class TutorAsk(BaseModel):
    topic: str


class TutorLearn(BaseModel):
    path: str
    label: str | None = None


@router.post("/tutor/ask")
async def tutor_ask(req: TutorAsk) -> dict:
    """Answer a learning question (vocab-first, grounded, never guesses)."""
    return await tutor.ask(req.topic)


@router.post("/tutor/learn")
async def tutor_learn(req: TutorLearn) -> dict:
    """Ingest a document into the Tutor's knowledge collection."""
    result = await tutor.ingest(req.path, label=req.label)
    return {"ingested": True, "result": str(result)}


@router.get("/tutor/review")
async def tutor_review() -> dict:
    """List terms due for spaced-repetition review."""
    return {"due": tutor.due_review()}
