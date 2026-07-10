"""LiteLLM chat-completions proxy and session close."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from gateway.constants import MAX_BODY_BYTES
from gateway.domain_router import classify_domain
from gateway.http_client import get_http_client
from gateway.llm_client import (
    chat_completions_non_stream,
    iter_chat_completions_stream,
    log_chat_trace,
    route_model,
)
from gateway.paths import LITELLM_BASE, LITELLM_KEY, LOG_FILE
from gateway.runtime_manifest import compact_runtime_context, compose_manifest

logger = logging.getLogger("kitty.gateway")
router = APIRouter(tags=["completions"])


class CloseSessionRequest(BaseModel):
    messages: list[dict] = Field(default_factory=list)
    session_id: str = ""


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    from gateway.buddy import (
        on_context_fetch,
        on_request_error,
        on_request_start,
        on_request_success,
    )

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_BYTES:
        on_request_error()
        return Response(status_code=413, content="Request body too large")

    on_request_start()

    body = await request.json()
    raw_project_id = body.get("project_id")
    if raw_project_id is not None and (
        isinstance(raw_project_id, bool) or not isinstance(raw_project_id, int) or raw_project_id <= 0
    ):
        raise HTTPException(
            status_code=400,
            detail=f"project_id must be a positive integer, got {raw_project_id!r}",
        )
    try:
        runtime_manifest = await compose_manifest(project_id=raw_project_id)
    except Exception:
        on_request_error()
        raise
    messages = body.get("messages", [])
    stream = body.get("stream", True)

    user_text = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_text = m.get("content", "")
            break

    correlation_id = str(uuid.uuid4())[:8]
    t_start = time.monotonic()

    domain = classify_domain(user_text)
    model_from_request = body.get("model", "kitty-default")
    if model_from_request and not model_from_request.startswith("kitty-"):
        model = model_from_request
    else:
        model = route_model(user_text)

    from gateway.context_assembler import assemble_context

    try:
        on_context_fetch()
        bundle = await assemble_context(user_text, parts_mode=False, domain=domain)
        system_prompt = f"{bundle.system}\n\n{compact_runtime_context(runtime_manifest)}"
    except Exception:
        on_request_error()
        raise

    enriched = [m for m in messages if m.get("role") != "system"]
    enriched = [{"role": "system", "content": system_prompt}] + enriched

    payload = {
        **{key: value for key, value in body.items() if key != "project_id"},
        "messages": enriched,
        "model": model,
        "stream": stream,
    }

    if stream:

        async def stream_with_trace():
            try:
                async for chunk in iter_chat_completions_stream(payload):
                    yield chunk
                log_chat_trace(
                    LOG_FILE,
                    correlation_id,
                    user_text,
                    domain,
                    model,
                    t_start,
                    runtime_revision=runtime_manifest["revision"],
                )
                on_request_success()
            except Exception:
                on_request_error()
                raise

        return StreamingResponse(
            stream_with_trace(),
            media_type="text/event-stream",
            headers={
                "X-Kitty-Runtime-Revision": runtime_manifest["revision"],
                "X-Kitty-Model-Selected": model,
            },
        )

    try:
        result = await chat_completions_non_stream(payload)
        log_chat_trace(
            LOG_FILE,
            correlation_id,
            user_text,
            domain,
            model,
            t_start,
            runtime_revision=runtime_manifest["revision"],
            model_resolved=result.get("model") or model,
        )
        on_request_success()
        return {
            **result,
            "kitty_runtime": {
                "manifest_revision": runtime_manifest["revision"],
                "resolved_model": result.get("model") or model,
            },
        }
    except Exception:
        on_request_error()
        raise


@router.post("/api/chat/completions")
async def api_chat_completions(request: Request):
    """Open WebUI-compatible alias so kitty-chat can target the gateway directly."""
    return await chat_completions(request)


@router.get("/api/models")
async def api_models():
    """Return available models in OpenAI list format, sourced from LiteLLM."""
    client = await get_http_client()
    try:
        resp = await client.get(
            f"{LITELLM_BASE}/v1/models",
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
        )
        if resp.status_code == 200:
            return Response(content=resp.content, media_type="application/json")
    except Exception as e:
        logger.warning("Failed to fetch models from LiteLLM: %s", e)
        return {
            "object": "list",
            "data": [
                {"id": "kitty-default", "object": "model", "owned_by": "kitty"},
            ],
        }


@router.post("/sessions/close")
async def close_session(payload: CloseSessionRequest):
    """End a chat session — consolidate short-term memory to long-term."""
    from gateway.memory import consolidate_session

    consolidate_session(payload.session_id, payload.messages)

    return {"status": "ok", "session_id": payload.session_id}
