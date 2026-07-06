# Kitty Architecture — Complete

**Last Updated:** 2026-05-25
**Status:** ✅ All Phases Complete

## System Overview

Kitty is a **local-first AI companion** with a FastAPI backend (`gateway/`) and Next.js frontend (`gateway/kitty-chat/`).

### Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                        │
│  - DashboardHome (Brief, Todos, Weather, Loops, Insights)  │
│  - RightPanel (Stats, Cron, Time, Model, Kitty status)     │
│  - SessionSidebar, TaskPanel, InputBar, TopBar            │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP / WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend (FastAPI - gateway/)                              │
│                                                             │
│  Routes (21 endpoints):                                    │
│  - /v1/chat/completions  → Main chat (with buddy hooks)   │
│  - /ask                  → Siri/script-friendly            │
│  - /voice (WS)           → Real-time voice conversation    │
│  - /search               → Unified cross-store search      │
│  - /loops                → Background task automation      │
│  - /insights             → Dream/consolidation output      │
│  - /monitors             → Web/page monitoring             │
│  - /cron/*               → Scheduled tasks                 │
│  - /todos/*              → Todo management                 │
│  - /tasks/*              → Task runner API                 │
│  - /calendar/*           → Calendar integration            │
│  - /brief, /weather      → Context enrichment              │
│                                                             │
│  Deep Modules:                                              │
│  - voice_pipeline.py     → STT → LLM → TTS → Gate         │
│  - memory_graph.py       → 5-store unified query           │
│  - buddy.py              → Mood/energy/drift tracking      │
│  - context_builder.py    → Prompt assembly                 │
│                                                             │
│  Store Adapters:                                            │
│  - Memory (mem0)        → Personal facts & patterns        │
│  - Knowledge (ChromaDB) → Document chunks                  │
│  - Journal (JSONL)      → Daily entries                    │
│  - Traces (JSONL)       → Activity logs                    │
│  - Todos (SQLite)       → Task list                        │
└─────────────────────────────────────────────────────────────┘
```

## Phase Completion Status

### ✅ Phase 1 — Companion Architecture Foundation
- [x] Unified context layers (`memory_graph.unified_context()`)
- [x] Companion voice with drift filtering
- [x] Persistent voice channel (WebSocket, 20-turn history)
- [x] Buddy mascot with live mood state

### ✅ Phase 2 — Plumbing & Persistence
- [x] Chat routed through gateway with context
- [x] Background brief refresh (15-min cache)
- [x] Persistent chats (JSON-backed)
- [x] Agent task UI with live polling
- [x] Telegram bot integration

### ✅ Phase 3 — External World Context
- [x] Calendar integration (macOS AppleScript)
- [x] Ambient context (active app detection)
- [x] Nudge engine (repeated research, milestones)
- [x] Weather (wttr.in, 30-min cache)
- [x] iMessage context (macOS)
- [x] Todos in context
- [x] Health summary (Apple Health export)

### ✅ Phase 4 — Wiring Existing Scaffolding
- [x] Web monitors → MonitorPanel
- [x] Patterns → Context injection
- [x] Builder/Researcher → Task types
- [x] Learning stats → Context
- [x] Cron scheduler → Background jobs
- [x] TTS/STT → Voice toggle in InputBar
- [x] Skills/Agents → RightPanel display

### ✅ Phase 5 — Dead Scaffolding Audit
- Deleted 9 unused modules
- Kept 12 actively-used modules

## Backend Enhancement Summary (2026-05-25)

### New Route Modules Created
1. **`/search`** — Unified cross-store search
   - Uses `memory_graph.search_all()`
   - Returns scored, flattened results

2. **`/loops`** — Background task loops
   - In-memory state (ready for cron integration)
   - Toggle on/off, create, delete

3. **`/insights`** — Dream/consolidation output
   - Integrates with `gateway.dream`
   - Dismiss functionality

4. **`/monitors`** — Web/page monitoring
   - Integrates with `gateway.web_monitor`
   - Create, delete, manual check

### Deep Module Pattern Applied

Modules like `voice_pipeline`, `memory_graph`, and `buddy` follow the **deep module principle**:

- **Small interface, large implementation**
- **Internal adapters hidden from callers**
- **Tests at the interface, not internal seams**

Example from `memory_graph.py`:
```python
# 5 store adapters internal
class MemoryAdapter, KnowledgeAdapter, JournalAdapter, TracesAdapter, TodosAdapter

# Deep interface
unified_context(query) -> str
search_all(query) -> dict
```

## Test Coverage

- **449 tests pass** (Python backend)
- **36 tests pass** (Frontend)
- **0 regressions** from architectural changes

## File Count

- **84 Python modules** in `gateway/`
- **21 route modules** in `gateway/routes/`
- **~50 React components** in `gateway/kitty-chat/src/components/`

## Next Steps

All phases from `TASKS.md` are complete. Future work:

1. **Image Generation UI** — When ComfyUI is available
2. **Cron Schedule Editor UI** — Currently runs silent
3. **Memory Consolidation UI** — Visual dream loop feedback
4. **Performance Optimization** — Token usage, query latency
5. **User Feedback Iteration** — Based on actual usage patterns

## Key Files

| File | Purpose |
|------|---------|
| `gateway/memory_graph.py` | Unified 5-store query with adapters |
| `gateway/voice_pipeline.py` | Deep voice pipeline (STT→LLM→TTS→Gate) |
| `gateway/buddy.py` | Mood/energy/drift tracking |
| `gateway/context_builder.py` | Prompt assembly with all context |
| `gateway/routes/completions.py` | Main chat with buddy hooks |
| `CLAUDE.md` | Deep module pattern documentation |
| `docs/ARCHITECTURE.md` | Live stack description |
| `docs/CONTEXT_ENGINEERING.md` | Context injection principles |
