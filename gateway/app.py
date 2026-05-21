"""Kitty Gateway — thin FastAPI brain between Open WebUI and LiteLLM."""

from __future__ import annotations

import logging
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from gateway.auth import BearerAuthMiddleware
from gateway.constants import MAX_BODY_BYTES
from gateway.http_client import get_http_client
from gateway.paths import validate_dirs, validate_env
from gateway.routes.register import register_routes

logger = logging.getLogger("kitty.gateway")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_dirs()
    validate_env()
    try:
        from gateway.telegram_bot import start_polling, is_configured as tg_configured

        if tg_configured():
            start_polling()
    except Exception:
        pass
    yield
    client = await get_http_client()
    if client and not client.is_closed:
        await client.aclose()
    try:
        from gateway.telegram_bot import stop as tg_stop

        await tg_stop()
    except Exception:
        pass


app = FastAPI(title="Kitty Gateway", lifespan=lifespan)

app.add_middleware(BearerAuthMiddleware)
_webui_origin = os.environ.get("KITTY_WEBUI_ORIGIN")
_cors_origins = [
    o for o in ["http://localhost:3000", "http://localhost:8000", _webui_origin] if o
]
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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "kitty-gateway"}


register_routes(app)
