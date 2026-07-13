"""LiteLLM chat-completions proxy and session close."""

from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from gateway import chat_lifecycle
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


def _finish_lifecycle_or_raise(
    handle: chat_lifecycle.TurnHandle,
    *,
    status: str,
    assistant_text: str,
    resolved_model: str | None = None,
    error: str | None = None,
) -> None:
    try:
        chat_lifecycle.finish_turn(
            handle,
            status=status,
            assistant_text=assistant_text,
            resolved_model=resolved_model,
            error=error,
        )
    except Exception as exc:
        raise RuntimeError(
            f"chat lifecycle finalization failed for turn {handle.turn_id}: {exc}"
        ) from exc


def _assistant_text_from_result(result: dict) -> str:
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("non-stream chat response omitted choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise RuntimeError("non-stream chat response omitted assistant message")
    content = message.get("content", "")
    if not isinstance(content, str):
        raise RuntimeError("non-stream chat response content was not text")
    return content


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    from gateway.buddy import (
        on_context_fetch,
        on_request_error,
        on_request_start,
        on_request_success,
    )

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError:
            on_request_error()
            return Response(status_code=400, content="Invalid Content-Length header")
        if declared_length < 0:
            on_request_error()
            return Response(status_code=400, content="Invalid Content-Length header")
        if declared_length > MAX_BODY_BYTES:
            on_request_error()
            return Response(status_code=413, content="Request body too large")

    on_request_start()

    body = await request.json()
    raw_project_id = body.get("project_id")
    if raw_project_id is not None and (
        isinstance(raw_project_id, bool)
        or not isinstance(raw_project_id, int)
        or raw_project_id <= 0
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

    conversation_id = body.get("conversation_id")
    if conversation_id is not None and (
        not isinstance(conversation_id, str) or not conversation_id.strip()
    ):
        raise HTTPException(status_code=400, detail="conversation_id must be a non-empty string")
    user_message_id = body.get("user_message_id")
    if user_message_id is not None and not isinstance(user_message_id, str):
        raise HTTPException(status_code=400, detail="user_message_id must be a string")
    conversation_title = body.get("conversation_title", "")
    if not isinstance(conversation_title, str):
        raise HTTPException(status_code=400, detail="conversation_title must be a string")
    raw_attachment_ids = body.get("attachment_ids")
    if raw_attachment_ids is not None:
        if not isinstance(raw_attachment_ids, list) or not all(
            isinstance(a, str) for a in raw_attachment_ids
        ):
            raise HTTPException(
                status_code=400, detail="attachment_ids must be a list of strings"
            )
        attachment_ids = [a for a in raw_attachment_ids if a.strip()]
    else:
        attachment_ids = None
    manifest_project = runtime_manifest["context"]["active_project"]["value"]
    scoped_project_id = raw_project_id
    if scoped_project_id is None and isinstance(manifest_project, dict):
        candidate_project_id = manifest_project.get("id")
        if isinstance(candidate_project_id, int) and not isinstance(candidate_project_id, bool):
            scoped_project_id = candidate_project_id

    lifecycle_handle: chat_lifecycle.TurnHandle | None = None
    lifecycle_done = False
    if conversation_id is not None:
        try:
            lifecycle_handle = chat_lifecycle.start_turn(
                conversation_id=conversation_id,
                project_id=scoped_project_id,
                title=conversation_title,
                user_message_id=user_message_id,
                user_text=user_text,
                manifest_revision=runtime_manifest["revision"],
                requested_model=model,
                attachment_ids=attachment_ids,
            )
        except Exception:
            on_request_error()
            raise

    thread_objective: str | None = None
    if conversation_id is not None:
        thread_objective = chat_lifecycle.get_conversation_objective(conversation_id)

    from gateway.context_assembler import assemble_context

    try:
        on_context_fetch()
        bundle = await assemble_context(
            user_text, parts_mode=False, domain=domain, model=model, objective=thread_objective,
        )
        system_prompt = f"{bundle.system}\n\n{compact_runtime_context(runtime_manifest)}"
    except Exception as exc:
        if lifecycle_handle is not None and not lifecycle_done:
            _finish_lifecycle_or_raise(
                lifecycle_handle,
                status="failed",
                assistant_text="",
                error=str(exc),
            )
            lifecycle_done = True
        on_request_error()
        raise

    enriched = [m for m in messages if m.get("role") != "system"]
    enriched = [{"role": "system", "content": system_prompt}] + enriched

    payload = {
        **{
            key: value
            for key, value in body.items()
            if key not in {"project_id", "conversation_id", "conversation_title", "user_message_id"}
        },
        "messages": enriched,
        "model": model,
        "stream": stream,
    }

    if stream:

        async def stream_with_trace():
            nonlocal lifecycle_done
            accumulated = ""
            try:
                async for chunk in iter_chat_completions_stream(payload):
                    yield chunk
                    if lifecycle_handle is not None and chunk.startswith(b"data: "):
                        raw_chunk = chunk[6:].strip()
                        if raw_chunk != b"[DONE]":
                            chunk_payload = json.loads(raw_chunk)
                            choices = chunk_payload.get("choices")
                            if not isinstance(choices, list) or not choices:
                                raise RuntimeError(
                                    "stream chunk omitted choices while recording chat lifecycle"
                                )
                            delta = choices[0].get("delta")
                            if not isinstance(delta, dict):
                                raise RuntimeError(
                                    "stream chunk omitted delta while recording chat lifecycle"
                                )
                            content = delta.get("content", "")
                            if not isinstance(content, str):
                                raise RuntimeError(
                                    "stream chunk content was not text while recording chat lifecycle"
                                )
                            accumulated += content
                if bundle.memory_items:
                    trailer = json.dumps({
                        "memory_items": [
                            {"source": item.source, "text": item.text[:200]}
                            for item in bundle.memory_items
                        ],
                    })
                    yield f"data: {trailer}\n\n".encode("utf-8")
                if lifecycle_handle is not None:
                    _finish_lifecycle_or_raise(
                        lifecycle_handle,
                        status="succeeded",
                        assistant_text=accumulated,
                        resolved_model=model,
                    )
                    lifecycle_done = True
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
            except Exception as exc:
                if lifecycle_handle is not None and not lifecycle_done:
                    _finish_lifecycle_or_raise(
                        lifecycle_handle,
                        status="interrupted",
                        assistant_text=accumulated,
                        resolved_model=model,
                        error=str(exc),
                    )
                    lifecycle_done = True
                on_request_error()
                raise

        lifecycle_headers = {
            "X-Kitty-Runtime-Revision": runtime_manifest["revision"],
            "X-Kitty-Model-Selected": model,
        }
        if lifecycle_handle is not None:
            lifecycle_headers["X-Kitty-Turn-ID"] = lifecycle_handle.turn_id
            lifecycle_headers["X-Kitty-Attempt-ID"] = lifecycle_handle.attempt_id
        return StreamingResponse(
            stream_with_trace(),
            media_type="text/event-stream",
            headers=lifecycle_headers,
        )

    try:
        result = await chat_completions_non_stream(payload)
        resolved_model = result.get("model") or model
        if lifecycle_handle is not None:
            _finish_lifecycle_or_raise(
                lifecycle_handle,
                status="succeeded",
                assistant_text=_assistant_text_from_result(result),
                resolved_model=resolved_model,
            )
            lifecycle_done = True
        log_chat_trace(
            LOG_FILE,
            correlation_id,
            user_text,
            domain,
            model,
            t_start,
            runtime_revision=runtime_manifest["revision"],
            model_resolved=resolved_model,
        )
        on_request_success()
        return {
            **result,
            "kitty_runtime": {
                "manifest_revision": runtime_manifest["revision"],
                "resolved_model": resolved_model,
            },
        }
    except Exception as exc:
        if lifecycle_handle is not None and not lifecycle_done:
            _finish_lifecycle_or_raise(
                lifecycle_handle,
                status="failed",
                assistant_text="",
                error=str(exc),
            )
            lifecycle_done = True
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
        detail = getattr(resp, "text", "")[:500]
        raise HTTPException(
            status_code=502,
            detail=(
                f"LiteLLM model discovery returned HTTP {resp.status_code}"
                + (f": {detail}" if detail else "")
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to fetch models from LiteLLM: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"LiteLLM model discovery failed: {exc}",
        ) from exc


@router.post("/sessions/close")
async def close_session(payload: CloseSessionRequest):
    """End a chat session — consolidate short-term memory to long-term."""
    from gateway.memory import consolidate_session

    consolidate_session(payload.session_id, payload.messages)

    return {"status": "ok", "session_id": payload.session_id}
