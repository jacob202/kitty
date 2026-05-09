"""Text-to-speech for Kitty Gateway — edge-tts (Microsoft Neural TTS, free)."""
from __future__ import annotations
import asyncio
import logging

import edge_tts

logger = logging.getLogger("kitty.tts")

# Kitty's default voice — warm, natural, female
DEFAULT_VOICE = "en-US-AriaNeural"

# OpenAI voice name → edge-tts voice mapping
VOICE_MAP = {
    "alloy":   "en-US-AriaNeural",
    "echo":    "en-US-GuyNeural",
    "fable":   "en-GB-SoniaNeural",
    "onyx":    "en-US-ChristopherNeural",
    "nova":    "en-US-JennyNeural",
    "shimmer": "en-US-AriaNeural",
    "kitty":   "en-US-AriaNeural",
}


async def synthesize_async(text: str, voice: str = "alloy", speed: float = 1.0) -> bytes:
    """Async synthesis — returns MP3 bytes. Call with await from async contexts."""
    edge_voice = VOICE_MAP.get(voice, voice)
    rate_pct = round((speed - 1.0) * 100)
    rate = f"{rate_pct:+d}%"
    communicate = edge_tts.Communicate(text, edge_voice, rate=rate)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


def synthesize(text: str, voice: str = "alloy", speed: float = 1.0) -> bytes:
    """Sync synthesis — use from non-async contexts (CLI, scripts)."""
    return asyncio.run(synthesize_async(text, voice=voice, speed=speed))
