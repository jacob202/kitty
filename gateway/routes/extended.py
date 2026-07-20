"""Skills, agents, tasks, notifications, and image generation."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
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

    engines = [
        {"name": "comfyui", "label": "ComfyUI", "available": comfy_available},
        {"name": "drawthings", "label": "Draw Things", "available": drawthings_available},
    ]
    return {"available": comfy_available or drawthings_available, "backend": "comfyui", "engines": engines}


@router.post("/image/generate")
async def image_generate(req: ImageGenRequest):
    import asyncio

    from gateway.image_gen import generate, is_available

    engine = req.engine.strip().lower()
    if engine not in {"comfyui", "drawthings"}:
        raise HTTPException(status_code=422, detail="engine must be 'comfyui' or 'drawthings'")

    if engine == "drawthings":
        from gateway import image_jobs
        from mcp.imagen.engines import get
        from mcp.imagen.io import save_image

        drawthings = get("drawthings")
        probe = getattr(getattr(drawthings, "_adapter", None), "is_available", None)
        if probe is not None and not await asyncio.to_thread(probe):
            raise HTTPException(status_code=503, detail="Draw Things is not running")
        job = image_jobs.create_job(
            provider="drawthings",
            operation="variation" if req.parent_id else "txt2img",
            prompt=req.prompt,
            parent_id=req.parent_id,
            model_id=getattr(drawthings, "model_name", None),
        )
        try:
            image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.SUBMITTED)
            image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.RUNNING)
            data = await drawthings.generate_async(req.prompt)
            path = await asyncio.to_thread(save_image, data, prefix="drawthings")
            image_jobs.update_job(job.job_id, output_path=str(path))
            image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.SUCCEEDED)
        except Exception as exc:
            image_jobs.update_job(job.job_id, normalized_error=str(exc)[:500])
            image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.FAILED)
            raise
        return {"filename": str(path), "job_id": job.job_id, "engine": engine}

    if not await is_available():
        raise HTTPException(status_code=503, detail="ComfyUI is not running")
    try:
        result = await generate(req.prompt, parent_id=req.parent_id)
        result["engine"] = engine
        return result
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/image/{job_id}/cancel")
async def image_cancel(job_id: str):
    """Stop the ComfyUI worker for a non-terminal durable image job."""
    import httpx

    from gateway.image_gen import cancel
    from gateway.image_jobs import IllegalTransitionError, JobNotFoundError

    try:
        return await cancel(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"ComfyUI interruption failed: {exc}"
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
