"""LiteLLM chat-completions proxy and session close."""

from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from gateway.constants import MAX_BODY_BYTES
from gateway.domain_router import classify_domain
from gateway.http_client import get_http_client
from gateway.llm_client import route_model
from gateway.paths import LITELLM_BASE, LITELLM_KEY, LOG_FILE
from gateway.token_usage_log import log_llm_usage, normalize_usage_payload

logger = logging.getLogger("kitty.gateway")
router = APIRouter(tags=["completions"])


class CloseSessionRequest(BaseModel):
    messages: list[dict] = Field(default_factory=list)
    session_id: str = ""


def extract_assistant_text(data: object) -> str:
    """Return the first assistant message content from a LiteLLM-style response."""
    if not isinstance(data, dict):
        return ""

    choices = data.get("choices", [])
    if not choices or not isinstance(choices[0], dict):
        return ""

    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        return ""

    content = message.get("content", "")
    return content if isinstance(content, str) else ""


async def _stream_response(payload, correlation_id, user_text, domain, model, t_start):
    client = await get_http_client()
    async with client.stream(
        "POST",
        f"{LITELLM_BASE}/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {LITELLM_KEY}"},
    ) as resp:
        async for chunk in resp.aiter_lines():
            if not chunk or not chunk.startswith("data: "):
                continue

            raw_data = chunk[6:].strip()
            if raw_data == "[DONE]":
                yield chunk.encode("utf-8") + b"\n\n"
                break

            try:
                data = json.loads(raw_data)
                delta = data["choices"][0].get("delta", {})
                if "reasoning_content" in delta:
                    pass
            except Exception:
                pass

            yield chunk.encode("utf-8") + b"\n\n"
    _log_trace(correlation_id, user_text, domain, model, t_start)


async def _non_stream_response(payload):
    client = await get_http_client()
    resp = await client.post(
        f"{LITELLM_BASE}/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {LITELLM_KEY}"},
    )
    data = resp.json()
    usage = normalize_usage_payload(
        data.get("usage") if isinstance(data, dict) else None
    )
    if usage:
        log_llm_usage(
            "litellm",
            str(data.get("model") or payload.get("model") or "unknown"),
            "chat.completions.create",
            usage,
            {
                "route": "gateway_chat_nonstream",
                "request_model": payload.get("model"),
            },
        )
    return data


def _filter_chat_response(result: dict) -> None:
    """Run voice_gate on the assistant content in a chat completions response."""
    try:
        reply = extract_assistant_text(result)
        if reply:
            from gateway.voice_gate import filter_response

            gate = filter_response(reply)
            result["choices"][0]["message"]["content"] = gate.cleaned
    except Exception:
        pass


def _log_trace(
    correlation_id: str, user_text: str, domain: str, model: str, t_start: float
):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    elapsed_ms = round((time.monotonic() - t_start) * 1000, 1)
    entry = {
        "correlation_id": correlation_id,
        "user_request": user_text[:120],
        "domain_classified": domain,
        "model_selected": model,
        "timestamp": time.time(),
        "elapsed_ms": elapsed_ms,
    }
    with LOG_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_BYTES:
        return Response(status_code=413, content="Request body too large")
    body = await request.json()
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

    from gateway.context_builder import get_system_prompt

    system_prompt = await get_system_prompt(user_text, parts_mode=False, domain=domain)

    enriched = [m for m in messages if m.get("role") != "system"]
    enriched = [{"role": "system", "content": system_prompt}] + enriched

    payload = {**body, "messages": enriched, "model": model, "stream": stream}

    if stream:
        return StreamingResponse(
            _stream_response(
                payload, correlation_id, user_text, domain, model, t_start
            ),
            media_type="text/event-stream",
        )
    result = await _non_stream_response(payload)
    _log_trace(correlation_id, user_text, domain, model, t_start)
    return result


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
