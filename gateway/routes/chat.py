"""Deprecated shim for older imports that still expect chat route helpers."""

from gateway.routes.completions import (
    _non_stream_response,
    _stream_response,
    extract_assistant_text,
)

__all__ = [
    "_non_stream_response",
    "_stream_response",
    "extract_assistant_text",
]
