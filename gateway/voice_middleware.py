"""Voice Gate Middleware — automatically clean AI responses for all endpoints."""

from __future__ import annotations

import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, StreamingResponse
from gateway.voice_gate import filter_response

class VoiceGateMiddleware(BaseHTTPMiddleware):
    """Protects the user from corporate 'As an AI' filler across all routes."""
    
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Only process JSON responses
        if response.headers.get("content-type") == "application/json":
            # We must consume the response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            try:
                data = json.loads(body)
                modified = False
                
                # Clean 'reply' or 'content' fields
                for key in ["reply", "content"]:
                    if key in data and isinstance(data[key], str):
                        gate = filter_response(data[key])
                        if gate.cleaned != data[key]:
                            data[key] = gate.cleaned
                            modified = True
                
                # Also handle chat completion choices structure
                if "choices" in data and isinstance(data["choices"], list):
                    for choice in data["choices"]:
                        msg = choice.get("message", {})
                        if msg.get("content") and isinstance(msg["content"], str):
                            gate = filter_response(msg["content"])
                            if gate.cleaned != msg["content"]:
                                msg["content"] = gate.cleaned
                                modified = True
                
                if modified:
                    new_body = json.dumps(data).encode("utf-8")
                    return Response(
                        content=new_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type="application/json"
                    )
            except Exception:
                # Fallback to original body if JSON parsing fails
                pass
            
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type="application/json"
            )
            
        return response
