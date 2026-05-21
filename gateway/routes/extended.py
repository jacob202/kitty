"""Skills, agents, tasks, notifications, and image generation."""

from __future__ import annotations

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
    from gateway.notify import send, is_configured

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
    from gateway.todo_store import update

    return {"todos": update(payload.items)}


@router.get("/todos")
async def todos_get():
    from gateway.todo_store import get

    return {"todos": get()}


@router.post("/todos/clear")
async def todos_clear():
    from gateway.todo_store import clear

    clear()
    return {"todos": []}


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
    from gateway.agent_runner import get_status, get_output

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


@router.get("/image/status")
async def image_status():
    from gateway.image_gen import is_available

    available = await is_available()
    return {"available": available, "backend": "comfyui"}


@router.post("/image/generate")
async def image_generate(req: ImageGenRequest):
    from gateway.image_gen import generate, is_available

    if not await is_available():
        raise HTTPException(status_code=503, detail="ComfyUI is not running")
    try:
        result = await generate(req.prompt)
        return result
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))