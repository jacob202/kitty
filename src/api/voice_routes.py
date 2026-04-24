"""Voice transcription routes for the web UI."""

import logging
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

voice_bp = Blueprint("voice", __name__)
MAX_AUDIO_BYTES = 10 * 1024 * 1024

_ALLOWED_TYPES = {
    "audio/webm": ".webm",
    "audio/mp4": ".mp4",
    "audio/wav": ".wav",
}
_transcriber = None


def get_transcriber():
    global _transcriber
    if _transcriber is None:
        from src.voice.web_transcriber import WebTranscriber

        _transcriber = WebTranscriber()
    return _transcriber


@voice_bp.route("/api/transcribe", methods=["POST"])
def transcribe_audio():
    upload = request.files.get("audio")
    if upload is None or not upload.filename:
        return jsonify({"ok": False, "error": "audio file is required"}), 400

    if (request.content_length or 0) > MAX_AUDIO_BYTES:
        return jsonify({"ok": False, "error": "audio file is too large"}), 413

    content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    suffix = _ALLOWED_TYPES.get(content_type)
    if suffix is None:
        return jsonify({"ok": False, "error": "unsupported audio format"}), 400

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            upload.save(temp_file)

        result = get_transcriber().transcribe_file(temp_path)
        return jsonify(
            {
                "ok": True,
                "text": result.text,
                "language": result.language,
                "duration_seconds": result.duration_seconds,
            }
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 422
    except Exception:
        logger.exception("Voice transcription failed")
        return jsonify({"ok": False, "error": "transcription failed"}), 500
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
