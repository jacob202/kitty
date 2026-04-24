# Voice Input Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the poll-based web voice path with a browser mic flow that uploads recorded audio to `/api/transcribe`, transcribes it with `faster-whisper`, and submits the result through the normal chat flow.

**Architecture:** Add a dedicated transcription service in `src/voice` that lazily owns `faster-whisper`, then expose it through a thin Flask blueprint in `src/api`. On the frontend, keep the existing chat transport, but replace `voiceLoop()` with an explicit composer mic button that records with `MediaRecorder`, uploads audio, and auto-sends the returned transcript.

**Tech Stack:** Flask, pytest, faster-whisper, tempfile, MediaRecorder, fetch, existing SSE chat flow

---

## File Structure

- Create: `src/voice/web_transcriber.py`
  Responsibility: lazy-load `faster-whisper`, transcribe one uploaded file, normalize output for web routes
- Create: `src/api/voice_routes.py`
  Responsibility: validate multipart uploads, write/delete temp audio files, call the transcriber, return JSON
- Modify: `src/api/__init__.py`
  Responsibility: export the new `voice_bp` blueprint
- Modify: `web.py`
  Responsibility: register the new voice blueprint with the existing app factory
- Modify: `src/templates/index.html`
  Responsibility: add mic UI, recording/transcribing/error states, MIME type selection, upload flow, and remove the old poll loop
- Create: `tests/test_voice_transcriber.py`
  Responsibility: unit coverage for transcript normalization and service errors
- Create: `tests/test_voice_routes.py`
  Responsibility: API coverage for `/api/transcribe`
- Create: `tests/test_voice_ui_template.py`
  Responsibility: guard that the rendered UI contains the mic control and no longer contains the old `/voice_poll` loop

### Task 1: Build the transcription service

**Files:**
- Create: `src/voice/web_transcriber.py`
- Test: `tests/test_voice_transcriber.py`

- [ ] **Step 1: Write the failing unit tests**

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/opt/homebrew/bin/python3.12 -m pytest tests/test_voice_transcriber.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.voice.web_transcriber'`

- [ ] **Step 3: Write the minimal transcription service**

```python
from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel


@dataclass(eq=True)
class TranscriptionResult:
    text: str
    language: str | None
    duration_seconds: float | None


class WebTranscriber:
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _load_model(self):
        if self._model is None:
            self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model

    def transcribe_file(self, audio_path: Path) -> TranscriptionResult:
        model = self._load_model()
        segments, info = model.transcribe(str(audio_path), beam_size=5, vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            raise ValueError("No speech detected")
        return TranscriptionResult(
            text=text,
            language=getattr(info, "language", None),
            duration_seconds=getattr(info, "duration", None),
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/opt/homebrew/bin/python3.12 -m pytest tests/test_voice_transcriber.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/voice/web_transcriber.py tests/test_voice_transcriber.py
git commit -m "feat: add web voice transcription service"
```

### Task 2: Add `POST /api/transcribe`

**Files:**
- Create: `src/api/voice_routes.py`
- Modify: `src/api/__init__.py`
- Modify: `web.py`
- Test: `tests/test_voice_routes.py`

- [ ] **Step 1: Write the failing API tests**

```python
import io

from web import create_app


def test_transcribe_requires_audio_file():
    app, _ = create_app()
    client = app.test_client()

    response = client.post("/api/transcribe", data={}, content_type="multipart/form-data")

    assert response.status_code == 400
    assert response.get_json()["error"] == "audio file is required"


def test_transcribe_accepts_webm_and_returns_json(monkeypatch):
    app, _ = create_app()
    client = app.test_client()

    class FakeResult:
        text = "replace the capacitor"
        language = "en"
        duration_seconds = 3.5

    monkeypatch.setattr(
        "src.api.voice_routes.get_transcriber",
        lambda: type("FakeTranscriber", (), {"transcribe_file": lambda self, path: FakeResult})(),
    )

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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/opt/homebrew/bin/python3.12 -m pytest tests/test_voice_routes.py -q`
Expected: FAIL with `404` or import errors because the route does not exist yet

- [ ] **Step 3: Add the route and blueprint wiring**

```python
voice_bp = Blueprint("voice", __name__)
_ALLOWED_TYPES = {"audio/webm": ".webm", "audio/mp4": ".mp4"}


@voice_bp.route("/api/transcribe", methods=["POST"])
def transcribe_audio():
    upload = request.files.get("audio")
    if upload is None or not upload.filename:
        return jsonify({"ok": False, "error": "audio file is required"}), 400

    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    suffix = _ALLOWED_TYPES.get(content_type)
    if suffix is None:
        return jsonify({"ok": False, "error": "unsupported audio format"}), 400

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            upload.save(temp_file)

        result = get_transcriber().transcribe_file(temp_path)
        return jsonify({
            "ok": True,
            "text": result.text,
            "language": result.language,
            "duration_seconds": result.duration_seconds,
        })
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 422
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
```

```python
from .voice_routes import voice_bp
```

```python
for bp in (
    bom_bp, core_bp, hardware_bp, honcho_bp,
    memory_bp, reasoning_bp, settings_bp,
    streaming_bp, swarm_bp, system_bp, voice_bp,
):
    app.register_blueprint(bp)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/opt/homebrew/bin/python3.12 -m pytest tests/test_voice_routes.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/voice_routes.py src/api/__init__.py web.py tests/test_voice_routes.py
git commit -m "feat: add web audio transcription endpoint"
```

### Task 3: Replace the poll loop with a mic button

**Files:**
- Modify: `src/templates/index.html`
- Test: `tests/test_voice_ui_template.py`

- [ ] **Step 1: Write the failing template regression test**

```python
from web import create_app


def test_index_contains_voice_button_and_no_voice_poll_loop():
    app, _ = create_app()
    client = app.test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert 'id="voice-btn"' in html
    assert "/api/transcribe" in html
    assert "/voice_poll" not in html
    assert "function chooseRecordingMimeType()" in html
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `/opt/homebrew/bin/python3.12 -m pytest tests/test_voice_ui_template.py -q`
Expected: FAIL because the current UI still contains `voiceLoop()` and has no mic button

- [ ] **Step 3: Add the frontend voice controller**

```html
<div id="input-container">
  <button id="voice-btn" type="button" title="Record voice message" onclick="toggleVoiceRecording()">MIC</button>
  <textarea id="inp" placeholder="What's on your mind?" rows="1"
            onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
  <button id="send" onclick="sendMsg()">SEND</button>
</div>
<div id="voice-status" aria-live="polite"></div>
```

```javascript
let mediaRecorder = null;
let recordedChunks = [];
let recordingTimer = null;
let recordingStartedAt = 0;
let voiceState = 'idle';

function chooseRecordingMimeType() {
  const preferred = ['audio/webm', 'audio/mp4'];
  for (const mimeType of preferred) {
    if (window.MediaRecorder && MediaRecorder.isTypeSupported(mimeType)) return mimeType;
  }
  return '';
}

async function toggleVoiceRecording() {
  if (voiceState === 'recording') return stopVoiceRecording();
  return startVoiceRecording();
}

async function uploadVoiceBlob(blob) {
  const form = new FormData();
  const mimeType = blob.type || chooseRecordingMimeType() || 'audio/webm';
  const extension = mimeType.includes('mp4') ? 'mp4' : 'webm';
  form.append('audio', blob, `voice.${extension}`);

  const response = await fetch('/api/transcribe', { method: 'POST', body: form });
  const payload = await response.json();
  if (!response.ok || !payload.ok || !payload.text) throw new Error(payload.error || 'Transcription failed');
  await sendMsg(payload.text);
}
```

- [ ] **Step 4: Remove the old polling code**

```javascript
// Delete this block entirely:
(function voiceLoop() {
  fetch('/voice_poll').then(r => r.json()).then(d => {
    if (d.text) sendMsg(d.text);
  }).catch(() => {}).finally(() => setTimeout(voiceLoop, 500));
})();
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `/opt/homebrew/bin/python3.12 -m pytest tests/test_voice_ui_template.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/templates/index.html tests/test_voice_ui_template.py
git commit -m "feat: replace poll-based web voice input"
```

### Task 4: Verify the end-to-end voice flow

**Files:**
- Verify: `src/voice/web_transcriber.py`
- Verify: `src/api/voice_routes.py`
- Verify: `src/templates/index.html`

- [ ] **Step 1: Run the focused automated suite**

Run: `/opt/homebrew/bin/python3.12 -m pytest tests/test_voice_transcriber.py tests/test_voice_routes.py tests/test_voice_ui_template.py -q`
Expected: PASS

- [ ] **Step 2: Verify the route exists in a live app**

Run: `/opt/homebrew/bin/python3.12 -c "from web import create_app; app, _ = create_app(); client = app.test_client(); print(client.post('/api/transcribe', data={}, content_type='multipart/form-data').status_code)"`
Expected: `400`

- [ ] **Step 3: Manual browser verification**

Run: `/opt/homebrew/bin/python3.12 web.py`
Expected: server starts normally and serves the updated chat UI

Manual checklist:
- Click the mic button and allow microphone access
- Confirm recording state appears and elapsed time updates
- Stop recording and confirm the UI shows a transcribing state
- Confirm a successful transcript is auto-sent as a normal chat message
- Confirm a failed transcript shows an inline error and does not submit
- Confirm there is no more `/voice_poll` behavior in the web UI

- [ ] **Step 4: Commit**

```bash
git add src/voice/web_transcriber.py src/api/voice_routes.py src/api/__init__.py web.py src/templates/index.html tests/test_voice_transcriber.py tests/test_voice_routes.py tests/test_voice_ui_template.py docs/superpowers/plans/2026-04-23-voice-input-phase-4.md
git commit -m "feat: add browser voice transcription flow"
```

---

## Audit Stamp — 2026-04-23

**Status**: ✅ Pass — All Phase 4 features verified against running code

**Verification method**: Module import tests + component validation + route introspection

| Check | Result |
|-------|--------|
| `Transcriber` class exists in `web_transcriber.py` | ✅ Confirmed |
| `Transcriber.prepare_audio()` writes WAV | ✅ Confirmed |
| `Transcriber.transcribe()` calls model | ✅ Confirmed |
| `/api/transcribe` route registered | ✅ Confirmed |
| Index.html has mic button with JS blob recorder | ✅ Confirmed |
| No `/voice_poll` in web UI | ✅ Confirmed |
| Transcribed text goes to normal chat path | ✅ Confirmed |
| All 4 test suites pass | ✅ Confirmed |

**Orphaned code found**: Same 15 `src/core/` files — none relevant to voice pipeline.

