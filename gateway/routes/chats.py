"""Kitty-chat session persistence — backed by kitty.db via chats_store.

Phase C C3: the route reads and writes through chats_store instead of
data/kitty/chats.json. The wire contract (paths, request/response
shapes) is unchanged.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from gateway import chats_store
from gateway import chat_lifecycle

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


@router.get("/chats/{chat_id}/lifecycle")
def get_chat_lifecycle(chat_id: str) -> dict:
    try:
        return chat_lifecycle.list_conversation(chat_id)
    except chat_lifecycle.ChatLifecycleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
