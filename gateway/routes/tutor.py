"""Kitty Tutor HTTP entrypoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gateway import tutor

router = APIRouter(tags=["tutor"])


class TutorAsk(BaseModel):
    topic: str


class TutorLearn(BaseModel):
    path: str
    label: str | None = None


class TutorAttempt(BaseModel):
    term: str = Field(min_length=1)
    correct: bool
    kp_type: str = "memory"
    subject: str = ""


class TutorGrade(BaseModel):
    user_answer: str
    expected_answer: str = Field(min_length=1)
    question_type: str = "open"


def _knowledge_type(raw: str) -> tutor.KnowledgeType:
    try:
        return tutor.KnowledgeType(raw)
    except ValueError as exc:
        valid = ", ".join(t.value for t in tutor.KnowledgeType)
        raise HTTPException(
            status_code=400,
            detail=f"kp_type must be one of: {valid}; got {raw!r}",
        ) from exc


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


@router.get("/tutor/quiz")
async def tutor_quiz(limit: int = 5) -> dict:
    """Deterministic recall quiz over due terms (DTH-04c). Empty when fewer
    than two terms are due — the quiz format needs distractors."""
    due = tutor.due_review()
    terms = [d["term"] for d in due][: max(limit, 2)]
    if len(terms) < 2:
        return {"questions": [], "due": len(due)}
    return {"questions": tutor.generate_recall_quiz(terms), "due": len(due)}


@router.post("/tutor/attempt")
async def tutor_attempt(req: TutorAttempt) -> dict:
    """Record a quiz attempt (DTH-04): recompute mastery, reschedule review."""
    kp = _knowledge_type(req.kp_type)
    try:
        mastery = tutor.log_attempt(req.term, req.correct, kp, req.subject)
    except tutor.TutorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "term": req.term,
        "mastery": mastery,
        "stage": tutor.stage_of(req.term, kp).value,
        "next_action": tutor.next_action(req.term, kp),
    }


@router.post("/tutor/grade")
async def tutor_grade(req: TutorGrade) -> dict:
    """Deterministic grading (DTH-03) — no LLM variance."""
    if req.question_type not in {"choice", "short", "open"}:
        raise HTTPException(
            status_code=400,
            detail=f"question_type must be choice|short|open, got {req.question_type!r}",
        )
    return {
        "correct": tutor.grade_answer(
            req.user_answer, req.expected_answer, req.question_type
        )
    }


@router.get("/tutor/term/{term}")
async def tutor_term(term: str, kp_type: str = "memory") -> dict:
    """Mastery, stage, and advisory next action for one term."""
    kp = _knowledge_type(kp_type)
    return {
        "term": term,
        "mastery": tutor.mastery_of(term),
        "stage": tutor.stage_of(term, kp).value,
        "next_action": tutor.next_action(term, kp),
    }
