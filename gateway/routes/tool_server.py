"""The deliberately small tool surface Kitty hands to Open WebUI.

Open WebUI turns every operation in an OpenAPI document into a model tool. The
Gateway's full schema contains hundreds of operations, so this router exposes
only bounded, user-facing projections. Reads must stay read-only: a chat tool
must never initialize, migrate, or repair a control-plane store as a side effect.

Mounted under ``/tools/v1`` and protected by the Gateway bearer secret.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field

from gateway.models.builder import Mission
from gateway.paths import BUILDER_QUEUE_DB, PROJECT_ROOT

logger = logging.getLogger("kitty.tool_server")

PREFIX = "/tools/v1"
router = APIRouter(prefix=PREFIX, tags=["kitty-tools"])

_ATTENTION_STATES = {"blocked", "failed", "paused"}
_TOOL_RESULT_LIMIT = 10


class RememberRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000, description="The fact to remember.")
    namespace: str = Field(
        default="facts",
        description="Which shelf it belongs on: facts, preferences, projects.",
    )


def _limit_context(context: str, limit: int) -> str:
    """Keep at most ``limit`` rendered memory items while retaining headings."""
    rendered: list[str] = []
    pending_heading: str | None = None
    item_count = 0

    for raw_line in context.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            pending_heading = line
            continue
        if not line.startswith("- "):
            continue
        if item_count >= limit:
            break
        if pending_heading is not None:
            if rendered:
                rendered.append("")
            rendered.append(pending_heading)
            pending_heading = None
        rendered.append(line)
        item_count += 1

    return "\n".join(rendered)


@router.get(
    "/memory/search",
    operation_id="search_memory",
    summary="Search what Kitty remembers about Jacob",
)
async def search_memory(
    query: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=5, ge=1, le=_TOOL_RESULT_LIMIT),
) -> dict:
    """Search the unified memory graph, including journal, inbox, todos, and facts."""
    from gateway.memory_graph import unified_context

    try:
        context = await unified_context(query, _record=False)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"memory search failed: {exc}") from exc
    return {
        "query": query,
        "context": _limit_context(context, limit),
        "result_limit": limit,
    }


@router.post("/memory/remember", operation_id="remember", summary="Remember something about Jacob")
def remember(body: RememberRequest) -> dict:
    """Store a durable fact. Use for things worth recalling in a later chat."""
    from gateway.memory import add_memory

    try:
        changed = add_memory(body.text, namespace=body.namespace)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"memory write failed: {exc}") from exc
    return {"stored": changed, "namespace": body.namespace}


@router.get(
    "/notes/search",
    operation_id="search_notes",
    summary="Search Jacob's notes, documents, and files",
)
async def search_notes(
    query: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=5, ge=1, le=_TOOL_RESULT_LIMIT),
) -> dict:
    """Retrieval over material deliberately ingested into Kitty's knowledge base."""
    from gateway.knowledge import search as _search

    try:
        chunks = await _search(query, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"note search failed: {exc}") from exc
    return {
        "query": query,
        "results": [
            {"text": c["text"], "source": c["source"], "score": round(c["score"], 3)}
            for c in chunks[:limit]
        ],
    }


@router.get("/projects", operation_id="list_projects", summary="List Jacob's projects")
def list_projects(status: str | None = None) -> dict:
    """Projects Kitty tracks, with life/admin work ahead of code work (ADR 0016)."""
    from gateway.project_store import list_projects as _list

    try:
        projects = _list(status)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"project read failed: {exc}") from exc

    projects.sort(
        key=lambda project: (
            project.get("kind") == "code",
            str(project.get("name") or "").casefold(),
            int(project.get("id") or 0),
        )
    )
    return {"projects": projects}


@router.get(
    "/projects/{project_id}/next-step",
    operation_id="project_next_step",
    summary="The next step on one project",
)
def project_next_step(project_id: int) -> dict:
    """One concrete next action, with an explicit normal empty state."""
    from gateway.next_step import get as _get

    try:
        step = _get(project_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"next step read failed: {exc}") from exc
    if step is None:
        return {
            "project_id": project_id,
            "available": False,
            "next_step": None,
        }
    return {"project_id": project_id, "available": True, "next_step": step}


@router.get("/calendar/today", operation_id="calendar_today", summary="Jacob's schedule today")
async def calendar_today() -> dict:
    """Today's events. ``available: false`` means the calendar is not connected."""
    from gateway.routes.calendar import calendar_today as _today

    try:
        return await _today()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"calendar read failed: {exc}") from exc


@router.get("/tutor/ask", operation_id="ask_tutor", summary="Ask Kitty's Tutor, grounded in ingested docs")
async def ask_tutor(topic: str = Query(min_length=1, max_length=500)) -> dict:
    """Answer from ingested documents and state honestly when none are available."""
    from gateway import tutor

    try:
        return await tutor.ask(topic)
    except tutor.TutorError as exc:
        return {"answer": None, "grounded": False, "reason": str(exc)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"tutor failed: {exc}") from exc


@router.get("/builder/status", operation_id="builder_status", summary="What KittyBuilder is doing")
def builder_status() -> dict:
    """A bounded, genuinely read-only control-plane summary."""
    from gateway.builder_status import build_control_plane_summary

    try:
        snapshot = build_control_plane_summary(db_path=BUILDER_QUEUE_DB)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"builder unavailable: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"builder read failed: {exc}") from exc

    initiatives = snapshot.get("initiatives", [])
    attention = [
        {
            "initiative": initiative.get("title"),
            "state": initiative.get("state"),
            "reason": initiative.get("pause_reason"),
        }
        for initiative in initiatives
        if initiative.get("state") in _ATTENTION_STATES
    ]
    return {
        "queue": snapshot.get("queue", {}),
        "initiative_count": len(initiatives),
        "needs_attention": attention[:_TOOL_RESULT_LIMIT],
        "needs_attention_total": len(attention),
    }


@router.post(
    "/builder/mission",
    operation_id="submit_builder_mission",
    summary="Submit an approved Mission to KittyBuilder",
)
def submit_builder_mission(body: Mission) -> dict:
    """Materialize Kitty's approved Mission through Builder's durable boundary."""
    from gateway.builder_initiative import (
        BaseSHAResolutionError,
        InitiativeConflictError,
        ManifestError,
        MissionSubmissionError,
        submit_mission,
    )

    try:
        return submit_mission(
            body,
            db_path=BUILDER_QUEUE_DB,
            repo_root=PROJECT_ROOT,
        )
    except (MissionSubmissionError, ManifestError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InitiativeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BaseSHAResolutionError as exc:
        raise HTTPException(status_code=503, detail=f"Builder unavailable: {exc}") from exc


@router.get(
    "/builder/mission/{mission_id}",
    operation_id="builder_mission_result",
    summary="Read a Mission's durable Builder result and evidence",
)
def builder_mission_result(mission_id: str) -> dict:
    """Return Builder's read-only projection for one Mission/initiative."""
    from gateway.builder_status_readonly import build_status_snapshot_readonly

    try:
        snapshot = build_status_snapshot_readonly(db_path=BUILDER_QUEUE_DB)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Builder unavailable: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Builder read failed: {exc}") from exc

    initiative = next(
        (
            item
            for item in snapshot.get("initiatives", [])
            if item.get("initiative_id") == mission_id
        ),
        None,
    )
    if initiative is None:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id!r} was not found")
    return {"mission_id": mission_id, "result": initiative}


def _tool_server_spec(server_url: str) -> dict:
    spec = get_openapi(
        title="Kitty",
        version="1",
        description=(
            "Jacob's own memory, notes, projects, and build queue. "
            "Prefer these over guessing; they are the source of truth for personal state."
        ),
        routes=router.routes,
    )
    spec["servers"] = [{"url": server_url.rstrip("/")}]
    return spec


@router.get("/openapi.json", include_in_schema=False)
def tool_server_openapi(request: Request) -> dict:
    """The bounded spec Open WebUI reads, anchored to the actual Gateway origin."""
    return _tool_server_spec(str(request.base_url))
