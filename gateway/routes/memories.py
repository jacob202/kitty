"""Long-term memory list and forget lifecycle."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from gateway.errors import StorageNotFound

router = APIRouter(tags=["memories"])


def _explicit_api_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "text": row["text"],
        "metadata": {
            "namespace": row.get("namespace"),
            "memory_key": row.get("memory_key"),
            "source_kind": row.get("source_kind"),
            "source_ref": row.get("source_ref"),
            "status": row.get("status"),
            "explicit": True,
        },
    }


@router.get("/memories")
async def list_memories(namespace: Optional[str] = None, limit: int = 50) -> dict:
    """List explicit memory first; semantic-memory outages are reported, not hidden."""
    from gateway import explicit_memory, memory

    bounded = 1000 if limit == 0 else max(1, min(limit, 1000))
    explicit_rows = explicit_memory.list_memories(namespace=namespace, limit=bounded)
    memories = [_explicit_api_row(row) for row in explicit_rows]
    warnings: list[str] = []

    remaining = 0 if limit != 0 and len(memories) >= bounded else (
        0 if limit == 0 else bounded - len(memories)
    )
    semantic_limit = 0 if limit == 0 else remaining
    if limit == 0 or semantic_limit > 0:
        try:
            memories.extend(
                memory.list_memories(namespace=namespace, limit=semantic_limit)
            )
        except memory.MemoryError as exc:
            warnings.append(f"semantic_memory: {exc}")

    if limit != 0:
        memories = memories[:bounded]
    return {"memories": memories, "warnings": warnings}


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str) -> dict:
    """Forget governed explicit memory, or delete a legacy semantic memory."""
    if memory_id.startswith("exp_"):
        from gateway.explicit_memory import forget

        deleted = forget(memory_id)
    else:
        from gateway.memory import delete_memory as delete_semantic_memory

        deleted = delete_semantic_memory(memory_id)

    if not deleted:
        raise StorageNotFound(
            f"memory {memory_id!r} was not found",
            details={"memory_id": memory_id},
        )
    return {"deleted": True, "memory_id": memory_id}
