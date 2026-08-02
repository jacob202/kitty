"""The tool surface Kitty hands to Open WebUI.

Open WebUI calls an OpenAPI server's operations as tools, so whatever this spec
lists is what the model can reach. The Gateway's own ``/openapi.json`` describes
more than two hundred operations across 54 route modules — handing that over
would bury the useful ones and cost a fortune in prompt. This module is a small,
deliberate menu instead, and every operation delegates to the function that
already owns the behaviour rather than reimplementing it.

Mounted under ``/tools/v1``. The Gateway's bearer auth covers it like any other
path; Open WebUI is configured with the same Gateway secret.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field

logger = logging.getLogger("kitty.tool_server")

PREFIX = "/tools/v1"
router = APIRouter(prefix=PREFIX, tags=["kitty-tools"])

# Builder's raw snapshot carries every initiative record — 425KB on Jacob's Mac.
# A tool result goes straight into the model's context, so this returns counts
# and the packets that need a human, never the corpus.
_ATTENTION_STATES = {"blocked", "failed"}


class RememberRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000, description="The fact to remember.")
    namespace: str = Field(
        default="facts",
        description="Which shelf it belongs on: facts, preferences, projects.",
    )


@router.get("/memory/search", summary="Search what Kitty remembers about Jacob")
def search_memory(query: str, limit: int = 5) -> dict:
    """Personal memory: facts, preferences, and history Jacob has told Kitty."""
    from gateway.memory import search_memory as _search

    try:
        return {"query": query, "results": _search(query, limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"memory search failed: {exc}") from exc


@router.post("/memory/remember", summary="Remember something about Jacob")
def remember(body: RememberRequest) -> dict:
    """Store a durable fact. Use for things worth recalling in a later chat."""
    from gateway.memory import add_memory

    try:
        changed = add_memory(body.text, namespace=body.namespace)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"memory write failed: {exc}") from exc
    return {"stored": changed, "namespace": body.namespace}


@router.get("/notes/search", summary="Search Jacob's notes, documents, and files")
async def search_notes(query: str, limit: int = 5) -> dict:
    """Retrieval over everything ingested into Kitty's knowledge base."""
    from gateway.knowledge import search as _search

    try:
        chunks = await _search(query, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"note search failed: {exc}") from exc
    return {
        "query": query,
        "results": [
            {"text": c["text"], "source": c["source"], "score": round(c["score"], 3)}
            for c in chunks
        ],
    }


@router.get("/projects", summary="List Jacob's projects")
def list_projects(status: str | None = None) -> dict:
    """Projects Kitty tracks. Life projects come before code projects (ADR 0016)."""
    from gateway.project_store import list_projects as _list

    try:
        return {"projects": _list(status)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"project read failed: {exc}") from exc


@router.get("/projects/{project_id}/next-step", summary="The next step on one project")
def project_next_step(project_id: int) -> dict:
    """One concrete next action, not a plan. Returns null when none is recorded."""
    from gateway.next_step import get as _get

    try:
        step = _get(project_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"next step read failed: {exc}") from exc
    if step is None:
        raise HTTPException(
            status_code=404, detail=f"no next step recorded for project {project_id}"
        )
    return step


@router.get("/builder/status", summary="What KittyBuilder is doing")
def builder_status() -> dict:
    """Queue counts and only the packets needing a human. Never the full corpus."""
    from gateway.builder_status import build_status_snapshot

    try:
        snapshot = build_status_snapshot()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"builder read failed: {exc}") from exc

    attention = [
        {
            "initiative": initiative.get("title"),
            "packet": packet.get("title"),
            "state": packet.get("task_state"),
            "reason": packet.get("blocked_reason") or packet.get("last_error"),
        }
        for initiative in snapshot.get("initiatives", [])
        for packet in initiative.get("packets", [])
        if packet.get("task_state") in _ATTENTION_STATES
    ]
    return {
        "queue": snapshot.get("queue", {}),
        "initiative_count": len(snapshot.get("initiatives", [])),
        "needs_attention": attention[:10],
        "needs_attention_total": len(attention),
    }


@router.get("/openapi.json", include_in_schema=False)
def tool_server_openapi() -> dict:
    """The spec Open WebUI reads — only this router's operations."""
    spec = get_openapi(
        title="Kitty",
        version="1",
        description=(
            "Jacob's own memory, notes, projects, and build queue. "
            "Prefer these over guessing; they are the only source of truth for "
            "anything personal."
        ),
        routes=router.routes,
    )
    # Open WebUI resolves operation paths against this, and the paths above are
    # already absolute, so the server URL must stop at the host.
    spec["servers"] = [{"url": "http://127.0.0.1:8000"}]
    return spec
