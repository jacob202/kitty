"""Kitty Gateway — thin FastAPI brain between Open WebUI and LiteLLM."""
import json
import logging
import time
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from gateway.domain_router import classify_domain
from gateway.prompt_loader import load_prompt

LITELLM_BASE = "http://localhost:8001"
LITELLM_KEY = "kitty-local-key-change-me"
LOG_FILE = Path("/Users/jacobbrizinski/Projects/kitty/logs/gateway_trace.jsonl")

app = FastAPI(title="Kitty Gateway")
logger = logging.getLogger("kitty.gateway")
logging.basicConfig(level=logging.INFO)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "kitty-gateway"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", "kitty-default")
    stream = body.get("stream", True)

    # Extract last user message for classification
    user_text = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_text = m.get("content", "")
            break

    correlation_id = str(uuid.uuid4())[:8]
    t_start = time.monotonic()

    # Classify domain and inject system prompt
    domain = classify_domain(user_text)
    system_prompt = load_prompt(domain)

    # Health queries always route to private model
    if domain == "health":
        model = "kitty-private"

    # Prepend system prompt (replace existing system message if present)
    enriched = [m for m in messages if m.get("role") != "system"]
    enriched = [{"role": "system", "content": system_prompt}] + enriched

    payload = {**body, "messages": enriched, "model": model, "stream": stream}

    _log_trace(correlation_id, user_text, domain, t_start)

    async def stream_response():
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{LITELLM_BASE}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {LITELLM_KEY}"},
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk

    return StreamingResponse(stream_response(), media_type="text/event-stream")


def _log_trace(correlation_id: str, user_text: str, domain: str, t_start: float):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "correlation_id": correlation_id,
        "user_request": user_text[:120],
        "domain_classified": domain,
        "timestamp": time.time(),
        "elapsed_ms": round((time.monotonic() - t_start) * 1000, 1),
    }
    with LOG_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")
