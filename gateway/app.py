"""Kitty Gateway — thin FastAPI brain between Open WebUI and LiteLLM."""
import json
import logging
import time
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

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


@app.get("/brief")
async def morning_brief():
    """Generate and return today's morning brief."""
    from gateway.brief import generate_brief
    return generate_brief()


@app.get("/weekly")
async def weekly_mirror():
    """Return this week's behavioral pattern mirror."""
    from gateway.honcho import get_weekly_mirror
    return get_weekly_mirror()


@app.post("/v1/audio/transcriptions")
async def audio_transcriptions(file: UploadFile = File(...), model: str = Form("whisper-1")):
    """OpenAI-compatible STT endpoint. Accepts audio file, returns {text}."""
    from gateway.stt import transcribe_bytes
    audio = await file.read()
    result = transcribe_bytes(audio, filename=file.filename or "audio.webm")
    return {"text": result["text"]}


@app.post("/v1/audio/speech")
async def audio_speech(request: Request):
    """OpenAI-compatible TTS endpoint. Returns MP3 audio bytes."""
    from gateway.tts import synthesize_async
    body = await request.json()
    text = body.get("input", "")
    voice = body.get("voice", "alloy")
    speed = float(body.get("speed", 1.0))
    if not text:
        return Response(content=b"", media_type="audio/mpeg")
    audio_bytes = await synthesize_async(text, voice=voice, speed=speed)
    return Response(content=audio_bytes, media_type="audio/mpeg")


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

    # Pull relevant memories and inject into system prompt
    from gateway.memory import get_context_block
    memory_context = ""
    try:
        memory_context = get_context_block(user_text, limit=5)
    except Exception:
        pass  # Memory unavailable — degrade gracefully

    # Pull relevant knowledge chunks
    from gateway.knowledge import get_knowledge_block
    knowledge_context = ""
    try:
        knowledge_context = get_knowledge_block(user_text, limit=3)
    except Exception:
        pass  # Knowledge unavailable — degrade gracefully

    # Combine memory + knowledge into system prompt
    extra = "\n\n".join(filter(None, [memory_context, knowledge_context]))
    if extra:
        system_prompt = system_prompt + "\n\n" + extra

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
