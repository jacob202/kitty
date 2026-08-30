"""Council supervisor HTTP entrypoint."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from gateway.council import CouncilOutput, council_route

router = APIRouter(tags=["council"])


class CouncilRequest(BaseModel):
    message: str
    state: str | None = None


class CouncilTask(BaseModel):
    task_id: str
    assigned_to: str
    output: str
    ok: bool


class CouncilResponse(BaseModel):
    answer: str
    results: list[CouncilTask]
    routing: list[dict] = []
    timings: list[dict] = []
    total_ms: float = 0.0


@router.post("/council")
async def council(request: CouncilRequest) -> CouncilResponse:
    """Run a user message through the Council supervisor (route -> verify -> synthesize)."""
    out: CouncilOutput = council_route(request.message, state=request.state)
    return CouncilResponse(
        answer=out.answer,
        results=[CouncilTask(**asdict(r)) for r in out.results],
        routing=out.routing,
        timings=out.timings,
        total_ms=out.total_ms,
    )
