import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

from src.voice.web_transcriber import TranscriptionResult, WebTranscriber


def test_transcribe_file_returns_joined_text(monkeypatch, tmp_path):
    audio_path = tmp_path / "sample.webm"
    audio_path.write_bytes(b"audio")

    class FakeSegment:
        def __init__(self, text):
            self.text = text

    class FakeInfo:
        language = "en"
        duration = 4.2

    class FakeModel:
        def transcribe(self, path, beam_size, vad_filter):
            assert Path(path) == audio_path
            return [FakeSegment("replace"), FakeSegment(" the cap")], FakeInfo()

    monkeypatch.setattr(WebTranscriber, "_load_model", lambda self: FakeModel())

    result = WebTranscriber().transcribe_file(audio_path)

    assert result == TranscriptionResult(
        text="replace the cap",
        language="en",
        duration_seconds=4.2,
    )


def test_transcribe_file_raises_when_transcript_is_empty(monkeypatch, tmp_path):
    audio_path = tmp_path / "empty.mp4"
    audio_path.write_bytes(b"audio")

    class FakeInfo:
        language = "en"
        duration = 1.0

    class FakeModel:
        def transcribe(self, path, beam_size, vad_filter):
            return [], FakeInfo()

    monkeypatch.setattr(WebTranscriber, "_load_model", lambda self: FakeModel())

    with pytest.raises(ValueError, match="No speech detected"):
        WebTranscriber().transcribe_file(audio_path)


def test_load_model_caches_constructor(monkeypatch):
    calls = []

    class FakeWhisperModel:
        def __init__(self, model_size, device, compute_type):
            calls.append((model_size, device, compute_type))

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisperModel))

    transcriber = WebTranscriber(model_size="tiny", device="cpu", compute_type="float32")

    first_model = transcriber._load_model()
    second_model = transcriber._load_model()

    assert first_model is second_model
    assert calls == [("tiny", "cpu", "float32")]
