# Tasks

Last updated: **2026-05-21**

## Current test baseline

`python3.11 -m pytest tests/ -q --tb=short`  → **306 passed, 2 skipped**

---

## Phase 1 — Companion architecture foundation ✅ COMPLETE

- [x] **1.1 Collapse context layers** — `memory_graph.unified_context()` queries all 4 stores concurrently; wired into every LLM call via `context_builder.py`.
- [x] **1.2 Companion voice wired** — `voice_gate.py` filters banned phrases; `self_review.py` drift injected into system prompt when threshold exceeded.
- [x] **1.3 Persistent voice channel** — `voice_session.py` WebSocket handler with 20-turn history; route `/voice` live in `app.py`.
- [x] **1.4 Buddy / mascot** — `gateway/buddy.py` persistent mood state + `/mood` endpoint; UI polls gateway; `MoodAvatar` in TopBar renders live state.

---

## Phase 2 — Plumbing & persistence (active)

- [x] **2.1 Route chat through gateway** — proxy default fixed to `:5001`; `/api/chat/completions` alias wires `streamChat` through `context_builder` + `voice_gate`.
- [x] **2.2 Background brief** — `_brief_bg_loop` in `lifespan` warms cache on startup, refreshes every 15 min; `/brief` now instant.
- [x] **2.3 Persistent chats** — `GET/POST/DELETE /chats` endpoints backed by `data/kitty/chats.json`; frontend loads on mount, saves after stream, deletes on close.
- [ ] **2.4 Agent tasks** — `task_runner.py` exists; need a UI surface to trigger + monitor background tasks from the dashboard.
- [x] **2.5 Telegram bot** — wired in lifespan; 7 tests passing; `TELEGRAM_BOT_TOKEN` documented in `.env.example`; supports `/brief`, `/stuck`, `/help`, plain chat.

---

## Next Smallest Action

Phase 2 complete. Start Phase 3: pick the highest-value external connection — calendar read (`GET /calendar/today`) or weather snapshot — and wire it into the morning brief.

---

## Phase 3+ (parked until Phase 2 is done)

External world: calendar read, email triage, weather, habit tracker. See `docs/UNIFIED_IMPLEMENTATION_PLAN.md`.
