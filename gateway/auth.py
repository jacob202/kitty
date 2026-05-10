# gateway/auth.py
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

EXEMPT_PATHS = {"/health"}


import logging
logger = logging.getLogger("kitty.auth")

if not os.environ.get("GATEWAY_SECRET"):
    if os.environ.get("KITTY_ENV") != "test":
        logger.warning("GATEWAY_SECRET not set — all routes blocked")

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        secret = os.environ.get("GATEWAY_SECRET", "")
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
            
        if not secret:
            if os.environ.get("KITTY_ENV") == "test":
                return await call_next(request)
            return JSONResponse({"error": "Gateway not configured"}, status_code=503)
            
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != secret:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)
