# Gemini / Kitty UI Harvest - 2026-04-27

## Scope

Reviewed local Gemini/LLM and Kitty UI notebook-style materials for reusable code, architecture notes, and cleanup decisions.

Searched:

- `/Users/jacobbrizinski/Documents/Kitty`
- `/Users/jacobbrizinski/Projects/kitty`
- broader `Documents`, `Desktop`, and `Downloads` paths for notebook/UI/Gemini filenames

No `.ipynb` notebook matching Kitty UI was found locally during this pass. The strongest local "notebook" equivalent is `docs/phase3b_ui_rebuild_guide.md`.

The Gemini share link `https://gemini.google.com/app/81b5438e3f428df4` was also checked directly. Both plain web fetch and browser automation reached Gemini's sign-in / zero-state page, not the shared conversation content, so no notebook text could be harvested from the link in this environment.

## Useful Sources Found

| Source | Keep / Use | Notes |
| --- | --- | --- |
| `src/api/web_llm.py` | Use | Live web-safe fallback client for OpenRouter/Anthropic streaming into `SpecialistResponse`. |
| `src/space_kitty/llm_client.py` | Use | Most complete current LLM client: OpenRouter first, Anthropic explicit fallback, native MLX fallback, budget tracking, circuit breaker, rate limiter, provider health. |
| `src/utils/resilient_llm_client.py` | Mine patterns | Good generic retry/fallback wrapper, but overlaps with `src/space_kitty/llm_client.py`; avoid adding another live LLM path unless consolidating. |
| `src/voice/gemini_voice.py` | Archive/hold | Placeholder for Gemini TTS; explicitly notes Gemini native TTS was not available when written. Do not build around it as a current source of truth without verification. |
| `src/tools/superpowers/GEMINI.md` | Ignore for runtime | Just tool instruction includes; not Kitty app logic. |
| `docs/phase3b_ui_rebuild_guide.md` | Use | High-value UI streaming notes: SocketIO/SSE coexistence, circular import pitfalls, busy-lock edge, TokenCapture behavior, verification checklist. |
| `garage-ui/app/page.tsx` | Review/fix next | Live UI currently streams via `EventSource` in `executeCommand()` while also maintaining SocketIO telemetry. This conflicts with the Phase 3B guide's "client only uses SocketIO" statement. |
| `garage-ui/app/components/ChatInterface.tsx` | Keep | Clean chat surface with mascot state, markdown rendering, source pills, empty states, and voice button wiring. |

## Harvested Decisions

1. Keep `src/space_kitty/llm_client.py` as the primary LLM spine for specialist/runtime calls. It already has the important pieces: local MLX fallback, provider health, spend tracking, rate limiting, and circuit breakers.
2. Keep `src/api/web_llm.py` as the web-only fallback, but do not duplicate its provider logic elsewhere.
3. Treat `src/utils/resilient_llm_client.py` as a pattern library unless/until the LLM stack is consolidated. It is good code, but another live path increases drift.
4. Treat `docs/phase3b_ui_rebuild_guide.md` as the UI streaming architecture notebook. It contains the critical SocketIO migration warnings and import-cycle rules.
5. Do not treat `src/voice/gemini_voice.py` as finished Gemini TTS. It is a gTTS placeholder with a future-facing name.

## Issues Found To Fix Later

### 1. Frontend streaming architecture drift

`docs/phase3b_ui_rebuild_guide.md` says the client should use SocketIO for chat tokens and that SSE remains server-side fallback only. The live `garage-ui/app/page.tsx` still uses:

```ts
const eventSource = new EventSource(`http://${backendHost}:5001/stream?query=${encodeURIComponent(command)}`);
```

This may be intentional drift, but it should be decided explicitly:

- Option A: keep SSE for chat and update/remove stale SocketIO migration docs.
- Option B: move `executeCommand()` to SocketIO `send_message` and use the guide's checklist as the implementation source.

### 2. Browser voice MIME handling is Chrome-only

`garage-ui/app/page.tsx` creates the recorder with `audio/webm` unconditionally:

```ts
const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
```

Safari/iOS generally needs `audio/mp4`. Use MIME preference detection before creating the recorder.

### 3. LLM client duplication

There are at least three LLM paths:

- `src/api/web_llm.py`
- `src/space_kitty/llm_client.py`
- `src/utils/resilient_llm_client.py`

The useful consolidation direction is:

- runtime specialists -> `src/space_kitty/llm_client.py`
- web fallback -> `src/api/web_llm.py`
- generic retry/circuit patterns -> migrate into the active paths, then archive `src/utils/resilient_llm_client.py` if it has no live imports.

## Recommended Next Patch

Smallest high-value patch:

1. Fix MediaRecorder MIME detection in `garage-ui/app/page.tsx`.
2. Add a short UI-streaming decision note to `docs/phase3b_ui_rebuild_guide.md` or a new current-state doc.
3. Add a reference test or lint-safe helper if frontend test tooling is available.

## If The Gemini Chat Is Needed

Use one of these paths:

1. Open the Gemini conversation in a signed-in browser and use Gemini's share/export/copy option to save the full text into `docs/imports/gemini-kitty-ui.md`.
2. Paste the chat text into a local `.md` file in this repo.
3. If browser automation should access it directly, first sign into Gemini in the automation browser session, then rerun:

```bash
agent-browser open "https://gemini.google.com/app/81b5438e3f428df4"
agent-browser snapshot -i -u
```
