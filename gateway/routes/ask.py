"""Siri / script-friendly ask endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gateway.domain_router import classify_domain
from gateway.llm_client import (
    chat_completions_non_stream,
    extract_assistant_text,
    route_model,
)

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

    from gateway.buddy import (
        on_context_fetch,
        on_request_error,
        on_request_start,
        on_request_success,
    )
    from gateway.context_assembler import assemble_context

    on_request_start()
    try:
        domain = classify_domain(message)
        on_context_fetch()
        bundle = await assemble_context(message, parts_mode=payload.parts_mode, domain=domain)
        system_prompt = bundle.system

        model = route_model(message)
        llm_payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
        }
        data = await chat_completions_non_stream(llm_payload)
        reply = extract_assistant_text(data)

        from gateway.voice_gate import filter_response

        gate = filter_response(reply)
        reply = gate.cleaned
        if gate.violations:
            on_request_error()
        else:
            on_request_success()

        from gateway.self_review import record_interaction

        record_interaction(message, reply)

        return {"reply": reply}
    except Exception:
        on_request_error()
        raise
