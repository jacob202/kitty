"""Todo routes.

Split from the former routes/extended.py on 2026-09-16 so each route module
owns one domain (architecture claim: "Routes should remain thin").
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["todos"])


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


class TodoProgressRequest(BaseModel):
    note: str = Field(default="", max_length=2000)


class TodoProjectRequest(BaseModel):
    project_id: Optional[int] = None


@router.post("/todos/{todo_id}/progress")
async def todos_set_progress(todo_id: int, payload: TodoProgressRequest):
    """Record where the user stopped. A different statement from completing it."""
    from gateway.storage_router import set_todo_progress

    todo = set_todo_progress(todo_id, payload.note)
    if todo is None:
        raise HTTPException(
            status_code=404,
            detail="That to-do is already finished or no longer exists.",
        )
    return {"todo": todo}


@router.post("/todos/{todo_id}/project")
async def todos_set_project(todo_id: int, payload: TodoProjectRequest):
    from gateway.storage_router import set_todo_project

    todo = set_todo_project(todo_id, payload.project_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="That to-do no longer exists.")
    return {"todo": todo}


@router.delete("/todos/{todo_id}")
async def todos_delete(todo_id: int):
    from gateway.storage_router import delete_todo

    return {"deleted": delete_todo(todo_id), "id": todo_id}
