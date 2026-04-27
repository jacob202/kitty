import io

from flask import Flask

from src.api.voice_routes import voice_bp
from src.voice.web_transcriber import TranscriptionResult


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(voice_bp)
    return app


def test_transcribe_requires_audio_file():
    client = _make_app().test_client()

    response = client.post("/api/transcribe", data={}, content_type="multipart/form-data")

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "audio file is required"}


def test_transcribe_accepts_webm_and_returns_json(monkeypatch):
    client = _make_app().test_client()

    class FakeTranscriber:
        def transcribe_file(self, path):
            assert path.suffix == ".webm"
            return TranscriptionResult(
                text="replace the capacitor",
                language="en",
                duration_seconds=3.5,
            )

    monkeypatch.setattr("src.api.voice_routes.get_transcriber", lambda: FakeTranscriber())

    response = client.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(b"audio"), "sample.webm", "audio/webm")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "text": "replace the capacitor",
        "language": "en",
        "duration_seconds": 3.5,
    }


def test_transcribe_accepts_wav_and_returns_json(monkeypatch):
    client = _make_app().test_client()

    class FakeTranscriber:
        def transcribe_file(self, path):
            assert path.suffix == ".wav"
            return TranscriptionResult(
                text="wav transcript",
                language="en",
                duration_seconds=1.5,
            )

    monkeypatch.setattr("src.api.voice_routes.get_transcriber", lambda: FakeTranscriber())

    response = client.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(b"audio"), "sample.wav", "audio/wav")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "text": "wav transcript",
        "language": "en",
        "duration_seconds": 1.5,
    }


def test_transcribe_accepts_mp4_and_returns_json(monkeypatch):
    client = _make_app().test_client()

    class FakeTranscriber:
        def transcribe_file(self, path):
            assert path.suffix == ".mp4"
            return TranscriptionResult(
                text="mp4 transcript",
                language="en",
                duration_seconds=2.25,
            )

    monkeypatch.setattr("src.api.voice_routes.get_transcriber", lambda: FakeTranscriber())

    response = client.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(b"audio"), "sample.mp4", "audio/mp4")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "text": "mp4 transcript",
        "language": "en",
        "duration_seconds": 2.25,
    }


def test_transcribe_rejects_unsupported_audio_format():
    client = _make_app().test_client()

    response = client.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(b"audio"), "sample.flac", "audio/flac")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "unsupported audio format"}


def test_transcribe_rejects_oversized_upload(monkeypatch):
    client = _make_app().test_client()

    monkeypatch.setattr("src.api.voice_routes.MAX_AUDIO_BYTES", 8)

    response = client.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(b"0123456789"), "sample.webm", "audio/webm")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert response.get_json() == {"ok": False, "error": "audio file is too large"}
