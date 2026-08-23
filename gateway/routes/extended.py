"""Skills, agents, tasks, notifications, and image generation."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel, Field

router = APIRouter(tags=["extended"])

# --- Notification endpoints ---


class NotifyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    title: str = "Kitty"
    url: Optional[str] = None


@router.post("/notify")
async def notify_send(payload: NotifyRequest):
    from gateway.notify import send

    success = send(payload.message, title=payload.title, url=payload.url)
    return {"sent": success}


@router.get("/notify/test")
async def notify_test():
    from gateway.notify import is_configured, send

    if not is_configured():
        return {
            "configured": False,
            "message": "Set PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN in .env",
        }
    success = send("Kitty notification system is working.", title="Kitty Test")
    return {"configured": True, "sent": success}


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


# --- Todo endpoints ---


class TodoUpdateRequest(BaseModel):
    items: list[dict] = Field(default_factory=list)


@router.post("/todos")
async def todos_update(payload: TodoUpdateRequest):
    """Replace the entire todo list. Model-invokable structured task tracking."""
    from gateway.storage_router import replace_todos

    return {"todos": replace_todos(payload.items)}


@router.get("/todos")
async def todos_get():
    from gateway.todo_store import get

    return {"todos": get()}


@router.post("/todos/clear")
async def todos_clear():
    from gateway.storage_router import clear_todos

    clear_todos()
    return {"todos": []}


class TodoAddRequest(BaseModel):
    content: str = Field(min_length=1, max_length=500)
    status: str = "pending"
    active_form: str = ""


@router.post("/todos/add")
async def todos_add(payload: TodoAddRequest):
    from gateway.storage_router import add_todo

    return add_todo(payload.content, payload.status, payload.active_form)


@router.post("/todos/{todo_id}/complete")
async def todos_complete_by_id(todo_id: int):
    from gateway.storage_router import complete_todo

    return {"completed": complete_todo(todo_id), "id": todo_id}


@router.delete("/todos/{todo_id}")
async def todos_delete(todo_id: int):
    from gateway.storage_router import delete_todo

    return {"deleted": delete_todo(todo_id), "id": todo_id}


# --- Agent endpoints ---


class AgentSpawnRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    agent_type: str = "explorer"
    model: Optional[str] = None
    max_iterations: Optional[int] = None
    temperature: Optional[float] = None
    extra_context: Optional[str] = None


@router.post("/agent/spawn")
async def agent_spawn(payload: AgentSpawnRequest):
    from gateway.agent_runner import spawn

    session_id = await spawn(
        goal=payload.goal,
        agent_type=payload.agent_type,
        model=payload.model,
        max_iterations=payload.max_iterations,
        temperature=payload.temperature,
        extra_context=payload.extra_context,
    )
    return {"session_id": session_id, "status": "spawned"}


@router.get("/agent/{session_id}")
async def agent_status(session_id: int):
    from gateway.agent_runner import get_output, get_status

    status = get_status(session_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Agent not found")
    if status.get("status") in ("completed", "failed", "cancelled"):
        status["output"] = get_output(session_id)
    return status


@router.get("/agents")
async def agent_list(limit: int = 20):
    from gateway.agent_runner import list_agents

    return {"agents": list_agents(limit=limit)}


@router.post("/agent/{session_id}/stop")
async def agent_stop(session_id: int):
    from gateway.agent_runner import stop

    stopped = stop(session_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="Agent not running")
    return {"session_id": session_id, "status": "cancelled"}


# --- Task endpoints ---


class TaskCreateRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    task_type: str = "research"
    model: Optional[str] = None
    metadata: Optional[dict] = None
    run_immediately: bool = True


@router.post("/task/create")
async def task_create(payload: TaskCreateRequest):
    from gateway.task_runner import create

    task_id = create(
        goal=payload.goal,
        task_type=payload.task_type,
        model=payload.model,
        metadata=payload.metadata,
        run_immediately=payload.run_immediately,
    )
    return {"task_id": task_id, "status": "queued"}


@router.get("/tasks")
async def task_list(status: Optional[str] = None, limit: int = 20):
    from gateway.task_runner import list_tasks

    return {"tasks": list_tasks(status=status, limit=limit)}


@router.get("/task/{task_id}")
async def task_get(task_id: str):
    from gateway.task_runner import get

    task = get(task_id)
    if task.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/task/{task_id}/output")
async def task_output(task_id: str):
    from gateway.task_runner import get_output

    output = get_output(task_id)
    return {"task_id": task_id, "output": output}


@router.post("/task/{task_id}/cancel")
async def task_cancel(task_id: str):
    from gateway.task_runner import cancel

    cancelled = cancel(task_id)
    if not cancelled:
        raise HTTPException(
            status_code=404, detail="Task not found or already finished"
        )
    return {"task_id": task_id, "status": "cancelled"}


# --- Image generation ---


class ImageGenRequest(BaseModel):
    prompt: str
    engine: str = "comfyui"
    parent_id: Optional[str] = None


COMFYUI_OFFLINE_REASON = (
    "ComfyUI is not running on this Mac. Start ComfyUI, then check again."
)
DRAWTHINGS_OFFLINE_REASON = (
    "Draw Things is not answering. Open the Draw Things app, turn on its API "
    "server, then check again."
)


@router.get("/image/status")
async def image_status():
    import asyncio

    from gateway.image_gen import is_available

    comfy_available = await is_available()

    # Draw Things is an optional local engine.  Its health probe is kept on
    # the adapter so this route reports the transport Kitty actually uses.
    from mcp.imagen.engines import get

    drawthings = get("drawthings")
    probe = getattr(getattr(drawthings, "_adapter", None), "is_available", None)
    if probe is None:
        raise RuntimeError("drawthings engine adapter does not expose is_available()")
    drawthings_available = bool(await asyncio.to_thread(probe))

    from gateway.image_runner import (
        airforce_images_available,
        fal_images_available,
        flux_images_available,
        openrouter_images_available,
    )

    airforce_available, airforce_reason = airforce_images_available()
    flux_available, flux_reason = flux_images_available()
    fal_available, fal_reason = fal_images_available()
    hosted_available, hosted_reason = openrouter_images_available()
    engines = [
        {
            "name": "comfyui",
            "label": "ComfyUI",
            "available": comfy_available,
            "unavailable_reason": None if comfy_available else COMFYUI_OFFLINE_REASON,
        },
        {
            "name": "drawthings",
            "label": "Draw Things",
            "available": drawthings_available,
            "unavailable_reason": None if drawthings_available else DRAWTHINGS_OFFLINE_REASON,
        },
        {
            "name": "airforce",
            "label": "Grok Imagine 2.0 via Airforce",
            "available": airforce_available,
            "unavailable_reason": airforce_reason or None,
            "cost_per_image_usd": 0.01,
        },
        {
            "name": "flux",
            "label": "Flux (Black Forest Labs)",
            "available": flux_available,
            "unavailable_reason": flux_reason or None,
            "cost_per_image_usd": 0.025,
        },
        {
            "name": "fal",
            "label": "FLUX PuLID via fal",
            "available": fal_available,
            "unavailable_reason": fal_reason or None,
            # fal bills PuLID at $0.0333/output MP, rounding up. Kitty's
            # default square_hd output is 1024x1024 (>1 MP), so its provider
            # price is two billable MP = $0.0666 before the $0.07 budget guard.
            "cost_per_image_usd": 0.0666,
            "cost_per_megapixel_usd": 0.0333,
        },
        {
            "name": "openrouter",
            "label": "Gemini via OpenRouter",
            "available": hosted_available,
            "unavailable_reason": hosted_reason or None,
            "cost_per_image_usd": 0.067,
        },
    ]
    available = (
        comfy_available
        or drawthings_available
        or airforce_available
        or flux_available
        or fal_available
        or hosted_available
    )
    # Local first when it is up (free), then the cheapest hosted lane.
    if comfy_available:
        backend = "comfyui"
    elif drawthings_available:
        backend = "drawthings"
    elif airforce_available:
        backend = "airforce"
    elif flux_available:
        backend = "flux"
    elif fal_available:
        backend = "fal"
    elif hosted_available:
        backend = "openrouter"
    else:
        backend = "comfyui"
    return {"available": available, "backend": backend, "engines": engines}


@router.post("/image/generate")
async def image_generate(req: ImageGenRequest):
    from gateway.image_runner import ENGINES, ImageRunnerError, run

    engine = req.engine.strip().lower()
    if engine not in ENGINES:
        raise HTTPException(
            status_code=422, detail=f"engine must be one of {', '.join(sorted(ENGINES))}"
        )

    try:
        result = await run(engine, req.prompt, parent_id=req.parent_id)
        return {
            "prompt_id": result.prompt_id,
            "filename": result.filename,
            "job_id": result.job_id,
            "engine": result.engine,
        }
    except ImageRunnerError as e:
        status = 503 if "not running" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/image/{job_id}/cancel")
async def image_cancel(job_id: str):
    """Cancel a ComfyUI image job after verifying prompt ownership."""
    import httpx

    from gateway.image_gen import (
        CancellationConflictError,
        CancellationUnsupportedError,
        cancel,
    )
    from gateway.image_jobs import IllegalTransitionError, JobNotFoundError

    try:
        return await cancel(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CancellationUnsupportedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CancellationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"ComfyUI cancellation failed: {exc}"
        ) from exc


@router.get("/image/view/{filename:path}")
async def image_view(filename: str):
    """Proxy an output image from ComfyUI (works with both local and Colab tunnel URLs)."""
    import httpx
    from fastapi.responses import FileResponse, Response

    from mcp.imagen.config import settings

    # Draw Things and the converged ComfyUI path persist artifacts in Kitty's
    # local image store.  Serve only files below that configured directory;
    # all other names retain the legacy ComfyUI proxy behavior.
    candidate = Path(filename)
    if not candidate.is_absolute():
        candidate = settings.output_dir / candidate
    try:
        candidate = candidate.resolve()
        output_root = settings.output_dir.resolve()
        candidate.relative_to(output_root)
    except ValueError:
        candidate = Path()
    if candidate.is_file():
        return FileResponse(candidate)

    from gateway.image_gen import COMFY_URL

    url = f"{COMFY_URL}/view?filename={filename}&subfolder=&type=output"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url)
        if r.status_code != 200:
            raise HTTPException(status_code=404, detail="Image not found in ComfyUI")
        ct = r.headers.get("content-type", "image/png")
        return Response(content=r.content, media_type=ct)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach ComfyUI: {e}")


@router.get("/image/history")
async def image_history(limit: int = 20):
    from gateway.image_gen import get_history

    return {"images": get_history(limit=limit)}


# --- Image Studio V1: Characters ---


class CharacterCreate(BaseModel):
    name: str
    description: Optional[str] = None
    preferred_recipe: Optional[str] = None
    identity_preset: str = "balanced"


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    preferred_recipe: Optional[str] = None
    identity_preset: Optional[str] = None


class RecipeUpdate(BaseModel):
    available: bool


class StudioGenerateRequest(BaseModel):
    prompt: str
    quality: str = "quality"
    identity: str = "balanced"
    character_id: Optional[str] = None
    recipe_id: Optional[str] = None
    negative_prompt: Optional[str] = None
    plan_id: Optional[str] = None
    session_id: Optional[str] = None


class PlanPreviewRequest(BaseModel):
    """Preview a generation plan before committing to generation.

    *content_lane*/*consent_basis*/*adult_confirmed* are the trusted policy
    declaration (ADR 0040 #8) persisted with the approved plan. They default
    to the safe lane, and private_adult cannot be inferred from prompt text.
    """
    prompt: str
    character_id: Optional[str] = None
    recipe_id: Optional[str] = None
    guidance_tags: Optional[List[str]] = None
    session_id: Optional[str] = None
    content_lane: Optional[str] = None
    consent_basis: Optional[str] = None
    adult_confirmed: bool = False


@router.get("/studio/characters")
async def studio_list_characters():
    from gateway.image_characters import list_characters

    chars = list_characters()
    return {"characters": [c.to_dict() for c in chars]}


@router.post("/studio/characters")
async def studio_create_character(req: CharacterCreate):
    from gateway.image_characters import CharacterError, create_character
    try:
        char = create_character(
            name=req.name,
            description=req.description,
            preferred_recipe=req.preferred_recipe,
            identity_preset=req.identity_preset,
        )
        return char.to_dict()
    except CharacterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/studio/characters/{character_id}")
async def studio_get_character(character_id: str):
    from gateway.image_characters import CharacterNotFoundError, get_character, list_character_refs
    try:
        char = get_character(character_id)
        refs = list_character_refs(character_id)
        result = char.to_dict()
        result["references"] = [r.to_dict() for r in refs]
        return result
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/studio/characters/{character_id}")
async def studio_update_character(character_id: str, req: CharacterUpdate):
    from gateway.image_characters import CharacterError, CharacterNotFoundError, update_character
    try:
        char = update_character(
            character_id,
            name=req.name,
            description=req.description,
            preferred_recipe=req.preferred_recipe,
            identity_preset=req.identity_preset,
        )
        return char.to_dict()
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CharacterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/studio/characters/{character_id}")
async def studio_delete_character(character_id: str):
    from gateway.image_characters import CharacterNotFoundError, soft_delete_character
    try:
        char = soft_delete_character(character_id)
        return char.to_dict()
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/studio/characters/{character_id}/references")
async def studio_add_character_ref(character_id: str, file: UploadFile):
    from gateway.image_characters import CharacterError, CharacterNotFoundError, add_character_ref
    from gateway.image_quality import check_reference_image

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file too large (max 20 MB)")
    try:
        quality = check_reference_image(data)
        quality_notes = quality.summary()
        ref = add_character_ref(
            character_id, data,
            original_name=file.filename,
            media_type=file.content_type,
            quality_notes=quality_notes,
        )
        result = ref.to_dict()
        result["quality"] = {
            "has_blockers": quality.has_blockers,
            "has_warnings": quality.has_warnings,
            "is_perfect": quality.is_perfect,
            "summary": quality.summary(),
            "advice": quality.advice(),
            "dimensions": f"{quality.width}×{quality.height}" if quality.width else None,
        }
        return result
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CharacterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/studio/characters/{character_id}/quality")
async def studio_character_quality(character_id: str):
    from gateway.image_characters import CharacterNotFoundError, get_character, list_character_refs
    from gateway.image_quality import check_reference_image

    try:
        get_character(character_id)
        refs = list_character_refs(character_id)
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if not refs:
        return {"quality": None, "message": "no reference images uploaded"}

    results = []
    for ref in refs:
        try:
            path = Path(ref.storage_path)
            if path.exists():
                data = path.read_bytes()
                qr = check_reference_image(data)
                results.append({
                    "ref_id": ref.ref_id,
                    "is_primary": ref.is_primary,
                    "original_name": ref.original_name,
                    "has_blockers": qr.has_blockers,
                    "has_warnings": qr.has_warnings,
                    "is_perfect": qr.is_perfect,
                    "summary": qr.summary(),
                    "advice": qr.advice(),
                    "dimensions": f"{qr.width}×{qr.height}" if qr.width else None,
                })
        except Exception:
            results.append({
                "ref_id": ref.ref_id,
                "is_primary": ref.is_primary,
                "original_name": ref.original_name,
                "has_blockers": True,
                "has_warnings": False,
                "is_perfect": False,
                "summary": "could not read reference file",
                "advice": ["the reference file may be missing or corrupted"],
                "dimensions": None,
            })

    return {"quality": results}


@router.delete("/studio/characters/{character_id}/references/{ref_id}")
async def studio_delete_character_ref(character_id: str, ref_id: str):
    from gateway.image_characters import (
        CharacterError,
        CharacterNotFoundError,
        delete_character_ref,
    )
    try:
        delete_character_ref(character_id, ref_id)
        return {"deleted": True}
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CharacterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --- Image Studio V1: Recipes ---

@router.get("/studio/recipes")
async def studio_list_recipes(available_only: bool = False):
    from gateway.image_recipes import list_recipes
    recipes = list_recipes(available_only=available_only)
    return {"recipes": [r.to_dict() for r in recipes]}


@router.patch("/studio/recipes/{recipe_id}")
async def studio_update_recipe(recipe_id: str, req: RecipeUpdate):
    from gateway.image_recipes import RecipeError, set_recipe_available
    try:
        recipe = set_recipe_available(recipe_id, req.available)
        return recipe.to_dict()
    except RecipeError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# --- Image Studio V1: Plan preview ---


@router.post("/studio/plan")
async def studio_plan(req: PlanPreviewRequest):
    """Preview a validated generation plan before committing.

    Returns the resolved plan with provenance so the user can inspect
    references and guidance before calling ``/studio/generate``.

    When *session_id* is supplied, the plan is persisted under a stable
    ``plan_id`` owned by that session, so ``/studio/generate`` can later
    dispatch from the approved plan instead of mutable form state.
    """
    from gateway.image_plan import ImagePlanError, build_image_plan

    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")

    try:
        plan = build_image_plan(
            req.prompt,
            character_id=req.character_id,
            recipe_id=req.recipe_id,
            guidance_tags=req.guidance_tags,
            content_lane=req.content_lane,
            consent_basis=req.consent_basis,
            adult_confirmed=req.adult_confirmed,
        )
    except ImagePlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    from gateway.image_guidance import available_guidance_tags

    result = plan.to_dict()
    result["available_guidance_tags"] = available_guidance_tags()

    if req.session_id:
        from gateway.image_plans import PlanStoreError, persist_plan

        try:
            stored = persist_plan(req.session_id, plan)
        except PlanStoreError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        result["plan_id"] = stored.plan_id

    return result


# --- Image Studio: conversational sessions (issue #336, slice A5) ---


class SessionCreateRequest(BaseModel):
    title: Optional[str] = None
    project_id: Optional[int] = None
    character_id: Optional[str] = None
    reference_ids: Optional[List[str]] = None
    protected_traits: Optional[List[str]] = None


class SessionUpdateRequest(SessionCreateRequest):
    """PATCH body for an active session. Only supplied fields change."""

    clear_character: Optional[bool] = False


class AgentTurnRequest(BaseModel):
    """One natural-language turn for the bounded image-specialist controller."""

    session_id: str
    request: str


class AnchorRequest(BaseModel):
    job_id: str


def _session_payload(session) -> dict:
    """A session plus the turns and jobs a resumed conversation replays."""
    from gateway import image_sessions

    turns = image_sessions.list_turns(session.session_id)
    jobs = image_sessions.list_session_jobs(session.session_id)
    payload = session.to_dict()
    payload["turns"] = [t.to_dict() for t in turns]
    payload["jobs"] = [j.to_dict() for j in jobs]
    return payload


@router.post("/studio/sessions")
async def studio_create_session(req: SessionCreateRequest):
    from gateway.image_sessions import ImageSessionError, create_session

    try:
        session = create_session(
            title=req.title,
            project_id=req.project_id,
            character_id=req.character_id,
            reference_ids=req.reference_ids,
            protected_traits=req.protected_traits,
        )
    except ImageSessionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _session_payload(session)


@router.get("/studio/sessions")
async def studio_list_sessions(limit: int = 50):
    from gateway.image_sessions import list_sessions

    return {"sessions": [s.to_dict() for s in list_sessions(limit=limit)]}


@router.get("/studio/sessions/{session_id}")
async def studio_get_session(session_id: str):
    """Resume: everything needed to rebuild the conversation after a restart."""
    from gateway.image_sessions import SessionNotFoundError, require_session

    try:
        session = require_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _session_payload(session)


@router.patch("/studio/sessions/{session_id}")
async def studio_update_session(session_id: str, req: SessionUpdateRequest):
    """Bind or refresh a character/references on an active session.

    Only supplied fields change; the agent's session registry reads these on
    the next turn, so attaching a character here is how a reference image is
    wired into an already-open conversation.
    """
    from gateway.image_sessions import (
        ImageSessionError,
        SessionNotFoundError,
        update_session,
    )

    try:
        session = update_session(
            session_id,
            title=req.title,
            character_id=req.character_id,
            reference_ids=req.reference_ids,
            protected_traits=req.protected_traits,
            clear_character=req.clear_character,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ImageSessionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _session_payload(session)


@router.post("/studio/sessions/{session_id}/anchor")
async def studio_set_anchor(session_id: str, req: AnchorRequest):
    """"Use this" — select a rendered result as the base for follow-up edits."""
    from gateway.image_sessions import (
        AnchorError,
        ImageSessionError,
        SessionNotFoundError,
        set_anchor,
    )

    try:
        session = set_anchor(session_id, req.job_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AnchorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ImageSessionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _session_payload(session)


@router.delete("/studio/sessions/{session_id}")
async def studio_end_session(session_id: str):
    from gateway.image_sessions import (
        ImageSessionError,
        SessionNotFoundError,
        end_session,
    )

    try:
        session = end_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ImageSessionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return session.to_dict()


@router.post("/studio/agent")
async def studio_agent_turn(req: AgentTurnRequest):
    """Decide what one natural request means, without dispatching it.

    The controller returns a validated decision plus, for a render, the
    ``plan_id`` the caller passes to ``/studio/generate``. Splitting decision
    from dispatch is what lets the UI show what will change before any GPU
    starts billing.
    """
    from gateway.image_agent import (
        AgentLoopExhaustedError,
        AgentProtocolError,
        BudgetRefusedError,
        CapabilityError,
        ImageAgentError,
        UnknownReferenceError,
        UnsupportedOperationError,
        decide,
    )
    from gateway.image_sessions import SessionNotFoundError

    try:
        decision = decide(req.session_id, req.request)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except BudgetRefusedError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except CapabilityError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except (UnknownReferenceError, UnsupportedOperationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (AgentProtocolError, AgentLoopExhaustedError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ImageAgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return decision.to_dict()


# --- Image Studio V1: Generate (Auto-routed) ---

@router.post("/studio/generate")
async def studio_generate(req: StudioGenerateRequest):
    from gateway import image_recipes
    from gateway.image_runner import (
        ImageRunnerError,
        estimated_cost_usd,
        paid_engine_available,
        read_anchor_artifact,
        run,
        run_edit,
    )

    # Dispatch from the stored approved plan when plan_id is supplied. The
    # plan owns the render inputs *and* the operation — request form fields
    # for prompt, character, recipe, and operation are ignored so a
    # post-approval edit cannot change what renders, and an approved edit
    # cannot be silently downgraded to a fresh generation.
    stored = None
    operation = "txt2img"
    approved_edit_anchor: str | None = None
    character_ref_path: str | None = None
    if req.plan_id:
        from gateway.image_plans import (
            PlanNotApprovedError,
            PlanNotFoundError,
            PlanSessionMismatchError,
            PlanStoreError,
            require_approved_plan,
        )

        try:
            stored = require_approved_plan(req.plan_id, req.session_id or "")
        except PlanNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except (PlanSessionMismatchError, PlanNotApprovedError, PlanStoreError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        operation = stored.operation
        prompt = stored.refined_prompt
        has_character = bool(stored.character_id)
        character_count = 1 if has_character else 0
        preferred_recipe = stored.recipe_id
        character_id = stored.character_id
        character_ref_path = getattr(stored, "character_ref_path", None)
        guidance_tags = stored.guidance_tags

        if operation == "img2img":
            # Fail loud before any spend or dispatch: a missing, unknown, or
            # non-owned anchor means this session cannot honestly edit that
            # image. Ownership reuses image_sessions' existing job-attachment
            # record rather than inventing a second ownership model.
            anchor_job_id = stored.anchor_job_id
            if not anchor_job_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"plan {stored.plan_id!r} is operation='img2img' but has "
                        "no anchor_job_id"
                    ),
                )
            from gateway import image_jobs as _image_jobs
            from gateway import image_sessions as _image_sessions

            if _image_jobs.get_job(anchor_job_id) is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"anchor job {anchor_job_id!r} no longer exists",
                )
            owned_job_ids = {
                j.job_id
                for j in _image_sessions.list_session_jobs(stored.session_id)
            }
            if anchor_job_id not in owned_job_ids:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"anchor job {anchor_job_id!r} does not belong to "
                        f"session {stored.session_id!r}; refusing to edit an "
                        "image this session does not own"
                    ),
                )
            approved_edit_anchor = anchor_job_id

        # Content-lane contract (ADR 0040 #8): dispatch from the STORED plan's
        # policy, never from a request body. The approved plan is the only
        # trusted source of content_lane/consent_basis/adult_confirmed.
        content_lane = stored.content_lane
        consent_basis = stored.consent_basis
        adult_confirmed = stored.adult_confirmed
    else:
        if not req.prompt or not req.prompt.strip():
            raise HTTPException(status_code=400, detail="prompt must not be empty")

        prompt = req.prompt
        has_character = bool(req.character_id)
        character_count = 1 if has_character else 0
        preferred_recipe = req.recipe_id
        character_id = req.character_id
        guidance_tags = None
        if character_id:
            from gateway.image_characters import list_character_refs

            character_refs = list_character_refs(character_id)
            primary = next(
                (ref for ref in character_refs if ref.is_primary),
                character_refs[0] if character_refs else None,
            )
            character_ref_path = primary.storage_path if primary is not None else None

        # A plan-less /studio/generate call carries no trusted policy metadata:
        # it is safe lane, and a prompt can never promote itself to private.
        content_lane = "safe"
        consent_basis = None
        adult_confirmed = False

    # Resolve session context before routing, provider preflight, or spend. A
    # supplied session is authoritative for Project scope; an unknown session
    # must never be allowed to render first and fail only during attachment.
    dispatch_session_id = req.session_id or (stored.session_id if stored else None)
    session_context = None
    project_id: int | None = None
    if dispatch_session_id:
        from gateway.image_sessions import SessionNotFoundError, require_session

        try:
            session_context = require_session(dispatch_session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        project_id = session_context.project_id

    try:
        decision = image_recipes.auto_route(
            has_character=has_character,
            character_count=character_count,
            quality_tier=req.quality,
            identity_mode=req.identity,
            operation=operation,
            preferred_recipe=preferred_recipe,
        )
    except image_recipes.RecipeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    recipe = decision.recipe

    # auto_route does not filter on operation, so the img2img capability has
    # to be asserted here or an approved edit would route to a text-only
    # recipe (mirrors image_agent._route_recipe's same assertion).
    if operation == "img2img" and (recipe is None or not recipe.supports_img2img):
        raise HTTPException(
            status_code=503,
            detail=(
                f"recipe {decision.recipe_id!r} does not support img2img; "
                "no available recipe can perform a reference-conditioned edit"
            ),
        )

    # Content-lane seam (ADR 0040 #8): select the execution target from the
    # stored plan's policy BEFORE any cost estimate or availability preflight.
    # Private work must pick a private executor first so a hosted availability
    # gate or hosted spend reservation can never run for private work — even if
    # the recipe metadata names a hosted provider.
    from gateway.image_policy import (
        ImagePolicyError,
        validate_image_execution_policy,
    )

    if content_lane == "private_adult":
        # v1's only Kitty-controlled private executor is the worker edit lane
        # (run_edit → kitty_worker). A private text-to-image plan has no
        # private executor yet, so it is refused here — never downgraded to a
        # hosted engine.
        if operation != "img2img":
            raise HTTPException(
                status_code=400,
                detail=(
                    "content_lane='private_adult' has no private text-to-image "
                    "executor in v1; only the worker edit lane (img2img) is "
                    "private, refusing to route private work to a hosted provider"
                ),
            )
        execution_target = "kitty_worker"
    else:
        execution_target = recipe.provider if recipe else "comfyui"

    try:
        validate_image_execution_policy(
            content_lane, consent_basis, adult_confirmed, execution_target
        )
    except ImagePolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    engine = execution_target

    # Hosted FLUX.2 (BFL Direct) selection (IL-03/IL-04). For provider=="flux2"
    # the recipe names an explicit flux2 execution target; the exact model,
    # estimate, availability, and dispatch must all agree on that one target.
    flux2_target = None
    compiled_request = None
    reference_bytes: tuple[bytes, ...] = ()
    render_width = 1024
    render_height = 1024

    if engine == "flux2":
        from gateway.flux2_compiler import (
            CompiledReference,
            Flux2CompilerError,
            compile_flux2_request,
        )
        from gateway.flux2_targets import (
            Flux2TargetError,
            resolve_flux2_target,
        )

        if not recipe or not recipe.execution_target:
            raise HTTPException(
                status_code=400,
                detail="recipe for the hosted FLUX.2 lane names no execution target",
            )
        try:
            flux2_target = resolve_flux2_target(recipe.execution_target)
        except Flux2TargetError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        if recipe.default_width and recipe.default_width > 0:
            render_width = recipe.default_width
        if recipe.default_height and recipe.default_height > 0:
            render_height = recipe.default_height

        refs: list[CompiledReference] = []
        ref_blobs: list[bytes] = []
        if operation == "img2img":
            if approved_edit_anchor is None:
                raise HTTPException(
                    status_code=500,
                    detail="approved img2img plan lost its validated anchor before dispatch",
                )
            try:
                anchor_bytes, anchor_name = read_anchor_artifact(
                    approved_edit_anchor
                )
            except ImageRunnerError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            refs.append(
                CompiledReference(
                    reference_id=approved_edit_anchor,
                    role="anchor",
                    order=1,
                    name=anchor_name,
                )
            )
            ref_blobs.append(anchor_bytes)
        for prov in (stored.references if stored else []):
            path = prov.get("path") if isinstance(prov, dict) else getattr(prov, "path", None)
            if not path or not Path(path).is_file():
                continue
            order = len(refs) + 1
            refs.append(
                CompiledReference(
                    reference_id=str(path),
                    role="identity",
                    order=order,
                    name=(prov.get("name") if isinstance(prov, dict) else getattr(prov, "name", None)),
                )
            )
            ref_blobs.append(Path(path).read_bytes())
        reference_bytes = tuple(ref_blobs)

        protected = []
        requested = []
        if session_context is not None:
            protected = list(session_context.protected_traits or [])
            requested = list(session_context.requested_changes or [])
        try:
            compiled_request = compile_flux2_request(
                prompt,
                references=refs,
                operation=operation,
                # StudioGenerateRequest intentionally has no user-authored seed.
                # Seeds become approved batch/VariationStrategy state in IL-08;
                # do not invent mutable request-side reproducibility here.
                seed=None,
                width=render_width,
                height=render_height,
                quality_tier=req.quality,
                protected_traits=protected,
                requested_changes=requested,
                negative_prompt=req.negative_prompt,
            )
        except Flux2CompilerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            estimated_cost = flux2_target.estimate_cost_usd(
                render_width, render_height, operation
            )
        except (Flux2TargetError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        try:
            estimated_cost = estimated_cost_usd(engine)
        except ImageRunnerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    paid_attempt_reserved = False
    if estimated_cost > 0:
        if not req.session_id:
            raise HTTPException(
                status_code=400,
                detail="paid image generation requires a session so spend can be budgeted",
            )
        available, reason = paid_engine_available(engine)
        if not available:
            raise HTTPException(status_code=400, detail=reason)

        from gateway.image_agent import AgentBudget
        from gateway.image_sessions import (
            ImageSessionError,
            SessionBudgetExceededError,
            reserve_attempt,
        )

        budget = AgentBudget()
        try:
            reserve_attempt(
                req.session_id,
                cost_usd=estimated_cost,
                max_attempts=budget.max_attempts,
                max_spend_usd=budget.max_spend_usd,
            )
            paid_attempt_reserved = True
        except SessionBudgetExceededError as exc:
            raise HTTPException(status_code=429, detail=str(exc))
        except ImageSessionError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    try:
        if engine == "flux2":
            result = await run(
                engine,
                prompt,
                recipe=recipe,
                character_id=character_id,
                character_ref_path=character_ref_path,
                negative_prompt=req.negative_prompt,
                guidance_tags=guidance_tags,
                content_lane=content_lane,
                consent_basis=consent_basis,
                adult_confirmed=adult_confirmed,
                flux2_target=flux2_target,
                compiled_request=compiled_request,
                reference_bytes=reference_bytes,
                project_id=project_id,
            )
        elif operation == "img2img":
            if approved_edit_anchor is None:
                raise HTTPException(
                    status_code=500,
                    detail="approved img2img plan lost its validated anchor before dispatch",
                )
            result = await run_edit(
                prompt,
                anchor_job_id=approved_edit_anchor,
                recipe=recipe,
                negative_prompt=req.negative_prompt,
                content_lane=content_lane,
                consent_basis=consent_basis,
                adult_confirmed=adult_confirmed,
                project_id=project_id,
            )
        else:
            result = await run(
                engine,
                prompt,
                recipe=recipe,
                character_id=character_id,
                character_ref_path=character_ref_path,
                negative_prompt=req.negative_prompt,
                guidance_tags=guidance_tags,
                content_lane=content_lane,
                consent_basis=consent_basis,
                adult_confirmed=adult_confirmed,
                project_id=project_id,
            )
        # Bind the render back to its conversation so a restart can replay it
        # and "use this" has something to anchor on. A failure to bind is
        # surfaced, not swallowed: a job the session cannot see is a job the
        # user cannot select.
        if req.session_id:
            from gateway.image_sessions import (
                ImageSessionError,
                attach_job,
                reconcile_reserved_attempt_cost,
                record_attempt,
            )

            try:
                if paid_attempt_reserved and result.cost_usd is not None:
                    reconcile_reserved_attempt_cost(
                        req.session_id,
                        reserved_cost_usd=estimated_cost,
                        actual_cost_usd=result.cost_usd,
                    )
                attach_job(req.session_id, result.job_id)
                if not paid_attempt_reserved:
                    record_attempt(req.session_id)
            except ImageSessionError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        return {
            "job_id": result.job_id,
            "filename": result.filename,
            "actual_cost_usd": result.cost_usd,
            "recipe": result.recipe,
            "routing_reason": decision.reason,
            "plan_id": req.plan_id,
            "session_id": req.session_id,
        }
    except ImageRunnerError as e:
        status = 503 if "not running" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc))
    except HTTPException:
        # A status this handler already chose must reach the client intact.
        # Without this the generic clause below rewraps it as a 500 whose body
        # is the text of the original error, hiding the real cause.
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
