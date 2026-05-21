"""Speech, transcription, and live voice WebSocket."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile, WebSocket
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(tags=["voice"])


class AudioSpeechRequest(BaseModel):
    input: str = ""
    voice: str = "alloy"
    speed: float = 1.0
    model: str = "tts-1"


@router.post("/v1/audio/transcriptions")
async def audio_transcriptions(
    file: UploadFile = File(...), model: str = Form("whisper-1")
):
    from gateway.stt import transcribe_bytes

    audio = await file.read()
    result = transcribe_bytes(audio, filename=file.filename or "audio.webm")
    return {"text": result["text"]}


@router.post("/v1/audio/speech")
async def audio_speech(payload: AudioSpeechRequest):
    from gateway.tts import synthesize_async

    text = payload.input
    voice = payload.voice
    speed = payload.speed
    if not text:
        return Response(content=b"", media_type="audio/mpeg")
    audio_bytes = await synthesize_async(text, voice=voice, speed=speed)
    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.websocket("/voice")
async def voice_session(ws: WebSocket):
    from gateway.voice_session import handle_voice_session

    await handle_voice_session(ws)
