# Voice Input Design

## Goal

Replace the current polling-based voice input path with a proper browser mic flow that records audio in the web UI, sends it to the server for `faster-whisper` transcription, and routes the returned text through the normal chat message path.

## Scope

This phase covers speech-to-text input only.

Included:
- Mic button in the existing chat composer
- Browser recording via `MediaRecorder`
- `POST /api/transcribe` endpoint for audio uploads
- Server-side transcription through `faster-whisper`
- Auto-send of transcribed text as a normal chat message
- Visible UI states for recording, transcribing, and failure
- Removal of the current `voiceLoop()` and `/voice_poll` web dependency

Excluded:
- Spoken replies by default
- Background listening
- Wake-word activation
- Dual support for both poll-based and browser-based voice flows

## Why This Approach

The current voice path is tied to file-drop polling and hidden browser polling loops, which is fragile on mobile and conceptually separate from the real chat flow. The new design keeps voice as just another input method for chat. That reduces moving parts, reuses the existing message pipeline, and keeps the first pass focused on the highest-value improvement.

## User Experience

The voice experience should behave like this:

1. The user taps the mic button in the composer.
2. The UI switches to a clear recording state and shows elapsed time.
3. The user taps again to stop recording.
4. The UI uploads the recorded blob and shows a transcribing state.
5. If transcription succeeds, the returned text is sent as a normal chat message automatically.
6. If transcription fails, the UI shows an inline error and does not send anything.

First-pass constraints:
- Maximum recording length is 60 seconds.
- Voice input is explicit start/stop only.
- The text composer remains available before and after voice submission.
- Empty transcripts are treated as no-op with a visible error or notice.

## Architecture

The design introduces one browser path and one server path.

### Browser Path

- The existing chat UI gets a mic button near the composer.
- Recording uses `navigator.mediaDevices.getUserMedia()` plus `MediaRecorder`.
- The frontend should choose a preferred `mimeType` when constructing `MediaRecorder`, preferring browser-supported formats in this order: `audio/webm`, then `audio/mp4`, then the browser default if neither can be requested explicitly.
- Audio chunks are collected client-side and combined into a `Blob`.
- The blob is uploaded to `POST /api/transcribe` using `multipart/form-data`.
- On success, the returned transcript is passed into the same send-message flow used by typed messages.

### Server Path

- A new `POST /api/transcribe` route receives one uploaded audio file.
- The route validates the upload, writes it to a temporary file, calls a small transcription service, returns JSON, and deletes the temp file in a `finally` block.
- A dedicated transcription helper owns `faster-whisper` initialization and inference so route code stays thin.
- The route is independent from `CoreOrchestrator`, `voice_poll`, CLI voice sessions, and file-drop watchers.

## Component Boundaries

### Frontend Voice Controller

Responsibility:
- Manage mic permission, start/stop recording, upload lifecycle, and UI state

Inputs:
- User clicks
- Browser microphone permission state
- `/api/transcribe` response

Outputs:
- UI status changes
- Normal chat submission with transcript text

### Transcription Route

Responsibility:
- Validate request, persist temp audio, call transcription service, return JSON

Inputs:
- Multipart audio upload

Outputs:
- JSON response with transcript metadata or error

### Transcription Service

Responsibility:
- Lazily load `faster-whisper`
- Run transcription with stable defaults
- Normalize transcript output for the route layer

Inputs:
- Temporary audio file path

Outputs:
- Transcript text, language, and optional timing metadata

## API Contract

### `POST /api/transcribe`

Request:
- `multipart/form-data`
- Field name: `audio`
- Accepted recording formats for first pass: `audio/webm` and `audio/mp4`
- Optional metadata fields if useful later, but not required for first pass

Successful response:

```json
{
  "ok": true,
  "text": "replace the capacitor on the left channel",
  "language": "en",
  "duration_seconds": 4.2
}
```

Failure response:

```json
{
  "ok": false,
  "error": "Transcription failed"
}
```

Rules:
- Reject missing files with `400`
- Reject uploads outside the accepted first-pass recording formats with `400`
- Reject oversized uploads with `413`
- Return `500` only for true server-side failures

Format note:
- Safari/iOS commonly records as `audio/mp4`
- Chromium browsers commonly record as `audio/webm`
- The server should accept both formats and rely on `ffmpeg` compatibility underneath `faster-whisper`

## Error Handling

### Frontend

- If microphone permission is denied, show a clear inline error and leave text chat usable.
- If recording startup fails, reset the mic button to idle and show an error.
- If upload fails, show a transcription failure message and do not send a chat message.
- If the server returns empty text, do not auto-send.
- If the user records again immediately after a failure, the previous error state should clear.

### Backend

- Validate content type and file presence before writing temp files.
- Enforce a maximum upload size consistent with the 60-second first-pass limit.
- Always remove temp files even when transcription errors occur.
- Time-box transcription so the route does not hang indefinitely.
- Log actionable errors on the server, but return compact messages to the UI.

## Migration Plan

- Remove the web UI `voiceLoop()` polling behavior.
- Stop depending on `/voice_poll` for browser voice input.
- Keep old CLI voice functionality untouched.
- Treat the new browser voice path as the only supported web voice input.

## Testing Strategy

### Automated

- Unit tests for the transcription service:
  - successful transcript extraction
  - empty transcript handling
  - model failure handling
  - temp-file cleanup behavior

- API tests for `POST /api/transcribe`:
  - missing file
  - unsupported content type
  - oversized upload
  - successful transcript JSON shape

- Frontend behavior tests where practical:
  - idle -> recording -> transcribing -> idle transitions
  - auto-send on success
  - visible error on failure

### Manual

- Desktop browser recording
- iPhone recording and permission prompts
- Repeated recordings in one session
- Recording followed by normal typed message
- Keyboard and composer remain usable after voice send

## Deferred Work

These are intentionally deferred until the input path is stable:
- Spoken replies through Piper or `say`
- Playback controls
- Interrupting or cancelling in-flight TTS
- Hold-to-record
- Conversation-aware voice settings

## Success Criteria

This phase is complete when:
- The web UI has a working mic button
- A recorded clip can be transcribed through `/api/transcribe`
- The transcript is sent through the normal chat path automatically
- Poll-based browser voice behavior is no longer required
- Errors are visible instead of silent

---

## Audit Stamp — 2026-04-23

**Status**: ✅ Verified — Design spec matches implementation

**Verification method**: Cross-referenced spec requirements against `web_transcriber.py`, `voice_routes.py`, `index.html`

| Requirement | Implementation Status |
|-------------|----------------------|
| Mic button in web UI | ✅ Present in `index.html` |
| Blob-based recording (JS) | ✅ `startRecording()` / `stopRecording()` |
| POST `/api/transcribe` | ✅ Route registered in `voice_routes.py` |
| Server-side transcription | ✅ `Transcriber.transcribe()` in `web_transcriber.py` |
| Auto-send as chat message | ✅ Returned transcript sent via normal chat path |
| No `/voice_poll` | ✅ Confirmed absent |
| Visible errors | ✅ Inline error display in UI |

**Deferred items (intentionally not implemented)**: Spoken replies, playback controls, hold-to-record, conversation-aware voice settings.
