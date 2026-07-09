"""Kitty Gateway — thin FastAPI brain between the kitty-chat UI and LiteLLM."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from gateway.auth import BearerAuthMiddleware
from gateway.constants import MAX_BODY_BYTES
from gateway.errors import KittyError
from gateway.paths import validate_dirs, validate_env
from gateway.routes.register import register_routes
from gateway.voice_middleware import VoiceGateMiddleware

logger = logging.getLogger("kitty.gateway")
logging.basicConfig(level=logging.INFO)


async def _brief_bg_loop():
    """Warm the brief cache on startup, then refresh every 15 minutes."""
    from gateway.brief import generate_brief

    loop = asyncio.get_event_loop()
    while True:
        try:
            await loop.run_in_executor(None, generate_brief)
            logger.info("Brief cache refreshed.")
        except Exception as e:
            logger.warning("Brief refresh failed: %s", e)
        await asyncio.sleep(900)


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_dirs()
    validate_env()
    try:
        from gateway.telegram_bot import is_configured as tg_configured
        from gateway.telegram_bot import start_polling

        if tg_configured():
            start_polling()
    except Exception:
        pass
    brief_task = asyncio.create_task(_brief_bg_loop())
    from gateway.brief_scheduler import start_brief_scheduler

    brief_scheduler_task = start_brief_scheduler()
    from gateway.inbox_watcher import watch_loop as _inbox_watch

    inbox_task = asyncio.create_task(_inbox_watch())
    try:
        from gateway.cron import register_action
        from gateway.cron import start as cron_start

        async def _action_refresh_brief():
            from gateway.brief import generate_brief

            await asyncio.to_thread(generate_brief)

        async def _action_check_nudges():
            from gateway.nudge import check

            check()

        async def _action_check_monitors():
            from gateway.web_monitor import check_now, list_watches

            for w in list_watches():
                try:
                    await check_now(w["watch_id"])
                except Exception:
                    pass

        async def _action_memory_consolidate():
            from gateway.memory_consolidation import nightly_dream

            await asyncio.to_thread(nightly_dream)

        async def _action_triage_inbox():
            from gateway import triage

            await asyncio.to_thread(triage.run_pass)

        async def _action_poll_mail():
            from gateway.connectors.mail import poll_now

            await asyncio.to_thread(poll_now)

        async def _action_warm_prefetch():
            from gateway.prefetcher import warm

            await warm()

        register_action("brief.refresh", _action_refresh_brief)
        register_action("nudges.check", _action_check_nudges)
        register_action("monitors.check", _action_check_monitors)
        register_action("memory.consolidate", _action_memory_consolidate)
        register_action("inbox.triage", _action_triage_inbox)
        def _action_poll_github():
            from gateway.connectors import github

            return github.poll_now()

        async def _action_poll_experts():
            from gateway.expert_proactive import poll_experts

            await asyncio.to_thread(poll_experts)

        register_action("mail.poll", _action_poll_mail)
        register_action("github.poll", _action_poll_github)
        register_action("experts.poll", _action_poll_experts)
        register_action("prefetch.warm", _action_warm_prefetch)
        cron_start()
    except Exception:
        pass
    yield
    brief_task.cancel()
    if brief_scheduler_task is not None:
        brief_scheduler_task.cancel()
    inbox_task.cancel()
    try:
        from gateway.http_client import _http_client

        if _http_client and not _http_client.is_closed:
            await _http_client.aclose()
    except Exception:
        pass
    try:
        from gateway.telegram_bot import stop as tg_stop

        await tg_stop()
    except Exception:
        pass


app = FastAPI(title="Kitty Gateway", lifespan=lifespan)

app.add_middleware(VoiceGateMiddleware)
app.add_middleware(BearerAuthMiddleware)
_cors_origins = ["http://localhost:3000", "http://localhost:4000", "http://localhost:4001"]
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
    return await call_next(request)


@app.exception_handler(KittyError)
async def kitty_error_handler(request: Request, exc: KittyError):
    """Translate ``KittyError`` subclasses to a consistent JSON error shape.

    Falls through to FastAPI's default 500 for genuinely unexpected
    exceptions — this handler only fires for errors the gateway
    describes on purpose. The body shape is:

    ``{"error": "<machine code>", "message": "...", "details": {...}}``
    """
    if exc.status_code >= 500:
        logger.exception("kitty_error: %s %s", exc.code, exc.message)
    return Response(
        status_code=exc.status_code,
        media_type="application/json",
        content=json.dumps(exc.to_dict()),
    )


@app.get("/health")
async def health():
    # litellm_reachable lives here because /api/models masks LiteLLM failures
    # behind a fallback model list — this is the one honest signal the UI
    # health strip can read. Short timeout so a dead proxy can't make the
    # gateway itself look slow.
    from gateway.http_client import get_http_client
    from gateway.paths import LITELLM_BASE

    litellm_reachable = False
    try:
        client = await get_http_client()
        resp = await client.get(f"{LITELLM_BASE}/health/readiness", timeout=1.5)
        litellm_reachable = resp.status_code == 200
    except Exception:  # noqa: BLE001 — any failure means "not reachable", which is the answer
        litellm_reachable = False
    return {
        "status": "ok",
        "service": "kitty-gateway",
        "litellm_reachable": litellm_reachable,
    }


@app.get("/mood")
async def get_mood():
    """Return Kitty's current mood and session stats for the UI."""
    from gateway.buddy import get_state

    return get_state()


@app.get("/stream")
async def sse_stream(request: Request, session_id: str | None = None):
    """Server-Sent Events endpoint for pushing state changes to the UI."""
    import uuid

    from fastapi.responses import StreamingResponse

    from gateway.sse import broadcaster

    client_id = session_id or str(uuid.uuid4())

    async def event_generator():
        async for message in broadcaster.subscribe(client_id):
            if await request.is_disconnected():
                break
            yield message

    return StreamingResponse(event_generator(), media_type="text/event-stream")


register_routes(app)
