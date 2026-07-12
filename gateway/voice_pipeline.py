"""Voice Pipeline — deep module for real-time voice conversation.

This is a DEEP module. Callers should only use:
- VoicePipeline.process_turn(audio_bytes) -> VoiceTurnResult: The high-leverage entry point.
- VoicePipeline.handle_websocket(ws): WebSocket handler for voice sessions.

Internal adapters (STT, TTS, gate) are implementation details.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect

from gateway.constants import MAX_BODY_BYTES

logger = logging.getLogger("kitty.voice_pipeline")

# --- Deep entry point result types ---


@dataclass
class VoiceTurnResult:
    """Result of processing one voice turn."""

    user_text: str
    assistant_text: str
    stt_language: str = ""
    stt_duration: float = 0.0
    turn_count: int = 0
    violations: List[str] = field(default_factory=list)
    error: Optional[str] = None


# --- Legacy compatibility: VoiceSession class ---


@dataclass
class VoiceSessionState:
    """State for one voice conversation session."""

    messages: List[Dict[str, str]] = field(default_factory=list)
    mode: str = "ptt"
    turn_count: int = 0
    created_at: float = field(default_factory=time.time)
    MAX_HISTORY: int = 20

    def add_user_message(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        self._trim()

    def add_assistant_message(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})
        self._trim()

    def _trim(self) -> None:
        if len(self.messages) > self.MAX_HISTORY:
            self.messages = self.messages[-self.MAX_HISTORY :]


class VoiceSession:
    """Legacy session wrapper kept for tests and older imports."""

    MAX_MESSAGE_HISTORY = 20

    def __init__(self, ws):
        self.ws = ws
        self._state = VoiceSessionState()

    @property
    def mode(self) -> str:
        return self._state.mode

    @mode.setter
    def mode(self, value: str) -> None:
        self._state.mode = value

    @property
    def messages(self) -> List[Dict[str, str]]:
        return self._state.messages

    @property
    def turn_count(self) -> int:
        return self._state.turn_count

    @turn_count.setter
    def turn_count(self, value: int) -> None:
        self._state.turn_count = value

    def add_user_message(self, text: str) -> None:
        self._state.add_user_message(text)

    def add_assistant_message(self, text: str) -> None:
        self._state.add_assistant_message(text)


# --- Internal adapters (implementation details) ---


class STTAdapter:
    """Speech-to-text adapter — wraps faster-whisper."""

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> dict:
        """Transcribe raw audio bytes. Returns {text, language, duration}."""
        from gateway.stt import transcribe_bytes

        return transcribe_bytes(audio_bytes, filename)


class TTSAdapter:
    """Text-to-speech adapter — wraps edge-tts."""

    async def synthesize(self, text: str, voice: str = "kitty", speed: float = 1.0) -> bytes:
        """Async synthesis — returns MP3 bytes."""
        from gateway.tts import synthesize_async

        return await synthesize_async(text, voice=voice, speed=speed)


class VoiceGateAdapter:
    """Voice gate adapter — SOUL.md compliance filtering."""

    def filter(self, text: str) -> tuple[str, List[str]]:
        """Filter response text. Returns (cleaned_text, violations)."""
        from gateway.voice_gate import filter_response

        result = filter_response(text)
        return result.cleaned, result.violations


# --- Deep module: VoicePipeline ---


class VoicePipeline:
    """Deep voice pipeline module.

    High-leverage entry point for all voice operations.
    Internal adapters (STT, TTS, gate) are implementation details.
    """

    def __init__(
        self,
        stt_adapter: Optional[STTAdapter] = None,
        tts_adapter: Optional[TTSAdapter] = None,
        gate_adapter: Optional[VoiceGateAdapter] = None,
    ):
        self._stt = stt_adapter or STTAdapter()
        self._tts = tts_adapter or TTSAdapter()
        self._gate = gate_adapter or VoiceGateAdapter()
        self._sessions: Dict[WebSocket, VoiceSessionState] = {}

    async def process_turn(
        self,
        audio_bytes: bytes,
        session: Optional[VoiceSessionState] = None,
        domain: Optional[str] = None,
    ) -> VoiceTurnResult:
        """Process one voice turn: STT → LLM → gate.

        When ``session`` is provided, prior turns in ``session.messages`` are
        included in the LLM payload. TTS and session mutation stay in the
        WebSocket handler.
        """
        # 1. Transcribe
        try:
            stt_result = self._stt.transcribe(audio_bytes)
            user_text = stt_result.get("text", "").strip()
        except Exception as e:
            logger.warning("STT failed: %s", e)
            return VoiceTurnResult(
                user_text="",
                assistant_text="",
                error="Couldn't understand that — try again?",
            )

        if not user_text:
            return VoiceTurnResult(
                user_text="",
                assistant_text="",
                stt_language="",
                stt_duration=0.0,
            )

        # 2. LLM response
        try:
            from gateway.context_builder import get_system_prompt
            from gateway.domain_router import classify_domain
            from gateway.llm_client import (
                chat_completions_non_stream,
                extract_assistant_text,
                route_model,
            )

            if domain is None:
                domain = classify_domain(user_text)

            system_prompt = await get_system_prompt(user_text, domain=domain)
            model = route_model(user_text)

            llm_messages: List[Dict[str, str]] = [
                {"role": "system", "content": system_prompt},
            ]
            if session is not None:
                llm_messages.extend(session.messages)
            llm_messages.append({"role": "user", "content": user_text})

            payload = {
                "model": model,
                "stream": False,
                "messages": llm_messages,
            }

            data = await chat_completions_non_stream(payload)
            reply = extract_assistant_text(data)

            # Gate filtering
            reply, violations = self._gate.filter(reply)

        except Exception:
            logger.exception("LLM call failed")
            return VoiceTurnResult(
                user_text=user_text,
                assistant_text="",
                error="Brain fog — say that again?",
            )

        if not reply:
            return VoiceTurnResult(
                user_text=user_text,
                assistant_text="",
                error="Got nothing back — try again?",
            )

        return VoiceTurnResult(
            user_text=user_text,
            assistant_text=reply,
            stt_language=stt_result.get("language", ""),
            stt_duration=stt_result.get("duration", 0.0),
            violations=violations,
        )

    async def handle_websocket(self, ws: WebSocket) -> None:
        """WebSocket handler for voice sessions.

        This is the WebSocket entry point. It maintains session state
        and routes messages to the deep pipeline.
        """
        await ws.accept(max_size=MAX_BODY_BYTES)
        session = VoiceSessionState()
        self._sessions[ws] = session
        logger.info("Voice session started (mode=%s)", session.mode)

        try:
            while True:
                data = await ws.receive()

                if "text" in data:
                    await self._handle_text_message(session, ws, data["text"])
                elif "bytes" in data:
                    await self._handle_audio_bytes(session, ws, data["bytes"])
        except WebSocketDisconnect:
            logger.info("Voice session ended after %d turns", session.turn_count)
        except Exception:
            logger.exception("Voice session error")
            try:
                await ws.send_json(
                    {"type": "error", "message": "Session error — reconnect to restart"}
                )
            except Exception:
                logger.debug("voice: failed to send error to client", exc_info=True)
        finally:
            self._sessions.pop(ws, None)

    async def _handle_text_message(
        self, session: VoiceSessionState, ws: WebSocket, text: str
    ) -> None:
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
            await ws.send_json({"type": "pong"})

    async def _handle_audio_bytes(
        self, session: VoiceSessionState, ws: WebSocket, audio: bytes
    ) -> None:
        """Process audio bytes through the deep pipeline."""
        t_start = time.monotonic()

        # Process through deep pipeline
        result = await self.process_turn(audio)

        if result.error:
            await ws.send_json({"type": "error", "message": result.error})
            return

        if not result.user_text:
            await ws.send_json({"type": "transcript", "text": "", "status": "empty"})
            return

        # Send transcript
        await ws.send_json(
            {
                "type": "transcript",
                "text": result.user_text,
                "timestamp": time.time(),
            }
        )

        session.add_user_message(result.user_text)

        # Send thinking indicator
        await ws.send_json({"type": "thinking", "text": "..."})

        # Send response text
        await ws.send_json({"type": "response_text", "text": result.assistant_text})

        session.add_assistant_message(result.assistant_text)
        session.turn_count += 1

        # Send audio if available
        if result.error:
            pass  # Error already sent
        else:
            try:
                audio_out = await self._tts.synthesize(result.assistant_text, voice="kitty")
                await ws.send_bytes(audio_out)
            except Exception as e:
                logger.warning("TTS failed (non-fatal): %s", e)

        elapsed = round((time.monotonic() - t_start) * 1000)
        logger.info("Voice turn %d completed in %dms", session.turn_count, elapsed)

        # Log interaction
        try:
            from gateway.self_review import record_interaction

            record_interaction(result.user_text, result.assistant_text)
        except Exception:
            logger.debug("voice: failed to record interaction", exc_info=True)

        await ws.send_json({"type": "done"})


# --- Legacy compatibility shim ---


async def handle_voice_session(ws: WebSocket) -> None:
    """Legacy entry point — delegates to VoicePipeline.

    Kept for backward compatibility. New callers should use
    VoicePipeline directly.
    """
    pipeline = VoicePipeline()
    await pipeline.handle_websocket(ws)


async def _handle_text_message(session: VoiceSession, text: str) -> None:
    """Module-level helper for legacy tests."""
    try:
        msg = json.loads(text)
    except json.JSONDecodeError:
        return

    msg_type = msg.get("type", "")
    if msg_type == "mode":
        session.mode = msg.get("mode", "ptt")
    elif msg_type == "ping":
        await session.ws.send_json({"type": "pong"})
