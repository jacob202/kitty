"""Journal interview and message management."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from gateway.errors import StorageNotFound, ValidationError
from gateway.llm_client import (
    chat_completions_non_stream,
    extract_assistant_text,
    route_model,
)

router = APIRouter(tags=["journal"])


class JournalChatRequest(BaseModel):
    messages: list[dict]
    system_prompt: str = ""


@router.get("/journal/prompt")
async def journal_prompt(theme: Optional[str] = None):
    """Return a random journal writing prompt. Optional ?theme= filter."""
    from gateway.journal import get_random_prompt

    return get_random_prompt(theme)


@router.post("/journal/start")
async def journal_start(theme: Optional[str] = None):
    """Begin a journal interview session. Returns Kitty's opening question."""
    from gateway.journal import build_interview_system_prompt, get_opener
    from gateway.prompt_loader import load_prompt

    opener = get_opener(theme)
    system_prompt = build_interview_system_prompt(load_prompt("general"), theme)
    return {"opener": opener, "system_prompt": system_prompt, "theme": theme}


@router.post("/journal/synthesize")
async def journal_synthesize(request: Request):
    """Synthesize a completed journal interview into a first-person entry."""
    body = await request.json()
    messages = body.get("messages", [])
    if not messages:
        raise ValidationError("messages required")

    from gateway.journal import build_synthesis_prompt, save_journal_entry

    synthesis_system = build_synthesis_prompt()
    theme = body.get("theme")
    session_id = body.get("session_id")

    model = route_model("")
    payload = {
        "model": model,
        "stream": False,
        "messages": [{"role": "system", "content": synthesis_system}] + messages,
    }
    data = await chat_completions_non_stream(payload)
    entry = extract_assistant_text(data)
    if entry:
        save_journal_entry(entry, theme=theme, session_id=session_id)
    return {"entry": entry}


@router.post("/journal/chat")
async def journal_chat(payload: JournalChatRequest):
    """Single journal interview turn — uses provided system_prompt, bypasses context_builder."""
    if not payload.messages:
        raise ValidationError("messages required")
    model = route_model("")
    llm_messages: list[dict] = []
    if payload.system_prompt:
        llm_messages.append({"role": "system", "content": payload.system_prompt})
    llm_messages.extend(payload.messages)
    data = await chat_completions_non_stream(
        {"model": model, "stream": False, "messages": llm_messages}
    )
    return {"reply": extract_assistant_text(data)}


@router.delete("/sessions/{session_id}/messages/{message_id}")
async def delete_message(session_id: str, message_id: str):
    """Delete a specific message from a session's journal by message_id (timestamp)."""
    from gateway.journal import delete_journal_message

    success = delete_journal_message(session_id, message_id)
    if not success:
        raise StorageNotFound("Message not found")
    return {"deleted": success, "session_id": session_id, "message_id": message_id}
