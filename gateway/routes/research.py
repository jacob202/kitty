from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field

from gateway import project_store, research_execution, research_runs

router = APIRouter(tags=["research"])


class StartResearchRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=1000)
    project_id: int | None = Field(default=None, ge=1)


@router.post("/research/runs", status_code=status.HTTP_202_ACCEPTED)
def start_research(request: StartResearchRequest, background_tasks: BackgroundTasks) -> dict:
    if request.project_id is not None and project_store.get(request.project_id) is None:
        raise HTTPException(status_code=404, detail=f"project {request.project_id} not found")
    try:
        run = research_runs.begin_run(topic=request.topic, project_id=request.project_id)
    except research_runs.ResearchRunError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(research_execution.run_persisted_research_background, run["id"])
    return {"run": run}


@router.get("/research/runs")
def list_research_runs(limit: int = Query(default=20, ge=1, le=100), project_id: int | None = Query(default=None, ge=1)) -> dict:
    return {"runs": research_runs.list_runs(limit=limit, project_id=project_id)}


@router.get("/research/runs/{run_id}")
def get_research_run(run_id: str) -> dict:
    run = research_runs.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"research run {run_id} not found")
    return {"run": run}
