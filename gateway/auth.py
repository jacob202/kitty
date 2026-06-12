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
        # If GATEWAY_SECRET is unset this middleware FAILS CLOSED (503) unless
        # KITTY_ENV is explicitly "test". This prevents a silent env-load
        # failure (e.g. under launchd) from leaving the gateway open.
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        if not secret:
            # Only bypass auth when explicitly running in test mode.
            # Any other value — including unset — blocks the request so that
            # a missing GATEWAY_SECRET under launchd fails closed, not open.
            if os.environ.get("KITTY_ENV") == "test":
                return await call_next(request)
            return JSONResponse({"error": "Gateway not configured"}, status_code=503)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != secret:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)
