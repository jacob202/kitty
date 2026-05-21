"""Siri / script-friendly ask endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gateway.domain_router import classify_domain
from gateway.llm_client import route_model
from gateway.routes import completions as llm

router = APIRouter(tags=["ask"])


class AskRequest(BaseModel):
    message: str
    parts_mode: bool = False


@router.post("/ask")
async def ask(payload: AskRequest):
    """Plain JSON chat endpoint for Siri Shortcuts and scripts."""
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    from gateway.context_builder import get_system_prompt

    domain = classify_domain(message)
    system_prompt = await get_system_prompt(
        message, parts_mode=payload.parts_mode, domain=domain
    )

    model = route_model(message)
    llm_payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    }
    data = await llm._non_stream_response(llm_payload)
    reply = llm.extract_assistant_text(data)

    from gateway.voice_gate import filter_response

    gate = filter_response(reply)
    reply = gate.cleaned

    from gateway.self_review import record_interaction

    record_interaction(message, reply)

    return {"reply": reply}
