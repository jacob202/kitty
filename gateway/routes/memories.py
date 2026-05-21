"""Long-term memory list and delete."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

router = APIRouter(tags=["memories"])


@router.get("/memories")
async def list_memories(namespace: Optional[str] = None, limit: int = 50):
    """List stored memories. Optional namespace filter: facts|patterns."""
    from gateway.memory import list_memories

    return {"memories": list_memories(namespace=namespace, limit=limit)}


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a specific memory by ID."""
    from gateway.memory import delete_memory

    success = delete_memory(memory_id)
    return {"deleted": success, "memory_id": memory_id}
