# KH-VOICE-01 — Voice WebSocket has authenticated bounded multi-turn semantics

**Initiative:** `kitty-hardening-voice-ws-20260903-v1`
**Owner:** Builder after explicit operator activation
**Default route:** free; no `policy.routing` pin
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`
**Status:** authored only — not applied, queued, or dispatched

## What Jacob can do after this
Jacob can use a voice session that keeps conversational context, rejects unauthenticated clients, bounds every audio turn, and closes normally without spurious session errors.

## Verified finding
The review reproduced four defects in `gateway/voice_pipeline.py`: `/voice` accepted an unauthenticated WebSocket despite a configured Gateway secret; binary frames bypassed `MAX_VOICE_BYTES`; `_handle_audio_bytes()` called `process_turn(audio)` without the session so prior turns were discarded; and a normal `websocket.disconnect` event could be followed by another `receive()`, producing a RuntimeError and error log.

## Objective
This packet creates no new files. Harden the existing `/voice` WebSocket rather than creating a second realtime voice path. Authenticate the handshake using the existing Gateway secret contract in a way compatible with current non-browser clients; do not put bearer secrets in URL query strings. Reject before `accept()` when auth fails. Enforce `MAX_VOICE_BYTES` (or a more specific existing voice cap) on every binary turn before STT. Pass the current `VoiceSessionState` into `process_turn` so bounded history is actually used. Handle Starlette disconnect events as normal closure and preserve the existing ping/mode control messages. Add explicit validation for unknown control-message shapes and mode values without making old valid clients fail. If a browser WebSocket client is introduced, it must go through a same-origin authenticated proxy or another reviewed credential mechanism; this packet must not expose the Gateway secret to browser JavaScript.

## Intended files / fence
- `gateway/routes/voice.py`
- `gateway/voice_pipeline.py`
- `gateway/auth.py`
- `gateway/constants.py`
- `tests/test_voice_gateway.py`
- `tests/test_upload_limits.py`

This is a deliberate edit-only fence: the executable objective says `creates no new files` If a new module/test becomes necessary, stop and revise the manifest first.

## Acceptance criteria
1. Unauthenticated `/voice` handshakes are rejected when Gateway authentication is configured.
2. A binary voice turn larger than the configured cap is rejected before STT is invoked.
3. The second voice turn receives the first user/assistant turn in its session context and history remains capped.
4. A normal websocket.disconnect ends the session without logging or returning a session error.
5. Ping and valid mode control messages remain backward compatible; malformed controls fail safely.
6. No credential is accepted from a URL query parameter and no Gateway secret is exposed to browser-side code.

## Verification
**Tier 1 — Builder mechanical.** These are the only commands Builder runs:
- `python -m pytest -q tests/test_voice_gateway.py tests/test_upload_limits.py`
- `python -m ruff check gateway/routes/voice.py gateway/voice_pipeline.py gateway/auth.py tests/test_voice_gateway.py tests/test_upload_limits.py`

**Tier 2 / Tier 3.** Tier 2: authenticated and unauthenticated live WebSocket probes plus a two-turn context probe. Tier 3: independent reviewer verifies normal disconnect, oversize rejection, and no secret appears in request URLs/log output.

Current-green tests are baseline only. The implementation must add or strengthen at least one regression that fails on `70c15583a6afa4aac9a6f6eb11abf840afa377a4` for the verified finding before production edits.

## Failure modes that must be tested
- The original review reproduction is a required RED case, not prose-only evidence.
- Dependency/service unavailable paths stay truthful; UNKNOWN never becomes success.
- Cancellation/timeout/partial input cannot leave a false success receipt.
- The fix must preserve the existing security/authority boundary named in the objective.

## Stop condition
If the only feasible browser authentication design requires putting the Gateway bearer token into client JavaScript, localStorage, cookies readable by JS, or the URL, stop and split a reviewed proxy design instead.

## Recovery / restartability
Session state is in memory and bounded; failed handshakes or turns must not persist partial messages or external effects.

## Dedupe / ownership guard
Before activation, re-read `workspace_global`, GitHub issue #490, current Git/PR state, and Builder task ownership. If current `main` already contains an equivalent fix or another live lane owns any implementation path, stop and reconcile rather than creating competing work. This packet never authorizes push, PR creation, merge, paid spend, credential mutation, or edits under `data/`.
