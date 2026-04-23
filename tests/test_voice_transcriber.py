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
