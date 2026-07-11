"""Long-term memory list and delete."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["memories"])


@router.get("/memories")
async def list_memories(namespace: Optional[str] = None, limit: int = 50):
    """List stored memories. Optional namespace filter: facts|patterns."""
    from gateway.memory import MemoryError, list_memories

    try:
        return {"memories": list_memories(namespace=namespace, limit=limit)}
    except MemoryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a specific memory by ID."""
    from gateway.memory import MemoryError, delete_memory

    try:
        success = delete_memory(memory_id)
    except MemoryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"deleted": success, "memory_id": memory_id}
