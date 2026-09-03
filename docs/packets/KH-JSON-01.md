# KH-JSON-01 — Response filtering leaves the HTTP transport correct

**Initiative:** `kitty-hardening-response-filter-20260903-v1`
**Owner:** Builder after explicit operator activation
**Default route:** free; no `policy.routing` pin
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`
**Status:** authored only — not applied, queued, or dispatched

## What Jacob can do after this
Jacob can receive filtered Kitty responses without corrupted Content-Length, global response buffering, or transport-layer rewriting of unrelated JSON.

## Verified finding
`VoiceGateMiddleware` currently consumes every `application/json` response body, may rewrite text, then reconstructs the response with the original headers. When content changes, the original Content-Length can be wrong. The middleware also buffers every qualifying response globally even though `filter_response` is already called explicitly by voice, Telegram, and `/ask` generation paths.

## Objective
This packet creates no new files. Remove personality/voice cleanup from the global HTTP transport layer. First add a regression proving the stale Content-Length/body-reconstruction bug. Move `filter_response` to the smallest shared generation boundary that still covers the non-stream chat/completion path not already filtering explicitly; preserve existing filtering for `/ask`, voice, and Telegram without double-filtering. Remove `VoiceGateMiddleware` registration once every intended generation path is explicit. Streaming SSE responses must remain streaming and must not be buffered for filtering. Preserve status codes, cookies/background tasks, response headers, and non-LLM JSON byte-for-byte. If a common generation helper already provides the necessary boundary on current main, extend it rather than adding another middleware/helper.

## Intended files / fence
- `gateway/app.py`
- `gateway/voice_middleware.py`
- `gateway/voice_gate.py`
- `gateway/routes/ask.py`
- `gateway/routes/completions.py`
- `gateway/voice_pipeline.py`
- `gateway/telegram_bot.py`
- `tests/test_voice_gate.py`
- `tests/test_ask_endpoint.py`

This is a deliberate edit-only fence: the executable objective says `creates no new files` If a new module/test becomes necessary, stop and revise the manifest first.

## Acceptance criteria
1. No global middleware buffers and reconstructs arbitrary JSON responses for voice/personality cleanup.
2. Non-stream generated assistant text is filtered exactly once at a generation boundary.
3. SSE/streaming completion responses remain streaming and are not collected into memory for filtering.
4. Non-LLM JSON responses preserve their original body, status, and headers.
5. A regression demonstrates that filtering cannot leave a stale Content-Length header.
6. Existing `/ask`, voice, and Telegram filtering behavior remains covered.

## Verification
**Tier 1 — Builder mechanical.** These are the only commands Builder runs:
- `python -m pytest -q tests/test_voice_gate.py tests/test_ask_endpoint.py`
- `python -m ruff check gateway/app.py gateway/voice_gate.py gateway/routes/ask.py gateway/routes/completions.py gateway/voice_pipeline.py gateway/telegram_bot.py tests/test_voice_gate.py tests/test_ask_endpoint.py`

**Tier 2 / Tier 3.** Tier 2: live non-stream completion + ordinary JSON route + SSE probe, confirming no response framing mismatch and no buffering-induced stream delay. Tier 3 not required if visible text is unchanged; if wording changes, independent PA is required.

Current-green tests are baseline only. The implementation must add or strengthen at least one regression that fails on `70c15583a6afa4aac9a6f6eb11abf840afa377a4` for the verified finding before production edits.

## Failure modes that must be tested
- The original review reproduction is a required RED case, not prose-only evidence.
- Dependency/service unavailable paths stay truthful; UNKNOWN never becomes success.
- Cancellation/timeout/partial input cannot leave a false success receipt.
- The fix must preserve the existing security/authority boundary named in the objective.

## Stop condition
If filtering streamed tokens would require buffering the whole stream or changing token semantics, leave streaming text unfiltered and document the boundary instead of degrading streaming.

## Recovery / restartability
Removing middleware must be reversible in one commit; no persistent state or schema changes.

## Dedupe / ownership guard
Before activation, re-read `workspace_global`, GitHub issue #490, current Git/PR state, and Builder task ownership. If current `main` already contains an equivalent fix or another live lane owns any implementation path, stop and reconcile rather than creating competing work. This packet never authorizes push, PR creation, merge, paid spend, credential mutation, or edits under `data/`.
