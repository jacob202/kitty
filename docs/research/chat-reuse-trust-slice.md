# Chat Reuse Trust Slice — Reuse Ledger

Branch: `spike/chat-reuse-trust-slice`
Date: 2026-08-01

Every evaluated reusable component or pattern. Accepted candidates name the
Kitty code they replace or avoid. Rejected candidates name the authority gate
they failed.

---

## 1. @assistant-ui/react — thread primitives and runtime adapter

- **Source:** `@assistant-ui/react` npm package
- **Pinned version:** `0.14.28` (MIT)
- **License:** MIT
- **Files inspected:**
  - `dist/index.js` — full export surface
  - `dist/primitives/thread.js` — `ThreadPrimitive` family
  - `dist/legacy-runtime/runtime-cores/external-store/useExternalStoreRuntime.js`
  - `dist/context/react/ThreadViewportContext.js` — `useThreadViewport`
- **Kitty code avoided:**
  - `KittyThread.tsx` uses `ThreadPrimitive.Root`, `ThreadPrimitive.Viewport`,
    `ThreadPrimitive.Messages`, `ThreadPrimitive.Empty`, and
    `ThreadPrimitive.ScrollToBottom` instead of custom scroll/viewport logic.
  - `KittyRuntimeProvider.tsx` wraps `AssistantRuntimeProvider` instead of
    implementing an event-loop-based runtime dispatch.
  - `kitty-runtime.ts` implements `ExternalStoreAdapter<Message>` and delegates
    to `useExternalStoreRuntime` — Kitty owns message state, assistant-ui owns
    the runtime loop contract and viewport/scroll/smooth animation primitives.
- **Adapter boundary:** `useKittyRuntime(options: KittyRuntimeOptions)` returns
  an assistant-ui runtime from Kitty's `Message[]`, `isStreaming`, `onSend`,
  `onCancel`, and `onReload` callbacks. No assistant-ui-managed message store,
  thread store, or cloud adapter is used.
- **Authority kept by Kitty:**
  - Conversation state (messages, chat list, model selection)
  - Streaming lifecycle (start, cancel, retry)
  - Persistence (chats_store + chat_lifecycle ledger)
  - Provider/model routing
  - Memory, context, tools, permissions, and project scope
- **Implementation benefit:** ~400 lines of scroll/viewport/composer wiring
  avoided. The `ExternalStoreAdapter` contract is ~50 lines of adapter code.
- **Maintenance burden:** Low. Upstream publishes releases; the adapter
  surface (`useExternalStoreRuntime`, `ThreadPrimitive`) is stable public API.
  Version bumps are narrow (the `convertMessage` contract and a few exported
  names changed at 0.11 and 0.13; both are already absorbed).
- **Accepted:** Yes. Already integrated before this slice. This ledger entry
  records the existing dependency for completeness.
- **Kill condition:** Remove if assistant-ui changes license, drops
  `useExternalStoreRuntime`/`ThreadPrimitive`, or Kitty migrates to a different
  UI shell. Removal cost: reimplement ~200 lines of viewport/scroll primitives
  plus a ~50-line runtime adapter bridge. Measurable because the adapter file
  (`kitty-runtime.ts`) is the only contact surface.

---

## 2. LibreChat — rejected as full-application foundation

- **Source:** `danny-avila/LibreChat` GitHub repository
- **Pinned version:** `v0.7.7` (commit verified by PR #286 bootstrap)
- **License:** MIT
- **Authority gate failed:** Would introduce a second conversation store (MongoDB),
  a second memory system (MeiliSearch RAG), its own agent, MCP, and auth
  subsystems that duplicate Kitty authorities.
- **Kitty code it would replace:** Entire Next.js frontend, thread management,
  provider/preset management, and auth surfaces. The estimated replacement scope
  is the entire `gateway/kitty-chat/` tree (~15k LOC) plus several backend
  adapters.
- **Status:** **Rejected** for this slice and for Kitty's Chat surface.
- **Reference:** PR #286 proved bootability against Kitty's OpenAI-compatible
  endpoint. Full-application adoption was never claimed as the next step; it
  was a feasibility spike.
- **Kill condition:** N/A — not adopted.

---

## 3. AnythingLLM — rejected as full-application foundation

- **Source:** `Mintplex-Labs/anything-llm` GitHub repository
- **Pinned version:** `v1.7.7` (commit verified by PR #286 bootstrap)
- **License:** MIT
- **Authority gate failed:** Same class of duplication as LibreChat — its
  workspace model, dynamic routing, memory, agents, flows, scheduled jobs, and
  Gmail/calendar skills duplicate Kitty's context, memory, routing, and project
  authorities.
- **Kitty code it would replace:** Entire Next.js frontend plus several backend
  adapters.
- **Status:** **Rejected** for this slice and for Kitty's Chat surface.
- **Reference:** PR #286 proved bootability. Not a product-fit claim.
- **Kill condition:** N/A — not adopted.

---

## 4. @assistant-ui/react `useLocalRuntime` — not adopted

- **Source:** `@assistant-ui/react@0.14.28` `dist/legacy-runtime/runtime-cores/local/useLocalRuntime.js`
- **License:** MIT
- **Files inspected:** `dist/legacy-runtime/runtime-cores/local/useLocalRuntime.js`
- **Authority gate failed:** `useLocalRuntime` owns message state internally
  (branching, editing, regenerating). Kitty must own message state because
  persistence goes through the Kitty gateway (`chats_store` + lifecycle ledger),
  not a client-side store. Forking `useLocalRuntime` to inject Kitty's
  persistence adapter would create more code than the current
  `useExternalStoreRuntime` adapter.
- **Kitty code it would replace:** The message state management inside
  `KittyContext.tsx`'s `runStream`, `handleSend`, `handleRetry`.
- **Status:** **Rejected.** `useExternalStoreRuntime` is the correct adapter
  for Kitty's external message authority. `useLocalRuntime` would require
  maintaining a parallel message store the UI would need to reconcile.
- **Kill condition:** N/A — not adopted.

---

## 5. @assistant-ui/react `useRemoteThreadListRuntime` — not adopted

- **Source:** `@assistant-ui/react@0.14.28` `dist/legacy-runtime/runtime-cores/remote-thread-list/useRemoteThreadListRuntime.js`
- **License:** MIT
- **Files inspected:** `dist/legacy-runtime/runtime-cores/remote-thread-list/useRemoteThreadListRuntime.js`
- **Authority gate failed:** Expects a cloud API contract (`AssistantCloud`)
  and thread CRUD semantics that differ from Kitty's chats/chat-lifecycle
  endpoints. The chat list management in `KittyContext.tsx` is already thin
  (~50 lines for fetch, create, select, close).
- **Kitty code it would avoid:** The chat-list fetch and management in
  `KittyContext.tsx` (~50 lines).
- **Status:** **Rejected.** Adapter complexity exceeds a thin custom
  implementation.
- **Kill condition:** Revisit when Kitty moves to a fully externally-managed
  thread store with standard CRUD semantics.

---

## 6. chat_lifecycle.py + chats_store.py — existing Kitty persistence

- **Source:** `gateway/chat_lifecycle.py` + `gateway/chats_store.py`
- **License:** MIT (part of Kitty)
- **Files inspected:** Full source of both modules (277 and 214 lines).
- **Kitty code this is:** The authoritative persistence layer. `start_turn`
  writes a durable user message and attempt before provider dispatch.
  `finish_turn` atomically finalizes the attempt, assistant message, and turn
  status. `list_conversation` + `_recover_messages` rebuild the ordered UI
  message list from the lifecycle ledger. `upsert_chat` stores the
  compatibility chat blob.
- **Improvement in this slice:** Added source-message-id deduplication in
  `_recover_messages` to prevent duplicate user turns after retries.
- **Authority kept by Kitty:** Conversation lifecycle, message identity, turn
  status, and recovery ordering.
- **Implementation benefit:** Already built. The dedup fix is 8 lines.
- **Maintenance burden:** Owned by Kitty. No external dependency.
- **Accepted:** Yes (existing).
- **Kill condition:** Replace only if a mature lifecycle store with the same
  authority boundaries (Kitty-owned conversation, no competing store) emerges.
  Current candidate: none.

---

## Summary

| # | Component | Accepted | Kitty Code Replaced/Avoided |
|---|-----------|----------|-----------------------------|
| 1 | `@assistant-ui/react` ThreadPrimitive + ExternalStoreAdapter | Yes | ~400 lines viewport/scroll/composer |
| 2 | LibreChat | No | N/A (rejected by authority gates) |
| 3 | AnythingLLM | No | N/A (rejected by authority gates) |
| 4 | `useLocalRuntime` | No | N/A (adapter more complex than current code) |
| 5 | `useRemoteThreadListRuntime` | No | N/A (~50 lines not worth adapter) |
| 6 | chat_lifecycle + chats_store | Yes (existing) | Own persistence, dedup fix added |

**Net custom code avoided by mature reuse:** ~400 lines of viewport/scroll/composer/thread UI primitives via `@assistant-ui/react`.

**Net custom code changed in this slice:** 8-line dedup fix in `_recover_messages`; 2-line error recovery message improvement; `data-testid` attribution anchor; 106-line Playwright smoke test; this ledger.
