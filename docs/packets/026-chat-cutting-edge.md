# 026 — Chat Cutting Edge

**Status:** In Progress
**Goal:** Make Kitty's chat worth opening instead of Claude/ChatGPT/OpenHuman — every day, first reach.

## Problem

Kitty's backend is strong (8-store memory graph, proactive experts, goal tracking, model routing). But the chat UI doesn't surface any of it. Users see a plain markdown stream with no reasoning, no memory visibility, no goal awareness, no proactive notifications. The backend knows things the frontend can't show.

## Features (execution order)

### Wave 1 — Backend foundations (parallel, no file conflicts)

| # | Feature | Files | What |
|---|---------|-------|------|
| 1a | Reasoning blocks in stream | `completions.py`, `chat-client.ts` | Pass thinking/reasoning blocks through SSE; parse in frontend |
| 1b | Thread-scoped goals (storage) | `chats_store.py`, `routes/chats.py` | Add `objective` column to chat sessions; CRUD endpoints |
| 1c | Memory items in response | `routes/completions.py` | Return `memory_items` alongside streamed content via trailer event |

### Wave 2 — Frontend rendering (sequential, shared files)

| # | Feature | Files | What |
|---|---------|-------|------|
| 2a | Reasoning display component | `ChatMessage.tsx`, `types.ts`, `chat-client.ts` | Collapsible thinking block on messages |
| 2b | Memory visibility overlay | `ChatMessage.tsx`, `types.ts` | "Kitty remembered..." collapsible section |
| 2c | Thread goal header | `page.tsx`, `types.ts`, `TopBar.tsx` | Goal/objective display + edit in thread header |
| 2d | SSE event listener | New: `lib/sse.ts`, `components/SignalCard.tsx` | Persistent EventSource for expert signals + deadline alerts |

### Wave 3 — Integration + polish

| # | Feature | Files | What |
|---|---------|-------|------|
| 3a | Proactive signal cards | `page.tsx`, `SignalCard.tsx` | Expert signals render as notification cards in chat |
| 3b | Goal progress sidebar | `Rail.tsx` or `SessionSidebar.tsx` | Projects/deadlines/TELOS visible per-thread |
| 3c | Memory correction inline | `ChatMessage.tsx`, `gateway.ts`, memory API | "That's wrong" → update memory from chat |
| 3d | Multi-model per-message | `InputBar.tsx`, `TopBar.tsx` | Override model for a single message |

## Architecture decisions

- **Reasoning blocks**: Use OpenAI-compatible `thinking` content blocks in SSE delta. LiteLLM already proxies these for Claude; just stop filtering them out.
- **Memory trailer**: After `[DONE]`, emit a `data: {"memory_items": [...]}` event. Frontend collects it post-stream.
- **Thread goals**: `objective TEXT` column on `chat_sessions`. Injected into system prompt via `assemble_context()`.
- **SSE listener**: Single persistent EventSource to `/events` (already exists as `gateway/sse.py`). Frontend reconnects on drop.
- **Memory correction**: `PUT /memories/{id}` already exists. Add inline UI trigger.

## What's NOT in scope

- TokenJuice (tool output compression) — Kitty doesn't have heavy tool sprawl
- Meeting agents — different product surface
- Workflow canvas — overkill for personal use
