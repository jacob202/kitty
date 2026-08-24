"""Long-term memory list and forget lifecycle."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from gateway.errors import StorageNotFound

router = APIRouter(tags=["memories"])


class CorrectMemoryRequest(BaseModel):
    text: str = Field(min_length=1)
    memory_key: Optional[str] = None


class PinMemoryRequest(BaseModel):
    pinned: bool


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


@router.get("/memories/{memory_id}/explain")
async def explain_memory(memory_id: str) -> dict:
    """Explain why a governed memory is remembered: source, authority, state, supersession."""
    from gateway.errors import StorageNotFound as NotFound
    from gateway.memory_explain import explain

    if not memory_id.startswith("exp_"):
        raise NotFound(
            f"memory {memory_id!r} was not found",
            details={"memory_id": memory_id},
        )
    from gateway.explicit_memory import ExplicitMemoryNotFound

    try:
        explanation = explain(memory_id)
    except ExplicitMemoryNotFound as exc:
        raise NotFound(str(exc), details={"memory_id": memory_id}) from exc
    return {"memory": explanation}


@router.post("/memories/{memory_id}/correct")
async def correct_memory(memory_id: str, body: CorrectMemoryRequest) -> dict:
    """Correct a remembered fact through the governed correction/supersession path."""
    from gateway.explicit_memory import ExplicitMemoryNotFound, remember
    from gateway.memory_explain import explain

    try:
        corrected = remember(
            body.text,
            memory_key=body.memory_key,
            supersedes_id=memory_id,
            source_kind="user_correction",
        )
    except ExplicitMemoryNotFound as exc:
        raise StorageNotFound(
            f"memory {memory_id!r} was not found",
            details={"memory_id": memory_id},
        ) from exc
    return {"memory": explain(corrected["id"])}


@router.post("/memories/{memory_id}/pin")
async def pin_memory(memory_id: str, body: PinMemoryRequest) -> dict:
    """Pin or unpin a governed memory so it stays at the top of future recall."""
    from gateway.explicit_memory import set_pinned

    updated = set_pinned(memory_id, pinned=body.pinned)
    if not updated:
        raise StorageNotFound(
            f"memory {memory_id!r} was not found",
            details={"memory_id": memory_id},
        )
    return {"memory_id": memory_id, "pinned": body.pinned}
