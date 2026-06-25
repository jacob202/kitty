"""Tests for gateway STT and TTS modules."""
from unittest.mock import MagicMock, patch

# ── STT ──────────────────────────────────────────────────────────────────────

def test_transcribe_bytes_returns_text():
    import gateway.stt as stt
    stt._get_model.cache_clear()

    mock_seg = MagicMock()
    mock_seg.text = " Hello Kitty "
    mock_info = MagicMock()
    mock_info.language = "en"
    mock_info.duration = 2.5

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_seg], mock_info)

    with patch.object(stt, "_get_model", return_value=mock_model):
        result = stt.transcribe_bytes(b"fake-audio", filename="test.wav")

    assert result["text"] == "Hello Kitty"
    assert result["language"] == "en"
    assert result["duration"] == 2.5


def test_transcribe_bytes_empty_audio():
    import gateway.stt as stt
    stt._get_model.cache_clear()

    mock_info = MagicMock()
    mock_info.language = "en"
    mock_info.duration = 0.0

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], mock_info)

    with patch.object(stt, "_get_model", return_value=mock_model):
        result = stt.transcribe_bytes(b"", filename="empty.wav")

    assert result["text"] == ""


# ── TTS ──────────────────────────────────────────────────────────────────────

def test_voice_map_covers_openai_voices():
    from gateway.tts import VOICE_MAP
    openai_voices = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
    for v in openai_voices:
        assert v in VOICE_MAP, f"Missing OpenAI voice: {v}"


def test_synthesize_returns_bytes():
    import gateway.tts as t

    async def fake_stream():
        yield {"type": "audio", "data": b"mp3chunk1"}
        yield {"type": "audio", "data": b"mp3chunk2"}
        yield {"type": "WordBoundary", "data": None}

    mock_communicate = MagicMock()
    mock_communicate.stream.return_value = fake_stream()

    with patch.object(t.edge_tts, "Communicate", return_value=mock_communicate):
        result = t.synthesize("Hello Kitty", voice="alloy")

    assert result == b"mp3chunk1mp3chunk2"


def test_synthesize_speed_conversion():
    import gateway.tts as t

    async def fake_stream():
        return
        yield  # make it a generator

    captured = {}

    class MockCommunicate:
        def __init__(self, text, voice, rate=""):
            captured["rate"] = rate
        def stream(self):
            return fake_stream()

    with patch.object(t.edge_tts, "Communicate", MockCommunicate):
        try:
            t.synthesize("test", voice="alloy", speed=1.5)
        except Exception:
            pass

    assert captured.get("rate") == "+50%"


def test_synthesize_default_speed_is_zero_pct():
    import gateway.tts as t

    async def fake_stream():
        return
        yield

    captured = {}

    class MockCommunicate:
        def __init__(self, text, voice, rate=""):
            captured["rate"] = rate
        def stream(self):
            return fake_stream()

    with patch.object(t.edge_tts, "Communicate", MockCommunicate):
        try:
            t.synthesize("test", voice="alloy", speed=1.0)
        except Exception:
            pass

    assert captured.get("rate") == "+0%"


# ── Gateway endpoints ─────────────────────────────────────────────────────────

def test_stt_endpoint_returns_text():
    from fastapi.testclient import TestClient

    import gateway.stt as stt
    from gateway.app import app
    stt._get_model.cache_clear()

    mock_seg = MagicMock()
    mock_seg.text = "Testing one two three"
    mock_info = MagicMock()
    mock_info.language = "en"
    mock_info.duration = 1.5

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_seg], mock_info)

    with patch.object(stt, "_get_model", return_value=mock_model):
        client = TestClient(app)
        resp = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("audio.wav", b"fake-audio", "audio/wav")},
            data={"model": "whisper-1"},
        )

    assert resp.status_code == 200
    assert resp.json()["text"] == "Testing one two three"


def test_tts_endpoint_returns_audio():
    from fastapi.testclient import TestClient

    import gateway.tts as t
    from gateway.app import app

    async def fake_synthesize(*args, **kwargs):
        return b"fakemp3"

    with patch.object(t, "synthesize_async", side_effect=fake_synthesize):
        client = TestClient(app)
        resp = client.post(
            "/v1/audio/speech",
            json={"model": "tts-1", "input": "Hello Kitty", "voice": "alloy"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"fakemp3"


def test_tts_endpoint_empty_input():
    from fastapi.testclient import TestClient

    from gateway.app import app
    client = TestClient(app)
    resp = client.post(
        "/v1/audio/speech",
        json={"model": "tts-1", "input": "", "voice": "alloy"},
    )
    assert resp.status_code == 200
    assert resp.content == b""
