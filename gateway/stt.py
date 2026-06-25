"""Speech-to-text for Kitty Gateway — wraps faster-whisper."""
from __future__ import annotations

import io
import logging
from functools import lru_cache

logger = logging.getLogger("kitty.stt")

_WHISPER_MODEL_SIZE = "base"
_WHISPER_DEVICE = "cpu"
_WHISPER_COMPUTE = "int8"


try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None  # type: ignore


@lru_cache(maxsize=1)
def _get_model():
    if WhisperModel is None:
        raise RuntimeError("faster-whisper not installed")
    logger.info("Loading faster-whisper model '%s' on %s...", _WHISPER_MODEL_SIZE, _WHISPER_DEVICE)
    return WhisperModel(_WHISPER_MODEL_SIZE, device=_WHISPER_DEVICE, compute_type=_WHISPER_COMPUTE)


def transcribe_bytes(audio_bytes: bytes, filename: str = "audio.webm") -> dict:
    """Transcribe raw audio bytes. Returns OpenAI-compatible dict: {text, language, duration}."""
    try:
        model = _get_model()
        segments, info = model.transcribe(io.BytesIO(audio_bytes), beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments).strip()

        return {
            "text": text,
            "language": info.language,
            "duration": round(info.duration, 2),
        }
    except Exception as e:
        logger.warning("Transcription failed: %s", e)
        raise
