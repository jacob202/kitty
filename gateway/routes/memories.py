"""Long-term memory list and delete."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from gateway.errors import StorageNotFound

router = APIRouter(tags=["memories"])


@router.get("/memories")
async def list_memories(namespace: Optional[str] = None, limit: int = 50) -> dict:
    """List stored memories. Optional namespace filter: facts|patterns."""
    from gateway.memory import list_memories

    return {"memories": list_memories(namespace=namespace, limit=limit)}


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str) -> dict:
    """Delete a specific memory by ID."""
    from gateway.memory import delete_memory

    if not delete_memory(memory_id):
        raise StorageNotFound(
            f"memory {memory_id!r} was not found",
            details={"memory_id": memory_id},
        )
    return {"deleted": True, "memory_id": memory_id}
