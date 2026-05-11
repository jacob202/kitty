# gateway/auth.py
import os
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("kitty.auth")

EXEMPT_PATHS = {"/health"}


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        secret = os.environ.get("GATEWAY_SECRET", "")
        # WARNING: if GATEWAY_SECRET is not set, ALL requests bypass auth.
        # This is intentional for local dev/test, but MUST NOT occur in production.
        # Set GATEWAY_SECRET in your environment before exposing this gateway externally.
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        if not secret:
            env = os.environ.get("KITTY_ENV", "")
            if env == "prod":
                return JSONResponse({"error": "Gateway not configured"}, status_code=503)
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != secret:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)
