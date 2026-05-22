"""Kitty-chat session persistence."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from gateway.paths import DATA_DIR

router = APIRouter(tags=["chats"])

_CHATS_FILE = DATA_DIR / "kitty" / "chats.json"


def _read_chats() -> list:
    if not _CHATS_FILE.exists():
        return []
    try:
        return json.loads(_CHATS_FILE.read_text())
    except Exception:
        return []


def _write_chats(chats: list) -> None:
    _CHATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CHATS_FILE.write_text(json.dumps(chats, ensure_ascii=False))


@router.get("/chats")
async def get_chats():
    """Return all saved chat sessions."""
    return {"chats": _read_chats()}


@router.post("/chats")
async def upsert_chat(request: Request):
    """Create or update a chat session by id."""
    chat = await request.json()
    if not chat.get("id"):
        raise HTTPException(status_code=400, detail="id required")
    existing = _read_chats()
    updated = [c for c in existing if c.get("id") != chat["id"]] + [chat]
    _write_chats(updated)
    return {"ok": True}


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str):
    """Delete a chat session."""
    existing = _read_chats()
    _write_chats([c for c in existing if c.get("id") != chat_id])
    return {"ok": True}
