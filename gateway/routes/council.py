"""Council supervisor HTTP entrypoint."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from gateway.council import council_route

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
    results: list[CouncilTask]


@router.post("/council")
async def council(request: CouncilRequest) -> CouncilResponse:
    """Run a user message through the Council supervisor (analyze -> route -> verify)."""
    results = council_route(request.message, state=request.state)
    return CouncilResponse(
        results=[CouncilTask(**asdict(r)) for r in results]
    )
