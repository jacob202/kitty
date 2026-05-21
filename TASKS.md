# Tasks

Last updated: **2026-05-21**

## Current test baseline

`python3.11 -m pytest tests/ -q --tb=short`  → **311 passed, 2 skipped**

---

## Phase 1 — Companion architecture foundation ✅ COMPLETE

- [x] **1.1 Collapse context layers** — `memory_graph.unified_context()` queries all 4 stores concurrently; wired into every LLM call via `context_builder.py`.
- [x] **1.2 Companion voice wired** — `voice_gate.py` filters banned phrases; `self_review.py` drift injected into system prompt when threshold exceeded.
- [x] **1.3 Persistent voice channel** — `voice_session.py` WebSocket handler with 20-turn history; route `/voice` live in `app.py`.
- [x] **1.4 Buddy / mascot** — `gateway/buddy.py` persistent mood state + `/mood` endpoint; UI polls gateway; `MoodAvatar` in TopBar renders live state.

---

## Phase 2 — Plumbing & persistence ✅ COMPLETE

- [x] **2.1 Route chat through gateway** — proxy default fixed to `:5001`; `/api/chat/completions` alias wires `streamChat` through `context_builder` + `voice_gate`.
- [x] **2.2 Background brief** — `_brief_bg_loop` in `lifespan` warms cache on startup, refreshes every 15 min; `/brief` now instant.
- [x] **2.3 Persistent chats** — `GET/POST/DELETE /chats` backed by `data/kitty/chats.json`; loads on mount, saves after stream, deletes on close.
- [x] **2.4 Agent task UI** — `TaskPanel.tsx` in BriefPanel sidebar; type selector, goal input, live status polling every 3s, cancel button.
- [x] **2.5 Telegram bot** — wired in lifespan; 7 tests passing; supports `/brief`, `/stuck`, `/help`, plain chat.

---

## Phase 3 — External world context (active)

- [x] **3.1 Calendar** — `gateway/calendar.py` reads macOS Calendar via AppleScript; wired into `context_builder.py` and `brief.py`; BriefPanel shows today's events.
- [x] **3.2 Ambient context** — `gateway/ambient.py` detects active macOS app; injected into context builder step 6; opt-in via `KITTY_AMBIENT_ENABLED=1`.
- [x] **3.3 Nudge engine** — `gateway/nudge.py` checks repeated research, dropped threads, milestones; injected into context builder step 7; `/nudges` + dismiss endpoint live.
- [x] **3.4 Weather** — `gateway/weather.py` hits wttr.in/Regina (30-min cache); `/weather` endpoint; injected into context builder step 5.5 and brief; RightBar shows live temp+conditions.
- [x] **3.5 iMessage context** — `get_recent_text()` added to `imessage.py`; injected into context builder step 5.7 (macOS only, silent fallback).
- [x] **3.6 Todos in context** — `get_todos_text()` added to `todo_store.py`; injected into context builder step 5.6 and brief.
- [x] **3.7 Health summary** — `get_health_text()` added to `health_parser.py`; injected into context builder step 5.8 (reads cached Apple Health export).

---

## Phase 4 — Wiring existing scaffolding (most already built)

These modules have endpoints in app.py but are fully disconnected from context/brief:

| Module | Endpoint(s) | What's missing |
|---|---|---|
| `web_monitor.py` | `/monitor/*` | Not surfaced in UI or context |
| `patterns.py` | `/patterns/weekly`, `/patterns/annual` | Not in brief or context |
| `builder.py` | `/build/*` | No UI surface in kitty-chat |
| `researcher.py` | `/research/deep` | No UI trigger |
| `learning.py` | `/learn` | No UI trigger |
| `cron.py` | `/cron/*` | No UI for scheduling |
| `image_gen.py` | `/image/*` | No UI |
| `tts.py` | `/v1/audio/speech` | ✅ Wired — voice toggle in InputBar, auto-plays responses |
| `stt.py` | `/v1/audio/transcriptions` | ✅ Wired — mic button in InputBar, transcribes to text |
| `skills/` | `/skills`, `/skill/*` | Not surfaced in UI |
| `agents.py` | `/agent/*` | No UI to spawn/monitor agents |

---

## Phase 5 — Untested / dead scaffolding (audit & decide keep or delete)

These modules exist, have no routes, and no tests. Evaluate each:
`agent_summarizer`, `agentic_mode`, `context_compactor`, `memory_consolidation`,
`onboarding`, `task_boundary`, `team_protocol`, `smoke_eval`, `specialist_router`,
`eval_domain`, `eval_runner`, `async_feedback`, `autonomy_state`, `base_tool`,
`antigravity_tools`, `chat_import`, `import_openwebui_prompts`, `ingest_policy`

---

## Next Smallest Action

Phase 4 STT/TTS done. Next: wire **`researcher.py`** (`/research/deep`) into TaskPanel as a "research" task type — already exists, just needs a UI path.
