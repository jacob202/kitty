"""Kitty Gateway — thin FastAPI brain between Open WebUI and LiteLLM."""
import asyncio
import json
import logging
import os
import time
import uuid

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from pathlib import Path

MAX_BODY_BYTES = 10 * 1024 * 1024  # 10MB

from gateway.domain_router import classify_domain
from gateway.llm_client import route_model
from gateway.prompt_loader import load_prompt

from contextlib import asynccontextmanager
from gateway.paths import LOG_FILE, LITELLM_BASE, LITELLM_KEY, validate_dirs, validate_env

_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_dirs()
    validate_env()
    yield
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()


logger = logging.getLogger("kitty.gateway")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Kitty Gateway", lifespan=lifespan)

from gateway.auth import BearerAuthMiddleware
app.add_middleware(BearerAuthMiddleware)
_webui_origin = os.environ.get("KITTY_WEBUI_ORIGIN")
_cors_origins = [o for o in ["http://localhost:3000", "http://localhost:8000", _webui_origin] if o]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def body_size_guard(request: Request, call_next):
    """Reject requests with content-length exceeding MAX_BODY_BYTES."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_BYTES:
        return Response(status_code=413, content="Request body too large")
    response = await call_next(request)
    return response


class AskRequest(BaseModel):
    message: str
    parts_mode: bool = False


class TroubleshootRequest(BaseModel):
    device: str = Field(min_length=1)
    symptom: str = Field(min_length=1)


class TasksSyncRequest(BaseModel):
    action: str


class LearnRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=1000)


async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=60, limits=httpx.Limits(max_connections=100))
    return _http_client


@app.get("/health")
async def health():
    return {"status": "ok", "service": "kitty-gateway"}


@app.get("/brief")
@app.get("/api/brief")
async def morning_brief():
    from gateway.brief import generate_brief
    return generate_brief()


@app.post("/ask")
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
    data = await _non_stream_response(llm_payload)
    choices = data.get("choices", []) if isinstance(data, dict) else []
    reply = ""
    if choices and isinstance(choices[0], dict):
        message_obj = choices[0].get("message", {})
        if isinstance(message_obj, dict):
            reply = message_obj.get("content", "")

    from gateway.voice_gate import filter_response
    gate = filter_response(reply)
    reply = gate.cleaned

    from gateway.self_review import record_interaction
    record_interaction(message, reply)

    return {"reply": reply}


@app.get("/journal/prompt")
async def journal_prompt(theme: Optional[str] = None):
    """Return a random journal writing prompt. Optional ?theme= filter."""
    from gateway.journal import get_random_prompt
    return get_random_prompt(theme)


@app.post("/journal/start")
async def journal_start(theme: Optional[str] = None):
    """Begin a journal interview session. Returns Kitty's opening question."""
    from gateway.journal import get_opener, build_interview_system_prompt
    from gateway.prompt_loader import load_prompt
    opener = get_opener(theme)
    system_prompt = build_interview_system_prompt(load_prompt("general"), theme)
    return {"opener": opener, "system_prompt": system_prompt, "theme": theme}


@app.post("/journal/synthesize")
async def journal_synthesize(request: Request):
    """Synthesize a completed journal interview into a first-person entry."""
    body = await request.json()
    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages required")

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
    data = await _non_stream_response(payload)
    choices = data.get("choices", []) if isinstance(data, dict) else []
    entry = ""
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message", {})
        if isinstance(msg, dict):
            entry = msg.get("content", "")
    if entry:
        save_journal_entry(entry, theme=theme, session_id=session_id)
    return {"entry": entry}


@app.get("/reset")
async def nightly_reset():
    from gateway.reset import send_nightly_reset
    success = send_nightly_reset()
    return {"status": "sent" if success else "failed"}


@app.post("/troubleshoot")
async def troubleshoot(payload: TroubleshootRequest):
    from gateway.troubleshooter import initiate_troubleshooting
    return {"response": await initiate_troubleshooting(payload.device, payload.symptom)}


@app.post("/learn")
async def learn(payload: LearnRequest):
    from gateway.learning import generate_knowledge_gate_question
    return {"lesson": await generate_knowledge_gate_question(payload.topic)}


@app.post("/inventory/photo")
async def inventory_photo(file: UploadFile = File(...)):
    from gateway.inventory import process_inventory_image
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or ".jpg").suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    result = process_inventory_image(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)
    return {"message": result}


@app.post("/tasks/sync")
async def tasks_sync(payload: TasksSyncRequest):
    from gateway.tasks import sync_next_action
    success = sync_next_action(payload.action)
    return {"success": success}


@app.post("/research/deep")
async def deep_research(topic: str):
    from gateway.researcher import deep_dive
    result = await deep_dive(topic)
    return {"result": result}


@app.get("/weekly")
async def weekly_mirror():
    from gateway.honcho import get_weekly_mirror
    return get_weekly_mirror()


@app.get("/memories")
async def list_memories(namespace: Optional[str] = None, limit: int = 50):
    """List stored memories. Optional namespace filter: facts|patterns."""
    from gateway.memory import list_memories
    return {"memories": list_memories(namespace=namespace, limit=limit)}


@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a specific memory by ID."""
    from gateway.memory import delete_memory
    success = delete_memory(memory_id)
    return {"deleted": success, "memory_id": memory_id}


@app.delete("/sessions/{session_id}/messages/{message_id}")
async def delete_message(session_id: str, message_id: str):
    """Delete a specific message from a session's journal by message_id (timestamp)."""
    from gateway.journal import delete_journal_message
    success = delete_journal_message(session_id, message_id)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"deleted": success, "session_id": session_id, "message_id": message_id}


@app.post("/v1/audio/transcriptions")
async def audio_transcriptions(file: UploadFile = File(...), model: str = Form("whisper-1")):
    from gateway.stt import transcribe_bytes
    audio = await file.read()
    result = transcribe_bytes(audio, filename=file.filename or "audio.webm")
    return {"text": result["text"]}


@app.post("/v1/audio/speech")
async def audio_speech(request: Request):
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
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_BYTES:
        return Response(status_code=413, content="Request body too large")
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", "kitty-default")
    stream = body.get("stream", True)

    user_text = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_text = m.get("content", "")
            break

    correlation_id = str(uuid.uuid4())[:8]
    t_start = time.monotonic()

    domain = classify_domain(user_text)
    if domain == "health":
        model = "kitty-private"
    else:
        model = route_model(user_text)

    from gateway.context_builder import get_system_prompt

    system_prompt = await get_system_prompt(user_text, parts_mode=False, domain=domain)

    enriched = [m for m in messages if m.get("role") != "system"]
    enriched = [{"role": "system", "content": system_prompt}] + enriched

    payload = {**body, "messages": enriched, "model": model, "stream": stream}

    if stream:
        return StreamingResponse(
            _stream_response(payload, correlation_id, user_text, domain, model, t_start),
            media_type="text/event-stream",
        )
    else:
        result = await _non_stream_response(payload)
        _log_trace(correlation_id, user_text, domain, model, t_start)
        return result


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
                yield chunk + b"\n\n"
                break

            try:
                data = json.loads(raw_data)
                # Standardize reasoning_content/thinking tokens for Open WebUI
                delta = data["choices"][0].get("delta", {})
                if "reasoning_content" in delta:
                    # Map to the format Open WebUI expects for thinking blocks
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
    return resp.json()


def _filter_chat_response(result: dict) -> None:
    """Run voice_gate on the assistant content in a chat completions response."""
    try:
        choices = result.get("choices", [])
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message", {})
            if isinstance(msg, dict) and msg.get("content"):
                from gateway.voice_gate import filter_response
                gate = filter_response(msg["content"])
                msg["content"] = gate.cleaned
    except Exception:
        pass


def _log_trace(correlation_id: str, user_text: str, domain: str, model: str, t_start: float):
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


@app.post("/sessions/close")
async def close_session(request: Request):
    """End a chat session — consolidate short-term memory to long-term."""
    body = await request.json()
    messages = body.get("messages", [])
    session_id = body.get("session_id", "")

    from gateway.memory import consolidate_session
    consolidate_session(session_id, messages)

    return {"status": "ok", "session_id": session_id}
