# Tasks

Last updated: **2026-06-18**

## Current test baseline

`python3.11 -m pytest tests/ -q --tb=short` → **500 passed, 2 deselected** (after Phase A A1+A4 cleanup, stale council tests removed, and doctor/auth/launcher regressions covered)

`cd gateway/kitty-chat && npm test` → **36 passed**

---

## UI home surface

- **DashboardHome** is the canonical home view (`BriefPanel` removed).
- Bootstraps: brief, todos, weather (`/weather`), loops, insights.
- **RightPanel** (formerly RightBar) stays on the right rail.

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
- [x] **2.4 Agent task UI** — `TaskPanel.tsx` on tasks rail; type selector, goal input, live status polling every 3s, cancel button.
- [x] **2.5 Telegram bot** — wired in lifespan; 7 tests passing; supports `/brief`, `/stuck`, `/help`, plain chat.

---

## Phase 3 — External world context ✅ COMPLETE

- [x] **3.1 Calendar** — `gateway/calendar_integration.py` reads macOS Calendar via AppleScript; wired into `context_enrichment.py` and `brief.py`.
- [x] **3.2 Ambient context** — `gateway/ambient.py` detects active macOS app; injected into context builder step 6; opt-in via `KITTY_AMBIENT_ENABLED=1`.
- [x] **3.3 Nudge engine** — `gateway/nudge.py` checks repeated research, dropped threads, milestones; injected into context builder step 7; `/nudges` + dismiss endpoint live.
- [x] **3.4 Weather** — `gateway/weather.py` hits wttr.in/Regina (30-min cache); `/weather` endpoint; injected into context enrichment and brief; DashboardHome BriefStrip shows live temp+conditions.
- [x] **3.5 iMessage context** — `get_recent_text()` added to `imessage.py`; injected into context builder step 5.7 (macOS only, silent fallback).
- [x] **3.6 Todos in context** — `get_todos_text()` added to `todo_store.py`; injected into context builder step 5.6 and brief.
- [x] **3.7 Health summary** — `get_health_text()` added to `health_parser.py`; injected into context builder step 5.8 (reads cached Apple Health export).

---

## Phase 4 — Wiring existing scaffolding ✅ COMPLETE

| Module | Status |
|---|---|
| `web_monitor.py` | ✅ MonitorPanel.tsx shows live monitors, add/remove form |
| `patterns.py` | ✅ Behavioral patterns injected into context builder (step 6.5) |
| `builder.py` | ✅ Surfaced via TaskPanel "build" task type |
| `researcher.py` | ✅ Surfaced via TaskPanel "research" task type |
| `learning.py` | ✅ Learning stats injected into context builder (step 6.6) |
| `cron.py` | ✅ Started in lifespan alongside brief bg loop |
| `image_gen.py` | ⏭ Skip — needs local ComfyUI, low priority |
| `tts.py` | ✅ Voice toggle in InputBar, auto-plays responses |
| `stt.py` | ✅ Mic button in InputBar, transcribes to text |
| `skills/` | ✅ RightPanel shows up to 6 skills + overflow count |
| `agents.py` | ✅ RightPanel shows up to 5 agents |

---

## Phase 5 — Dead scaffolding audit ✅ COMPLETE

**Deleted** (0 imports, 0 routes, 0 tests):
`agent_summarizer`, `agentic_mode`, `base_tool`, `chat_import`,
`context_compactor`, `import_openwebui_prompts`, `ingest_policy`,
`memory_consolidation`, `onboarding`, `specialist_router`

**Kept** (actively imported or have tests):
`eval_runner` (routes in app.py), `eval_domain` (used by smoke_eval),
`smoke_eval` (eval cluster), `autonomy_state` (used by agent_runner),
`task_boundary` / `async_feedback` / `team_protocol` (used by antigravity_tools + tests),
`antigravity_tools` (has test_antigravity_tools.py)

---

## Next

All phases complete. Possible future work:
- Image generation UI when ComfyUI is available
- Cron schedule editor UI (currently runs silent background jobs)
- Memory consolidation / dream loop using `memory_consolidation.py` patterns
