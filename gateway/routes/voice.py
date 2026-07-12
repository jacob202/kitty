"""Speech, transcription, and live voice WebSocket."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket
from fastapi.responses import Response
from pydantic import BaseModel

from gateway.constants import MAX_VOICE_BYTES

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

    written = 0
    chunks: list[bytes] = []
    while chunk := await file.read(64 * 1024):
        written += len(chunk)
        if written > MAX_VOICE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"voice upload exceeds {MAX_VOICE_BYTES} bytes",
            )
        chunks.append(chunk)
    audio = b"".join(chunks)
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
    from gateway.voice_pipeline import VoicePipeline

    pipeline = VoicePipeline()
    await pipeline.handle_websocket(ws)
