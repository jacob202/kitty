# Chat UI Harvest — 2026-08-01

**Branch:** `research/chat-ux-harvest-2026-08-01`
**Phase 1 PR:** #367
**Phase 1 SHA:** `e3ff82fc`
**Status:** Research only. No implementation files modified.

---

## Scope

Source-level UX and component harvest from seven upstream chat applications and
component libraries. Every candidate is classified against Kitty's current
architecture, license compatibility, and existing Phase 1 work.

Architecture rules from ADR-0007 and ADR-0019 apply: borrow proven patterns, do
not import a repo's worldview wholesale; Open WebUI and Khoj are study-only.

---

## Kitty Baseline

### Current chat architecture (post-Phase 1)

| Surface | Implementation |
|---|---|
| Chat thread rendering | `KittyThread.tsx` using `ThreadPrimitive.Root/Viewport/Messages/Empty/ScrollToBottom` |
| Runtime adapter | `useKittyRuntime(options)` → `useExternalStoreRuntime` via `ExternalStoreAdapter<Message>` |
| Message state ownership | `KittyContext.tsx` — `chats[]`, `activeChatId`, `runStream`, `handleSend`, `handleRetry` |
| Streaming | `lib/chat-client.ts` → SSE parser → `StreamChunk` generator |
| Persistence | `chat_lifecycle.py` (turns, attempts, messages) + `chats_store.py` (chat blobs) |
| Recovery | `_recover_messages` in `routes/chats.py` (lifecycle → ordered message list) |
| Attribution | `X-Kitty-Provider-Selected` / `X-Kitty-Model-Requested` headers → SSE `StreamChunk` fields |
| Retry | `handleRetry` in `KittyContext.tsx` — pops last assistant message, re-sends |
| Mobile | `BottomNav` + `MOBILE_BREAKPOINT` (mobile-first: `docs/ARCHITECTURE.md`) |
| Tools | `ToolCallCard` component, `toolCalls` field on Message |
| Documents | `DocumentsPanel`, Archivist pipeline, ChunkedDocument type |
| Citations | Not implemented |
| Provider switching | `ProviderCenter` settings panel, `ModelSelectorCmdk`, provider chain |
| Composer | `ThreadPrimitive.Composer` → Kitty's `InputBar` (model override, attachments) |
| Chat history | `SessionSidebar` with search, `chats[]` list, close/select/create |
| Cat state | `catState` model (mood, energy, focus) — Kitty unique |
| Design system | CSS custom properties (`--bg`, `--ink`, `--ink-2`, `--surface`, `--font-mono`, `--font-body`) |

### Gaps identified in Phase 1

1. **Retry silently replaces** prior assistant response — no branch picker, no retry history, no "show previous versions"
2. **No tool-call intermediate-work visibility** — tool calls are rendered as completed cards only
3. **No citation/source inspection** — memory items have `sources[]` but no clickable citation UI
4. **Attachments UX is basic** — file drop zones exist but no preview, progress, or inline rendering
5. **No model-comparison mode** — users can switch models but cannot view side-by-side responses
6. **Conversation organization is flat** — no folders, tags, pins, or semantic search
7. **Keyboard accessibility is minimal** — no focus management, skip navigation, or keyboard shortcuts beyond Enter-to-send
8. **Offline/recovery states are binary** — no partial-failure granularity, streaming progress, or honest loading states

---

## Upstream Project Matrix

### assistant-ui/assistant-ui

- **Pinned SHA:** `ff12cf2d` (2026-08-01)
- **License:** MIT (Copyright AgentbaseAI Inc)
- **Package:** `@assistant-ui/react@0.14.28`
- **Already in Kitty:** ExternalStoreAdapter, ThreadPrimitive (viewport, scroll, messages, empty, scroll-to-bottom). See THIRD_PARTY_NOTICES.md and reuse ledger.

| Source path | User value | Overlap with Kitty | Verdict | Dependencies | Effort | Verification |
|---|---|---|---|---|---|---|
| `packages/react/src/primitives/branchPicker/BranchPickerPrimitive.tsx` | Visible retry/branch navigation; show prior assistant responses instead of silently replacing them | None — Kitty has no branch model | **WRAP** — adapter behind Kitty-owned ExternalStoreAdapter | None (existing dep) | 3-5 days | Playwright: retry→branch visible→select branch→attribution preserved |
| `packages/react/src/primitives/thread/ThreadPrimitive.tsx` (full) | ThreadMessages, Suggestion, If, ContentPart | Partially — Kitty uses ThreadPrimitive subset | Already adopted | — | — | — |
| `packages/react/src/model-context/ModelContextTypes.ts` | `ToolCallContentPart`, `ToolCallState`, intermediate work display | Kitty has `ToolCallCard` but no intermediate/progress states | **REIMPLEMENT** — borrow the state model, not the code | — | 2-3 days | Vitest: tool-call lifecycle states mapped to Kitty SSE parser |
| `packages/react/src/primitives/composer/ComposerPrimitive.tsx` | Rich composer with send/cancel/stop/attachment states | Kitty uses ThreadPrimitive.Composer partially | Already adopted | — | — | — |
| `packages/react/src/primitives/attachment/AttachmentPrimitive.tsx` | File preview, drop zone, progress | `FileDropZones` component exists but is basic | **REIMPLEMENT** — borrow attachment state model | — | 1-2 days | Playwright: file drop→preview→send→attachment in message |

### danny-avila/LibreChat

- **Pinned SHA:** `3191f697` (2026-08-01)
- **License:** MIT
- **Phase 1 status:** Rejected as full-application foundation (MongoDB, MeiliSearch, duplicate backend)
- **Pattern-reference only**

| Source path | User value | Overlap with Kitty | Verdict | Dependencies | Effort | Verification |
|---|---|---|---|---|---|---|
| `client/src/components/Chat/Messages/Content/Markdown.tsx` | Citation tooltips, inline source links | None | **REIMPLEMENT** — inline citation rendering pattern | react-markdown (already in Kitty) | 1-2 days | Vitest: markdown parsing preserves citation markers |
| `client/src/components/Chat/Input/ModelSelect/ModelSelect.tsx` | Model comparison sidebar | `ModelSelectorCmdk` is single-select | **REIMPLEMENT** — dual-model comparison UX | — | 2-3 days | Playwright: select two models→send→side-by-side responses |
| `client/src/components/Conversations/Convo.tsx` | Conversation search, tags, folders | `SessionSidebar` has basic search only | **REIMPLEMENT** — search-with-tags pattern | — | 1-2 days | Playwright: search→filter→select chat |
| `client/src/components/Chat/Messages/MessageActions.tsx` | Regenerate, branch, copy, share | Kitty has copy and retry only | **REIMPLEMENT** — action row pattern (already partially in `ChatMessage.tsx`) | — | 1 day | Vitest: action buttons render for each message state |

### lobehub/lobehub

- **Pinned SHA:** `ca27228d` (2026-08-01, v2.2.13)
- **License:** LobeHub Community License (Apache 2.0 + commercial restrictions)
- **⚠ RESTRICTED:** Derivative works require commercial license from LobeHub LLC
- **Separately licensed packages:** `@lobehub/ui`, `@lobehub/editor`, `@lobehub/icons`, `@lobehub/charts` — these have their own permissive licenses (MIT). Inspect individually before reuse.

| Source path | User value | Overlap with Kitty | Verdict | Dependencies | Effort | Verification |
|---|---|---|---|---|---|---|
| `src/app/chat/features/ConversationList/ConversationList.tsx` | Pinned conversations, batch operations, semantic search | `SessionSidebar` is flat | **REIMPLEMENT** — pin/batch patterns | — | 1-2 days | Playwright: pin→reload→pinned stays |
| `src/features/Retrieval/Retrieval.tsx` (document ingestion) | Document indexing progress, chunk preview, re-index button | Archivist pipeline exists; no progress UI | **REIMPLEMENT** — ingestion progress UX | — | 2-3 days | Playwright: upload doc→progress bar→chunks visible→ready |
| `src/features/Conversation/components/ChatList/ChatListItem.tsx` | Last-message preview, draft indicator, unread dot | `SessionSidebar` items show title only | **REIMPLEMENT** — rich list-item pattern | — | 1 day | Vitest: chat item renders last message snippet |
| `src/features/PluginsUI/PluginsUI.tsx` (tool-call rendering) | Intermediate tool-call display with status, structured output | `ToolCallCard` is final-state only | **REIMPLEMENT** — tool-call lifecycle states: pending→running→done→error | — | 2-3 days | Playwright: tool call shows progress→result→expand details |
| `src/app/chat/features/SessionList/SessionList.tsx` | Session grouping by date, search, agent filter | Not implemented | **REIMPLEMENT** — date-grouped session list | — | 1 day | Vitest: groups render correct date boundaries |
| `src/features/ChatInput/ChatInput.tsx` (composer) | Topic/prompt template selector, token counter, file previews | `InputBar` has model override and attachment button | **REIMPLEMENT** — token counter, template selector patterns | — | 1-2 days | Vitest: token counter updates on type |

**LobeHub sub-packages (permissively licensed):**

| Package | License | Value | Verdict |
|---|---|---|---|
| `@lobehub/ui` | MIT | Icon set, design tokens, basic components | **REJECT** — Kitty has own design system; importing a competing design system violates ADR-0007 |
| `@lobehub/editor` | MIT | Rich text editor | **REJECT** — Kitty's chat is plain-text by design; rich editor adds complexity without user need |
| `@lobehub/icons` | MIT | AI/LLM brand icons | **COPY** — individual SVG icons are small, isolated, and permissively licensed |
| `@lobehub/charts` | MIT | D3-based chart components | **REJECT** — Kitty has no chart surface; adding one would be scope creep |

### open-webui/open-webui

- **Pinned SHA:** `01f4282f` (2026-07-27)
- **License:** Custom BSD-like with branding clause (§4) — "licensees are strictly prohibited from altering, removing, obscuring, or replacing any 'Open WebUI' branding"
- **REJECT for code reuse.** ADR-0019 also confirms study-only.
- **Pattern-reference only**

| Source path | User value | Verdict | Notes |
|---|---|---|---|
| `src/lib/components/chat/Messages/ResponseMessage.svelte` | Citation footnotes, source inspection panel | **REIMPLEMENT** — citation UI pattern | License permits studying patterns; code must not be copied |
| `src/lib/components/chat/ModelSelector.svelte` | Model switching with comparison | **REIMPLEMENT** — model comparison UX pattern | Same |
| `src/lib/components/chat/MessageInput/MessageInput.svelte` | Web search toggle, knowledge toggle, prompt library | **REIMPLEMENT** — context-toggle patterns | Same |
| `src/lib/components/layout/Sidebar.svelte` | Collapsible sidebar with search, tags, pinned | **REIMPLEMENT** — sidebar organization pattern | Same |
| `src/lib/components/workspace/Knowledge.svelte` | Document ingestion list with status badges | **REIMPLEMENT** — knowledge ingestion status UI | Same |

### khoj-ai/khoj

- **Pinned SHA:** `1e30154d` (2026-06-24)
- **License:** AGPL-3.0
- **HARD REJECT.** Copyleft (AGPL-3.0) is incompatible with Kitty's MIT license. No code may be copied. Pattern reference only, with an explicit note that no AGPL code was ingested.
- **Also confirmed study-only in ADR-0019.**

| Source path | User value | Verdict | Notes |
|---|---|---|---|
| `src/khoj/interface/web/chat/chat_history.html` | Semantic chat search with content preview | **REIMPLEMENT** — semantic search pattern | Pattern only; no AGPL code |
| `src/khoj/interface/web/agent/agent.html` | Agent intermediate-reasoning display | **REIMPLEMENT** — step-visibility pattern | Pattern only; no AGPL code |
| `src/khoj/interface/web/content_source.html` | Source/citation cards with relevance scores | **REIMPLEMENT** — citation card pattern | Pattern only; no AGPL code |

### Mintplex-Labs/anything-llm

- **Pinned SHA:** `v1.7.7` (verified in Phase 1 PR #286)
- **License:** MIT
- **Phase 1 status:** Rejected as full-application foundation
- **Additional inspection:** Document ingestion pipeline, workspace management, citation UI

| Source path | User value | Verdict | Notes |
|---|---|---|---|
| `frontend/src/components/WorkspaceChat/ChatContainer.jsx` | Workspace-based chat with multi-document context | **REIMPLEMENT** — workspace/context indicator pattern | MIT license allows pattern study |
| `frontend/src/components/Modals/ManageWorkspace/Documents/DocumentList.jsx` | Document ingestion with chunk counts, re-sync, status | **REIMPLEMENT** — document management list pattern | Same |
| `frontend/src/components/WorkspaceChat/ChatContainer/ChatInput.jsx` | @agent mentions, slash commands in composer | **REIMPLEMENT** — mention/command pattern | Same |

---

## Meta-Analysis — Recurring Patterns

### 1. Conversation branching and retry history (5 of 7 projects)

LibreChat, LobeHub, assistant-ui, Open WebUI, and AnythingLLM all expose prior
responses under a branch/version selector. The dominant interaction contract:

- Each user message can have N assistant responses
- A branch picker (dropdown, numbered pills, or tree view) lets users view prior responses
- The current/selected branch is shown; others are one click away
- Retrying creates a new branch, never replaces

Kitty's current retry (`handleRetry` in `KittyContext.tsx`) pops the last
assistant message and re-sends — the prior response is permanently lost. This is
the single largest UX gap.

**Recommendation:** Implement a Kitty-owned branch model in the ExternalStoreAdapter
where each user message maps to an ordered list of assistant responses. The UI
shows the current branch and a branch picker to navigate. assistant-ui's
`BranchPickerPrimitive` provides a ready-made UI primitive that fits this
contract.

### 2. Tool-call lifecycle visibility (6 of 7 projects)

All projects show intermediate tool-call progress:
- LobeHub: plugin execution with status badges and structured output
- assistant-ui: `ToolCallContentPart` with loading states
- LibreChat: agent step-by-step display
- Open WebUI: function-call status indicators
- Khoj: agent reasoning steps
- AnythingLLM: document-query progress

Kitty renders tool calls as completed `ToolCallCard` components only. The SSE
parser in `chat-client.ts` receives deltas but has no intermediate-state model.

**Recommendation:** Extend `ToolCall` type with `status: 'pending' | 'running' | 'done' | 'error'`
and render progress states. Borrow the state model from assistant-ui's
`ToolCallState` without importing it directly.

### 3. Citation and source inspection (4 of 7 projects)

LibreChat (inline footnotes), Khoj (relevance-scored cards), Open WebUI (source
panel), and LobeHub (document-chip citations) all expose source evidence.

Kitty has `memoryItems` with `sources[]` on messages but no visual citation
system. The data is present; the UI is missing.

**Recommendation:** Add inline citation markers (e.g., `[1]`, `[2]`) to
react-markdown rendering and a collapsible source panel showing document title,
chunk text, and relevance. This is a pure UI addition — no backend change needed.

### 4. Model switching and comparison (3 of 7 projects)

LibreChat and Open WebUI offer side-by-side model comparison. LobeHub has a
model-selection drawer with capability badges.

Kitty has `ModelSelectorCmdk` (single-select) and `ProviderCenter` (provider
chain management). Model comparison does not exist.

**Recommendation:** Low priority. Model comparison is a "nice to have" that
would require significant SSE pipeline changes (two concurrent streams). Defer
until citation and branching are implemented.

### 5. Composer richness (5 of 7 projects)

Common patterns: token counter, prompt template selector, @mention autocomplete,
slash commands, web-search toggle, knowledge-base toggle.

Kitty's composer is minimal: text input + model override + file attachment. The
existing `ThreadPrimitive.Composer` handles basic send/cancel/stop state.

**Recommendation:** Add token counter (pure client-side, uses the existing
tokenizer from model metadata). Defer @mentions, slash commands, and context
toggles until chat is a daily surface with usage data.

### 6. Session search and organization (4 of 7 projects)

Pinned conversations, folder/tag organization, semantic search, date-grouped
lists, unread indicators.

Kitty has `SessionSidebar` with basic text search and a flat list. The chat
store has no tags, pins, or folder fields.

**Recommendation:** Add pin/unpin to `Chat` interface and `SessionSidebar`.
Date grouping is a pure client-side transform. Defer semantic search (requires
embedding infrastructure).

### 7. Mobile chat navigation (all projects)

Universal pattern: bottom tab bar, swipe-to-close sidebar, collapsible panels,
full-height chat view with fixed composer.

Kitty already implements `BottomNav`, mobile sidebar drawer, and responsive
breakpoints. The mobile foundation is solid.

**Recommendation:** No architectural change. Minor refinements: swipe-to-dismiss
sidebar, keyboard-avoidance in the composer on iOS Safari.

### 8. Offline, partial-failure, and recovery states (3 of 7 projects)

Most projects show a binary "connected"/"disconnected" state. LibreChat has the
most honest recovery model: preempt-incomplete turns (truncated by context
window), abort title handling, and explicit turn-status metadata.

Kitty's `KittyRuntimeProvider` has a `HealthGate` that shows a blocking offline
screen. The `StatusBar` shows save state and gateway reachability. This is
adequate for a local-first app but could be more granular.

**Recommendation:** Add streaming progress indicator (tokens received, time
elapsed). Show partial-failure states in the `StatusBar` (e.g., "stream
interrupted — tap retry"). No architectural change needed.

---

## What None of Them Solve — Uniquely Kitty

Several problems remain Kitty's exclusive responsibility regardless of what
upstream projects offer:

1. **Cat state model** — Kitty's mood/energy/focus primitives have no upstream
   analog. Rendering cat-state-aware responses, expressions, and suggestions is a
   uniquely Kitty concern.
2. **Local-first durable lifecycle** — `chat_lifecycle.py` records turns,
   attempts, and messages in SQLite before provider dispatch. No upstream
   project has a turn-level lifecycle ledger this fine-grained. Branch models
   must map to this ledger, not replace it.
3. **SSE runtime with turn/attempt identity** — `X-Kitty-Turn-ID` and
   `X-Kitty-Attempt-ID` headers are Kitty-specific. No upstream project tags
   streams with durable attempt identity.
4. **KittyBuilder control plane** — The Kitty/KittyBuilder separation (ADR-0017)
   has no analog. Chat features must not introduce a second execution queue or
   task model.
5. **Fully offline-first vision** — While Open WebUI and AnythingLLM can run
   locally, neither is designed to go fully offline with local models as the
   primary path. Kitty's `kitty-local` model and MLX integration make this
   feasible.
6. **Project-scoped memory and context** — Kitty's `context_assembler`,
   `memory_graph`, and project-scoped knowledge retrieval are unique. Other
   projects' document ingestion pipelines assume a single global knowledge base.
7. **Personality documents** — Kitty's `SOUL.md`, preferences, and personality
   injection pipeline (`SettingsPanel`) are custom. No upstream project has an
   editable personality document system.

---

## Sequenced Implementation Packets

### Packet 1 — BranchPickerPrimitive Evaluation and Retry Branch Navigation

**User-visible outcome:** When a user retries a message or the assistant
produces multiple responses, a branch picker (dropdown or numbered pills)
appears. Users can view prior assistant responses without losing the current one.

**Files likely involved:**
- `gateway/kitty-chat/src/lib/kitty-runtime.ts` — extend `ExternalStoreAdapter` with branch state
- `gateway/kitty-chat/src/state/KittyContext.tsx` — replace pop-based retry with branch-append
- `gateway/kitty-chat/src/components/ChatMessage.tsx` — render `BranchPickerPrimitive`
- `gateway/kitty-chat/src/lib/types.ts` — add `branches?: Message[][]` to Chat type
- `gateway/routes/chats.py` — ensure lifecycle ledger preserves multiple attempts per turn
- `gateway/chat_lifecycle.py` — verify turn model supports multiple attempts
- `gateway/kitty-chat/tests/smoke/chat-trust-slice.spec.ts` — add branch-navigation test

**Upstream source:** `@assistant-ui/react` `BranchPickerPrimitive` at
`packages/react/src/primitives/branchPicker/BranchPickerPrimitive.tsx`, SHA
`ff12cf2d`, MIT license. Kitty already depends on `@assistant-ui/react@0.14.28`.

**Architecture verification required:**

The current `ExternalStoreAdapter<Message>` contract has:
- `messages: Message[]` — flat list
- `onReload?: () => void` — single retry path

BranchPickerPrimitive requires the adapter to expose:
- A branching model where each user message maps to a list of assistant responses
- An `onSwitchBranch(messageIndex: number, branchIndex: number)` callback

This requires either:
a) Extending `ExternalStoreAdapter` with optional branch fields (if the adapter
   contract allows arbitrary extra fields), or
b) Wrapping BranchPickerPrimitive in a Kitty-owned component that manages branch
   state independently and feeds the current branch's messages to the adapter.

Option (b) is preferred: Kitty owns branch state as a durable Concern; the
adapter feeds the "current branch view" to assistant-ui. This keeps the
`ExternalStoreAdapter` contract unchanged and the branch model entirely on
Kitty's side.

**Stop condition:** Do not implement if the branch model cannot be made durable
in the lifecycle ledger without introducing a second message store. The
lifecycle ledger's turn model already supports multiple attempts — verify this
maps cleanly to branches before writing UI code.

**Dependencies:** None (existing `@assistant-ui/react` dep)

**Acceptance tests:**
- Send message → assistant responds → retry → second response appears → branch
  picker shows (2) → switch to prior branch → first response visible → attribution
  preserved
- Reload → branch picker still shows → both branches recoverable
- Retry 3 times → branch picker shows (3) → last branch active

**Mobile/desktop:** Both viewports. Branch picker must not overflow mobile width.

**Failure/recovery:** If a branch's attempt was interrupted, the branch shows
"incomplete — tap to retry this branch" instead of the partial response.

**Non-goals:**
- Branching from arbitrary points in the conversation (only from the last user
  message)
- Editing user messages to create branches
- Comparing branches side-by-side
- Merging branches
- Visual tree view (simple numbered picker only)

**Conflict/overlap notes:**
- Phase 1 retry copy ("tap retry below") should remain for the first retry;
  branch picker only appears when there are ≥2 branches
- Phase 1 `_recover_messages` dedup must be audited for branch recovery
- Does not replace Phase 1 `data-testid="chat-attribution"`

**Estimated effort:** 5-7 days (evaluation + implementation + tests)

---

### Packet 2 — Tool-Call Lifecycle Visibility

**User-visible outcome:** When Kitty calls a tool (code execution, search, web
fetch), users see the tool's status change from "pending" to "running" to
"done" with intermediate output visible. Failed tool calls show error details.

**Files likely involved:**
- `gateway/kitty-chat/src/lib/types.ts` — add `toolCall.status` field
- `gateway/kitty-chat/src/lib/chat-client.ts` — parse tool-call deltas for status changes
- `gateway/kitty-chat/src/components/ToolCallCard.tsx` — render status-dependent UI
- `gateway/kitty-chat/tests/ToolCallCard.test.tsx` — extend coverage

**Upstream source:** assistant-ui `ToolCallState` type (pattern only — REIMPLEMENT)

**Dependencies:** None

**Acceptance tests:** Vitest unit tests for each tool-call status state.
Playwright smoke: send message that triggers tool use → tool status updates
visible → final result rendered.

**Estimated effort:** 2-3 days

---

### Packet 3 — Citation and Source Inspection

**User-visible outcome:** Assistant responses that reference specific documents
show inline citation markers. Clicking a marker opens a panel showing document
title, chunk text, and relevance. Users can verify the source without leaving
the chat.

**Files likely involved:**
- `gateway/kitty-chat/src/components/ChatMessage.tsx` — inline citation rendering
- `gateway/kitty-chat/src/components/SourcePanel.tsx` (new) — citation detail panel
- `gateway/kitty-chat/src/lib/types.ts` — add `Citation` type

**Upstream source:** LibreChat `Markdown.tsx` inline citation pattern (REIMPLEMENT)

**Dependencies:** None (uses existing `react-markdown` + `memoryItems.sources`)

**Acceptance tests:** Vitest: markdown with citation markers renders clickable badges.
Playwright: send knowledge-grounded question → citations appear → click → panel opens → source verified.

**Estimated effort:** 2-3 days

---

### Packet 4 — Document Ingestion Progress

**User-visible outcome:** When users upload documents, they see a progress
indicator showing chunking status and document count. Uploaded documents appear
in a management list with re-index and delete options.

**Files likely involved:**
- `gateway/kitty-chat/src/components/DocumentsPanel.tsx` — progress display
- `gateway/kitty-chat/src/components/DocumentListItem.tsx` (new) — per-document status
- `gateway/routes/documents.py` — progress endpoint (if not already present)

**Upstream source:** LobeHub retrieval progress + AnythingLLM document list (REIMPLEMENT)

**Dependencies:** Existing Archivist pipeline

**Acceptance tests:** Playwright: upload PDF → progress bar → chunks counted → document
appears in list → re-index available → delete works.

**Estimated effort:** 2-3 days

---

### Packet 5 — Session Organization (Pins + Date Groups)

**User-visible outcome:** Users can pin important conversations to the top of
the sidebar. Conversations are grouped by date (Today, Yesterday, This Week,
Older). Pinned conversations survive reload.

**Files likely involved:**
- `gateway/kitty-chat/src/components/SessionSidebar.tsx` — pin toggle, date groups
- `gateway/kitty-chat/src/state/KittyContext.tsx` — handlePin, handleUnpin
- `gateway/kitty-chat/src/lib/types.ts` — add `pinned?: boolean` to `Chat`
- `gateway/chats_store.py` — persist pinned flag

**Upstream source:** LobeHub + LibreChat session list patterns (REIMPLEMENT)

**Dependencies:** None

**Acceptance tests:** Vitest: pin toggles, date grouping logic. Playwright: pin chat →
reload → still pinned at top.

**Estimated effort:** 1-2 days

---

## Five Highest-Value Harvest Decisions

| # | Candidate | Decision | Value | Rationale |
|---|---|---|---|---|
| 1 | assistant-ui BranchPickerPrimitive | **WRAP** | Highest | Already a dependency (MIT); fills Kitty's largest UX gap (silent retry replacement) |
| 2 | Tool-call lifecycle states | **REIMPLEMENT** | High | Borrows state model from assistant-ui; no code dependency needed; existing ToolCallCard only needs status field |
| 3 | Citation/source inspection UI | **REIMPLEMENT** | High | Pattern from LibreChat/Open WebUI; pure UI addition; uses existing `memoryItems.sources` data |
| 4 | Document ingestion progress | **REIMPLEMENT** | Medium | Pattern from LobeHub/AnythingLLM; requires no new dependencies |
| 5 | Session pins and date groups | **REIMPLEMENT** | Medium | Pattern from LobeHub/LibreChat; small scope with high daily use impact |
| — | assistant-ui useLocalRuntime | **REJECT** (Phase 1) | N/A | Would replace Kitty's message ownership with assistant-ui's internal store |
| — | assistant-ui useRemoteThreadListRuntime | **REJECT** (Phase 1) | N/A | Assumes cloud API contract; Kitty's chat list is ~50 lines |
| — | LibreChat full app | **REJECT** (Phase 1) | N/A | Duplicates Kitty's backend, memory, routing, and auth |
| — | AnythingLLM full app | **REJECT** (Phase 1) | N/A | Same duplication class as LibreChat |
| — | Open WebUI code | **REJECT** | N/A | Branding clause (§4) prohibits removing "Open WebUI" identifiers; study-only per ADR-0019 |
| — | Khoj code | **REJECT** | N/A | AGPL-3.0 is copyleft and incompatible with Kitty's MIT license; study-only per ADR-0019 |
| — | LobeHub core code | **REJECT** | N/A | Community License requires commercial license for derivative works |
| — | LobeHub `@lobehub/icons` | **COPY** | Low | MIT license; small isolated SVG assets for AI/LLM brand logos |
| — | LobeHub `@lobehub/ui` | **REJECT** | N/A | Would introduce competing design system; violates ADR-0007 |

---

## Recommended Next Implementation Packet

**Packet 1 — BranchPickerPrimitive Evaluation and Retry Branch Navigation.**

This is the highest-value, lowest-risk packet:
- Uses an existing MIT dependency (`@assistant-ui/react`)
- Addresses Kitty's single largest UX gap (retry silently destroys prior responses)
- Can be implemented entirely through the existing `ExternalStoreAdapter` boundary
- Does not require backend changes (lifecycle ledger already supports multiple attempts per turn)
- Has a clear stop condition (durable branch model must map to lifecycle ledger)

Start with a 1-day evaluation spike that verifies the lifecycle ledger's
attempt model supports branches, then a 3-4 day implementation of the
Kitty-owned branch state + `BranchPickerPrimitive` wrapper, and 1-2 days of
testing.

---

## Phase 1 Cross-Reference

No Phase 1 work is duplicated by any packet:
- `source_message_id` dedup in `_recover_messages` — Packet 1 must verify this
  works with branch recovery
- "tap retry below" copy — remains useful; Packet 1 adds branch picker beside it
- `data-testid="chat-attribution"` — unchanged; Packet 1 must verify attribution
  is preserved per-branch
- Proxy header forwarding — unchanged; Packet 1 uses same SSE pipeline
- Playwright smoke suite — extend with branch-navigation tests

