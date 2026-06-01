"""
Kitty orchestrator — OpenAI-compatible FastAPI endpoint.
Point Open WebUI at http://localhost:8000 with any API key.
"""

import json
import time
import uuid
from typing import AsyncIterator

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import settings
from .memory import (
    add_memory,
    format_memory_injection,
    format_profile_injection,
    get_user_profile,
    search_memories,
)
from .router import build_system_prompt, classify, get_max_tokens, get_model

app = FastAPI(title="Kitty")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ── Request / response models (OpenAI-compatible subset) ──────────────────────

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = settings.sonnet_model
    messages: list[Message]
    stream: bool = True
    max_tokens: int | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _last_user_message(messages: list[Message]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    return ""


def _openai_chunk(content: str, model: str, finish: bool = False) -> str:
    chunk = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {"content": content} if not finish else {},
            "finish_reason": "stop" if finish else None,
        }],
    }
    return f"data: {json.dumps(chunk)}\n\n"


def _openai_response(content: str, model: str) -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


# ── Core chat handler ─────────────────────────────────────────────────────────

async def _stream_response(request: ChatRequest) -> AsyncIterator[str]:
    last_user_msg = _last_user_message(request.messages)
    specialist = classify(last_user_msg)

    profile = get_user_profile()
    memories = search_memories(last_user_msg)

    system_prompt = build_system_prompt(
        specialist=specialist,
        memory_block=format_memory_injection(memories),
        profile_block=format_profile_injection(profile),
    )

    model = get_model(specialist)
    max_tokens = request.max_tokens or get_max_tokens(specialist)

    anthropic_messages = [
        {"role": m.role, "content": m.content}
        for m in request.messages
        if m.role in ("user", "assistant")
    ]

    full_response = ""

    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=anthropic_messages,
    ) as stream:
        for text in stream.text_stream:
            full_response += text
            yield _openai_chunk(text, model)

    yield _openai_chunk("", model, finish=True)
    yield "data: [DONE]\n\n"

    # Store the exchange in memory asynchronously
    add_memory(
        conversation=[
            {"role": "user", "content": last_user_msg},
            {"role": "assistant", "content": full_response},
        ],
        metadata={"specialist": specialist},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {"id": settings.sonnet_model, "object": "model"},
            {"id": settings.opus_model, "object": "model"},
            {"id": settings.haiku_model, "object": "model"},
        ],
    }


@app.post("/v1/chat/completions")
async def chat(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages required")

    if request.stream:
        return StreamingResponse(
            _stream_response(request),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )

    # Non-streaming path
    last_user_msg = _last_user_message(request.messages)
    specialist = classify(last_user_msg)
    profile = get_user_profile()
    memories = search_memories(last_user_msg)
    system_prompt = build_system_prompt(
        specialist=specialist,
        memory_block=format_memory_injection(memories),
        profile_block=format_profile_injection(profile),
    )
    model = get_model(specialist)
    max_tokens = request.max_tokens or get_max_tokens(specialist)
    anthropic_messages = [
        {"role": m.role, "content": m.content}
        for m in request.messages
        if m.role in ("user", "assistant")
    ]
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=anthropic_messages,
    )
    content = response.content[0].text
    add_memory(
        conversation=[
            {"role": "user", "content": last_user_msg},
            {"role": "assistant", "content": content},
        ],
        metadata={"specialist": specialist},
    )
    return _openai_response(content, model)


@app.get("/health")
def health():
    return {"status": "ok"}
