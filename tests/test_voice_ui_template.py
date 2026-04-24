from pathlib import Path

from flask import Flask

from src.api.streaming_routes import streaming_bp


def _make_app():
    root = Path(__file__).resolve().parents[1]
    return Flask(
        __name__,
        template_folder=str(root / "src" / "templates"),
        static_folder=str(root / "src" / "static"),
    )


def test_index_contains_mic_control_and_transcribe_flow():
    app = _make_app()
    app.register_blueprint(streaming_bp)

    response = app.test_client().get("/")

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert 'id="voice-toggle"' in html
    assert "MediaRecorder" in html
    assert "/api/transcribe" in html
    assert "voice_poll" not in html


def test_index_initializes_voice_support_and_reuses_composer_send_path():
    app = _make_app()
    app.register_blueprint(streaming_bp)

    html = app.test_client().get("/").get_data(as_text=True)

    assert "setVoiceState(supportsVoiceInput() ? 'idle' : 'unsupported')" in html
    assert "await sendMsg();" in html
    assert "MAX_VOICE_RECORDING_MS" in html
    assert "cancelVoiceRecording" in html
    assert "e.key === 'Escape'" in html
