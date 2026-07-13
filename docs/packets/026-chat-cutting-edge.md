# 026 — Chat Cutting Edge

**Status:** In Progress
**Goal:** Make Kitty's chat worth opening instead of Claude/ChatGPT/OpenHuman — every day, first reach.

## Problem

Kitty's backend is strong (8-store memory graph, proactive experts, goal tracking, model routing). But the chat UI doesn't surface any of it. Users see a plain markdown stream with no reasoning, no memory visibility, no goal awareness, no proactive notifications. The backend knows things the frontend can't show.

## Features (execution order)

### Wave 1 — Backend foundations (parallel, no file conflicts) ✅

| # | Feature | Files | What | Status |
|---|---------|-------|------|--------|
| 1a | Reasoning blocks in stream | `completions.py`, `chat-client.ts` | Pass thinking/reasoning blocks through SSE; parse in frontend | ✅ |
| 1b | Thread-scoped goals (storage) | `chat_lifecycle.py`, `routes/chats.py` | Add `objective` column to chat sessions; CRUD endpoints | ✅ |
| 1c | Memory items in response | `routes/completions.py` | Return `memory_items` alongside streamed content via trailer event | ✅ |

### Wave 2 — Frontend rendering (sequential, shared files)

| # | Feature | Files | What | Status |
|---|---------|-------|------|--------|
| 2a | Reasoning display component | `ChatMessage.tsx`, `types.ts`, `chat-client.ts` | Collapsible thinking block on messages | ✅ |
| 2b | Memory visibility overlay | `ChatMessage.tsx`, `types.ts` | "Kitty remembered..." collapsible section | ✅ |
| 2c | Thread goal header | `page.tsx`, `types.ts`, `TopBar.tsx` | Goal/objective display + edit in thread header | |
| 2d | SSE event listener | New: `lib/sse.ts`, `components/SignalCard.tsx` | Persistent EventSource for expert signals + deadline alerts | |

### Wave 3 — Integration + polish

| # | Feature | Files | What | Status |
|---|---------|-------|------|--------|
| 3a | Proactive signal cards | `page.tsx`, `SignalCard.tsx` | Expert signals render as notification cards in chat | |
| 3b | Goal progress sidebar | `Rail.tsx` or `SessionSidebar.tsx` | Projects/deadlines/TELOS visible per-thread | |
| 3c | Memory correction inline | `ChatMessage.tsx`, `gateway.ts`, memory API | "That's wrong" → update memory from chat | |
| 3d | Multi-model per-message | `InputBar.tsx`, `TopBar.tsx` | Override model for a single message | |
| 3e | Reasoning level config | `TopBar.tsx`, `completions.py` | Thinking depth knob (off/normal/deep) mapped to model-specific params | |

### Wave 4 — Kitty Reasoning Engine (KRE)

Native reasoning scaffold that wraps the model call — enhances quality, reduces waste.

| # | Feature | Files | What |
|---|---------|-------|------|
| 4a | Question classifier | `gateway/reasoning.py` | Classify complexity (trivial/medium/deep) before model dispatch |
| 4b | Pre-flight decomposition | `gateway/reasoning.py` | Break complex questions into sub-questions, frame the prompt better |
| 4c | Context sharpening | `context_assembler.py` | Score memory items for relevance, drop low-signal items before prompt |
| 4d | Post-flight self-review | `self_review.py` | Evaluate response quality, flag low-confidence answers |
| 4e | Adaptive model routing | `llm_client.py` | Trivial → cheap model; medium → default; deep → reasoning model |
| 4f | Token budget optimizer | `gateway/reasoning.py` | Track actual token use per complexity tier, tune routing thresholds |

**Design principle:** The reasoning engine works WITH the model, not against it. It doesn't replace the model's thinking — it reduces the garbage the model has to think about (sharper context) and catches mistakes after (self-review). Net effect: better answers for fewer tokens because the model isn't wading through irrelevant memory or poorly-framed prompts.

**Key insight:** Most of Jacob's questions don't need deep reasoning. The classifier routes trivial questions to fast/cheap models, saving reasoning budget for decisions, planning, and analysis where it actually matters. The Parts system already does something similar for decisions — KRE generalizes that.

## Architecture decisions

- **Reasoning blocks**: Use OpenAI-compatible `thinking` content blocks in SSE delta. LiteLLM already proxies these for Claude; just stop filtering them out.
- **Memory trailer**: After `[DONE]`, emit a `data: {"memory_items": [...]}` event. Frontend collects it post-stream.
- **Thread goals**: `objective TEXT` column on `chat_conversations`. Injected into system prompt via `assemble_context()`.
- **SSE listener**: Single persistent EventSource to `/events` (already exists as `gateway/sse.py`). Frontend reconnects on drop.
- **Memory correction**: `PUT /memories/{id}` already exists. Add inline UI trigger.
- **Reasoning level config**: Map UI knob to `thinking.budget_tokens` (Claude), `reasoning_effort` (OpenAI o-series). Pass through LiteLLM. Models without reasoning support → knob grayed out.
- **KRE classifier**: Lightweight heuristic + small model call. Must add <100ms to request latency. Runs before context assembly so it can influence memory retrieval depth.
- **Context sharpening**: Re-rank memory items by cosine similarity to the actual question (not just the retrieval query). Drop items below threshold. Saves 30-60% of memory tokens on average.

## What's NOT in scope

- TokenJuice (tool output compression) — Kitty doesn't have heavy tool sprawl
- Meeting agents — different product surface
- Workflow canvas — overkill for personal use
