"""Persistent voice session — WebSocket-based hands-free conversation.

Flow:
  Client connects → sends binary audio chunks → STT → LLM → TTS → audio back
  
Maintains conversation context across turns so Kitty remembers what was said.
Supports mode signaling: push-to-talk (client controls when audio is coming) 
or VAD (voice activity detection — client-side).

Messages (JSON text frames):
  {"type": "mode", "mode": "ptt" | "vad"}
  {"type": "transcript", "text": "...", "timestamp": 1234.5}
  {"type": "response_text", "text": "..."}
  {"type": "thinking", "text": "..."}
  {"type": "error", "message": "..."}
  {"type": "done"}

Binary frames: client → server = audio bytes (webm/mp4)
               server → client = TTS audio bytes (mp3)
"""
from __future__ import annotations

import json
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("kitty.voice_session")

MAX_MESSAGE_HISTORY: int = 20  # number of turns to keep in context


class VoiceSession:
    """State for one WebSocket voice connection."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.messages: list[dict] = []  # [{"role": "user"|"assistant", "content": ...}]
        self.mode: str = "ptt"
        self.created_at: float = time.time()
        self.turn_count: int = 0

    def add_user_message(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        self._trim()

    def add_assistant_message(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})
        self._trim()

    def _trim(self) -> None:
        if len(self.messages) > MAX_MESSAGE_HISTORY:
            self.messages = self.messages[-MAX_MESSAGE_HISTORY:]


async def handle_voice_session(ws: WebSocket) -> None:
    """Main voice session loop. Entry point from the WebSocket route."""
    await ws.accept()
    session = VoiceSession(ws)
    logger.info("Voice session started (mode=%s)", session.mode)

    try:
        while True:
            data = await ws.receive()

            if "text" in data:
                await _handle_text_message(session, data["text"])
            elif "bytes" in data:
                await _handle_audio_bytes(session, data["bytes"])
    except WebSocketDisconnect:
        logger.info("Voice session ended after %d turns", session.turn_count)
    except Exception:
        logger.exception("Voice session error")
        try:
            await ws.send_json({"type": "error", "message": "Session error — reconnect to restart"})
        except Exception:
            pass


async def _handle_text_message(session: VoiceSession, text: str) -> None:
    """Handle JSON control messages from the client."""
    try:
        msg = json.loads(text)
    except json.JSONDecodeError:
        return

    msg_type = msg.get("type", "")

    if msg_type == "mode":
        session.mode = msg.get("mode", "ptt")
        logger.debug("Voice mode switched to %s", session.mode)

    elif msg_type == "ping":
        await session.ws.send_json({"type": "pong"})


async def _handle_audio_bytes(session: VoiceSession, audio: bytes) -> None:
    """Transcribe audio, run through LLM, synthesize response, send back."""
    t_start = time.monotonic()

    # 1. Transcribe
    try:
        from gateway.stt import transcribe_bytes
        result = transcribe_bytes(audio)
        user_text = result.get("text", "").strip()
    except Exception as e:
        logger.warning("Voice STT failed: %s", e)
        await session.ws.send_json({"type": "error", "message": "Couldn't understand that — try again?"})
        return

    if not user_text:
        await session.ws.send_json({"type": "transcript", "text": "", "status": "empty"})
        return

    # Send transcript to client (for UI display)
    await session.ws.send_json({
        "type": "transcript",
        "text": user_text,
        "timestamp": time.time(),
    })

    session.add_user_message(user_text)

    # 2. Build system prompt + get LLM response
    try:
        from gateway.context_builder import get_system_prompt
        from gateway.domain_router import classify_domain
        from gateway.llm_client import route_model
        from gateway.voice_gate import filter_response

        domain = classify_domain(user_text)
        system_prompt = await get_system_prompt(user_text, domain=domain)
        model = route_model(user_text)

        # Send thinking indicator
        await session.ws.send_json({"type": "thinking", "text": "..."})

        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                *session.messages,
            ],
        }

        from gateway.app import _non_stream_response
        data = await _non_stream_response(payload)

        choices = data.get("choices", []) if isinstance(data, dict) else []
        reply = ""
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message", {})
            if isinstance(msg, dict):
                reply = msg.get("content", "")

        # Filter through voice gate
        gate = filter_response(reply)
        reply = gate.cleaned

    except Exception:
        logger.exception("Voice LLM call failed")
        await session.ws.send_json({"type": "error", "message": "Brain fog — say that again?"})
        return

    if not reply:
        await session.ws.send_json({"type": "error", "message": "Got nothing back — try again?"})
        return

    session.add_assistant_message(reply)
    session.turn_count += 1

    # Send response text (for UI)
    await session.ws.send_json({"type": "response_text", "text": reply})

    # 3. Synthesize speech
    try:
        from gateway.tts import synthesize_async
        audio_out = await synthesize_async(reply, voice="kitty")
        await session.ws.send_bytes(audio_out)
    except Exception as e:
        logger.warning("Voice TTS failed (non-fatal): %s", e)
        # Text response already sent — TTS failure is non-fatal

    elapsed = round((time.monotonic() - t_start) * 1000)
    logger.info("Voice turn %d completed in %dms", session.turn_count, elapsed)

    # 4. Log interaction
    try:
        from gateway.self_review import record_interaction
        record_interaction(user_text, reply)
    except Exception:
        pass

    await session.ws.send_json({"type": "done"})
