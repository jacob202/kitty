"""Kitty-chat session persistence — backed by kitty.db via chats_store.

Phase C C3: the route reads and writes through chats_store instead of
data/kitty/chats.json. The wire contract (paths, request/response
shapes) is unchanged.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from gateway import artifact_store, chat_lifecycle, chats_store

router = APIRouter(tags=["chats"])


@router.get("/chats")
async def get_chats():
    """Return all saved chat sessions."""
    return {"chats": chats_store.list_chats()}


@router.post("/chats")
async def upsert_chat(request: Request):
    """Create or update a chat session by id."""
    chat = await request.json()
    if not chat.get("id"):
        raise HTTPException(status_code=400, detail="id required")
    chats_store.upsert_chat(chat)
    return {"ok": True}


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str):
    """Delete a chat session."""
    chats_store.delete_chat(chat_id)
    return {"ok": True}


@router.patch("/chats/{chat_id}/objective")
async def patch_chat_objective(chat_id: str, request: Request):
    """Set or clear a chat's per-thread objective."""
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON body: {exc}") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be an object")
    if "objective" not in body:
        raise HTTPException(status_code=400, detail="objective field required")
    objective = body["objective"]
    if objective is not None:
        if not isinstance(objective, str):
            raise HTTPException(
                status_code=400,
                detail="objective must be a string or null",
            )
        if len(objective) > 500:
            raise HTTPException(
                status_code=400,
                detail=f"objective must be at most 500 characters, got {len(objective)}",
            )
    try:
        updated = chats_store.patch_objective(chat_id, objective)
    except chats_store.ChatNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return updated


@router.get("/chats/{chat_id}/lifecycle")
def get_chat_lifecycle(chat_id: str) -> dict:
    try:
        return chat_lifecycle.list_conversation(chat_id)
    except chat_lifecycle.ChatLifecycleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _recover_messages(conversation_id: str) -> list[dict]:
    """Rebuild an ordered UI message list from the durable lifecycle ledger.

    Falls back gracefully: a missing conversation (no ledger entry yet) yields
    an empty list so the caller can keep using the legacy chat blob.
    """
    try:
        state = chat_lifecycle.list_conversation(conversation_id)
    except chat_lifecycle.ChatLifecycleError:
        return []

    messages: list[dict] = []
    for turn in state.get("turns", []):
        if turn is None:
            continue
        attempt_model = None
        for attempt in turn.get("attempts", []):
            if attempt.get("resolved_model"):
                attempt_model = attempt["resolved_model"]
                break
        turn_status = turn.get("status")
        for msg in turn.get("messages", []):
            raw_artifacts = msg.get("artifact_ids") or "[]"
            try:
                artifact_ids = json.loads(raw_artifacts) if isinstance(raw_artifacts, str) else raw_artifacts
            except (TypeError, json.JSONDecodeError):
                artifact_ids = []
            attachments = []
            for art_id in artifact_ids:
                artifact = artifact_store.get_artifact(art_id)
                if artifact is None:
                    continue
                attachments.append(
                    {
                        "id": artifact["id"],
                        "display_name": artifact["display_name"],
                        "media_type": artifact["media_type"],
                        "size": artifact["size_bytes"],
                    }
                )
            raw_memory = msg.get("memory_items")
            try:
                memory_items = json.loads(raw_memory) if isinstance(raw_memory, str) else []
            except json.JSONDecodeError:
                memory_items = []
            if not (
                isinstance(memory_items, list)
                and all(isinstance(item, str) for item in memory_items)
            ):
                memory_items = []
            messages.append(
                {
                    "id": msg["id"],
                    "role": msg["role"],
                    "content": msg["content"],
                    "created_at": msg["created_at"],
                    "model": attempt_model if msg["role"] == "assistant" else None,
                    "status": turn_status,
                    "attachments": attachments,
                    "memory_items": memory_items,
                }
            )
    return messages


@router.get("/chats/{chat_id}/messages")
def get_chat_messages(chat_id: str) -> dict:
    """Recover ordered chat history from the normalized lifecycle ledger.

    The legacy chat blob stays the compatibility record; this endpoint is the
    honest durable read surface for restart/recovery when the in-memory UI state
    is gone but the ledger survived.
    """
    return {"conversation_id": chat_id, "messages": _recover_messages(chat_id)}
