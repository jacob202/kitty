"""Kitty Gateway — thin FastAPI brain between Open WebUI and LiteLLM."""
import asyncio
import json
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

MAX_BODY_BYTES = 10 * 1024 * 1024  # 10MB

from gateway.domain_router import classify_domain
from gateway.llm_client import route_model
from gateway.prompt_loader import load_prompt
from gateway.context_builder import build_user_context
from gateway.paths import PROJECT_ROOT, LOGS_DIR, validate_dirs

LITELLM_BASE = "http://localhost:8001"
LITELLM_KEY = os.environ.get("LITELLM_API_KEY", "kitty-local-key-change-me")
LOG_FILE = LOGS_DIR / "gateway_trace.jsonl"

validate_dirs()

app = FastAPI(title="Kitty Gateway")
logger = logging.getLogger("kitty.gateway")
logging.basicConfig(level=logging.INFO)


def _validate_env() -> None:
    """Warn on missing or unsafe default environment configuration."""
    required = ("OPENROUTER_API_KEY", "GATEWAY_SECRET")
    for key in required:
        value = os.environ.get(key, "").strip()
        if not value:
            logger.warning("Missing required env var: %s", key)

    defaults = {
        "LITELLM_API_KEY": "kitty-local-key-change-me",
        "GATEWAY_SECRET": "kitty-local-key-change-me",
    }
    for key, default in defaults.items():
        value = os.environ.get(key, "").strip()
        if value and value == default:
            logger.warning("Unsafe default value detected for %s", key)


_validate_env()

from gateway.auth import BearerAuthMiddleware
app.add_middleware(BearerAuthMiddleware)
_webui_origin = os.environ.get("KITTY_WEBUI_ORIGIN")
allow_origins = [o for o in [
    "http://localhost:3000",
    "http://localhost:8000",
    _webui_origin,
] if o]  # filter None

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_http_client: httpx.AsyncClient | None = None


class AskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32000)


class TroubleshootRequest(BaseModel):
    device: str = Field(..., min_length=1, max_length=1000)
    symptom: str = Field(..., min_length=1, max_length=1000)


class LearnRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=1000)


class TasksSyncRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=1000)


class DeepResearchRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=1000)


async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=60, limits=httpx.Limits(max_connections=100))
    return _http_client


@app.on_event("shutdown")
async def shutdown():
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()


@app.middleware("http")
async def enforce_max_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                return Response(status_code=413, content="Request body too large")
        except ValueError:
            return Response(status_code=400, content="Invalid content-length")
    return await call_next(request)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "kitty-gateway"}


@app.get("/ops/doctor")
async def ops_doctor(fail_on_warn: bool = False):
    """Return kitty_gateway doctor report as JSON for UI/automation."""
    root_dir = Path(__file__).resolve().parent.parent
    doctor_script = root_dir / "kitty_gateway" / "doctor.sh"
    if not doctor_script.exists():
        raise HTTPException(status_code=500, detail=f"doctor script missing: {doctor_script}")

    cmd = [str(doctor_script), "--json"]
    if fail_on_warn:
        cmd.append("--fail-on-warn")

    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            cmd,
            cwd=str(root_dir),
            env={**os.environ},
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="doctor check timed out")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"doctor exec failed: {exc}")

    payload = {}
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": proc.stdout}

    response = {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "doctor": payload,
        "stderr": proc.stderr[-2000:] if proc.stderr else "",
        "fail_on_warn": fail_on_warn,
    }
    return response


@app.get("/brief")
async def morning_brief():
    from gateway.brief import generate_brief
    return generate_brief()


@app.post("/ask")
async def ask(payload: AskRequest):
    """Plain JSON chat endpoint for Siri Shortcuts and scripts."""
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    domain = classify_domain(message)
    domain_prompt = load_prompt(domain)
    cached_prefix, dynamic_suffix = await build_user_context(message, domain)
    system_prompt = "\n\n".join(part for part in [domain_prompt, cached_prefix, dynamic_suffix] if part)

    model = "kitty-private" if domain == "health" else route_model(message)
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

    return {"reply": reply}


@app.get("/reset")
async def nightly_reset():
    from gateway.reset import send_nightly_reset
    success = send_nightly_reset()
    return {"status": "sent" if success else "failed"}


@app.post("/troubleshoot")
async def troubleshoot(payload: TroubleshootRequest):
    from gateway.troubleshooter import initiate_troubleshooting
    return {"response": initiate_troubleshooting(payload.device, payload.symptom)}


@app.post("/learn")
@limiter.limit("10/minute")
async def learn(request: Request, payload: LearnRequest):
    from gateway.learning import generate_micro_lesson
    return {"lesson": generate_micro_lesson(payload.topic)}


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
@limiter.limit("10/minute")
async def deep_research(request: Request, payload: DeepResearchRequest):
    from gateway.researcher import deep_dive
    # Deep dive performs ingestion automatically
    result = await asyncio.to_thread(deep_dive, payload.topic)
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

    from gateway.context_builder import build_user_context
    domain = classify_domain(user_text)
    if domain == "health":
        model = "kitty-private"
    else:
        model = route_model(user_text)
        
    cached_prefix, dynamic_suffix = await build_user_context(user_text, domain)
    
    if "claude" in model.lower():
        sys_msgs = [
            {"role": "system", "content": cached_prefix, "cache_control": {"type": "ephemeral"}},
            {"role": "system", "content": dynamic_suffix}
        ] if dynamic_suffix else [{"role": "system", "content": cached_prefix}]
    else:
        system_prompt = "\n\n".join(part for part in [cached_prefix, dynamic_suffix] if part)
        sys_msgs = [{"role": "system", "content": system_prompt}]

    enriched = [m for m in messages if m.get("role") != "system"]
    enriched = sys_msgs + enriched

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
        async for chunk in resp.aiter_bytes():
            yield chunk
    _log_trace(correlation_id, user_text, domain, model, t_start)


async def _non_stream_response(payload):
    client = await get_http_client()
    resp = await client.post(
        f"{LITELLM_BASE}/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {LITELLM_KEY}"},
    )
    return resp.json()


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
