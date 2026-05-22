"""Voice session legacy shim — re-exports from voice_pipeline.

This module is kept for backward compatibility. New code should use
gateway.voice_pipeline directly.
"""

from gateway.voice_pipeline import (
    VoiceSession,
    VoiceSessionState,
    _handle_text_message,
    handle_voice_session,
)

__all__ = [
    "VoiceSession",
    "VoiceSessionState",
    "handle_voice_session",
    "_handle_text_message",
]
