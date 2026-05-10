"""Lazy-loaded faster-whisper transcription service (singleton)."""

import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model = None
_model_size = "base"


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        try:
            from faster_whisper import WhisperModel
            logger.info("[Transcription] Loading faster-whisper model '%s'...", _model_size)
            _model = WhisperModel(_model_size, device="cpu", compute_type="int8")
            logger.info("[Transcription] Model loaded.")
        except ImportError:
            logger.error("[Transcription] faster-whisper not installed — run: pip install faster-whisper")
            raise
    return _model


def transcribe(audio_path: str | Path) -> dict:
    """Transcribe an audio file. Returns {text, language, duration_seconds}."""
    model = _get_model()
    segments, info = model.transcribe(str(audio_path), beam_size=5)
    text = " ".join(s.text.strip() for s in segments).strip()
    return {
        "text": text,
        "language": info.language,
        "duration_seconds": round(info.duration, 2),
    }
