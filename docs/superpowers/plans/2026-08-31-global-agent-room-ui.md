# Global Agent Room UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the scripted localStorage-backed Agents demo with a polished command-center client for the merged durable `workspace_global` protocol.

**Architecture:** Keep all collaboration truth in the merged Gateway Global Agent Room. The frontend auto-opens `workspace_global`, reads recent messages plus Jacob's receipt-aware inbox, posts as `jacob`, replies with `parent_message_id`, and explicitly acknowledges incoming messages. No frontend state becomes authoritative for agent presence or task completion.

**Tech Stack:** Next.js/React 19, TypeScript, Vitest + Testing Library, existing Kitty UI primitives/tokens.

**Spec:** `docs/superpowers/specs/2026-08-31-global-agent-room-design.md`

## Global Constraints

- Canonical room id is exactly `workspace_global`; there is no create/reset-room UX.
- Canonical agent identities are `chatgpt`, `claude`, `codex`, and `kitty`; Jacob is the human sender.
- Agent roster status means membership (`registered`), never fabricated online presence.
- Reads do not mark messages seen. Acknowledgement is an explicit mutation and never means task completion.
- Builder remains execution truth; #490 remains collision/ownership truth.
- Do not touch `views.tsx`, `page.tsx`, or `Rail.tsx` while their active owners remain unresolved.
- Preserve existing Gateway global-room endpoints; GAR-UI-01 adds no new backend state machine.

---

### Task 1: Typed Global Room Gateway Client

**Files:**
- Modify: `gateway/kitty-chat/src/lib/gateway.ts`
- Create/Test: `gateway/kitty-chat/tests/agentRoomGateway.test.ts`

**Interfaces:**
- Consumes: merged `/agent-room/global`, `/messages`, `/inbox/{participant}`, `/threads/{message}`, and `/receipts` routes.
- Produces: `fetchGlobalAgentRoom`, `fetchGlobalAgentMessages`, `fetchGlobalAgentInbox`, `postGlobalAgentMessage`, `updateGlobalAgentReceipt`, plus receipt-aware message types.

- [ ] **Step 1: Write failing client tests** that mock `fetch` and assert exact HTTP methods/paths/bodies for ensure/read, direct post, reply post, Jacob inbox, and acknowledgement.
- [ ] **Step 2: Run the new test file** and confirm RED because the global-room client functions do not exist.
- [ ] **Step 3: Extend types** so global roster status accepts `registered`, inbox messages expose `seen_at`, `acknowledged_at`, and `receipt_state`, and post input uses existing message-kind literals.
- [ ] **Step 4: Implement thin client functions** using `gfetch`; `postGlobalAgentMessage` always sends `sender_id: 'jacob'`, and receipt mutation always sends `participant_id: 'jacob'`.
- [ ] **Step 5: Re-run the client tests** and TypeScript typecheck for the touched frontend.
- [ ] **Step 6: Commit** as `feat(agent-room): add global room frontend client`.

---

### Task 2: Command-Center Agents Panel

**Files:**
- Modify: `gateway/kitty-chat/src/components/AgentWorkspacePanel.tsx`
- Rewrite/Test: `gateway/kitty-chat/tests/AgentWorkspacePanel.test.tsx`
- Rewrite/Test: `gateway/kitty-chat/tests/AgentWorkspacePanel.conflict.test.tsx`
- Rewrite/Test: `gateway/kitty-chat/tests/AgentWorkspacePanel.stale-room.test.tsx`

**Interfaces:**
- Consumes: Task 1 global-room client functions and types.
- Produces: one self-contained `AgentWorkspacePanel` that is safe to wire into the `agents` view once the registry collision clears.

- [ ] **Step 1: Write failing panel tests** proving mount auto-loads the stable Global Agent Room with no localStorage/create-room call and renders ChatGPT/Claude/Codex/Kitty as `registered`, not online.
- [ ] **Step 2: Add failing interaction tests** for broadcast/direct recipient selection, posting as Jacob, selecting reply context, cancelling reply context, and preserving `parent_message_id` on send.
- [ ] **Step 3: Add failing receipt tests** that render Jacob's unread addressed messages, show an unread count, explicitly acknowledge one message, and refresh state without treating acknowledgement as completion.
- [ ] **Step 4: Add failing recovery tests** proving a polling failure keeps the last transcript visible and a rejected post preserves the draft/reply context.
- [ ] **Step 5: Verify RED** with the three panel test files.
- [ ] **Step 6: Replace scripted-room behavior**: remove localStorage room IDs, create-room/reset-room flows, and `runAgentWorkspaceTurn`; auto-load `workspace_global`, poll recent messages/Jacob inbox, and preserve prior data on transient errors.
- [ ] **Step 7: Build the command-center UI**: compact header with room truth, registered roster with last-activity text, unread attention count, transcript with sender/recipient/kind/thread context, direct-recipient selector, reply target, explicit acknowledge action, and responsive composer using existing UI tokens/components.
- [ ] **Step 8: Verify GREEN** with all panel tests, `agentRoomGateway.test.ts`, TypeScript, and frontend lint/build checks appropriate to the touched files.
- [ ] **Step 9: Commit** as `feat(agent-room): turn Agents into global command center`.

---

### Task 3: First-Class Door — Collision-Gated

**Files after ownership clears:**
- Modify: `gateway/kitty-chat/src/lib/views.tsx`
- Test: `gateway/kitty-chat/tests/views.test.ts`

**Interfaces:**
- Consumes: Task 2 `AgentWorkspacePanel`.
- Produces: `VIEWS.agents.component === AgentWorkspacePanel` while retaining every concurrent view entry already merged.

- [ ] **Step 1: Refresh PR #735 and `origin/main`**. Do not edit `views.tsx` while #735 is still an active owner.
- [ ] **Step 2: After #735 is merged/closed**, merge fresh `origin/main` into this branch and rerun Task 1–2 verification.
- [ ] **Step 3: Write a failing registry test** that imports `VIEWS` and asserts the Agents entry resolves to `AgentWorkspacePanel`, not `PlaceholderView`.
- [ ] **Step 4: Import `AgentWorkspacePanel` in `views.tsx` and replace only the `agents` registry component**, preserving all newly merged view IDs/entries byte-for-byte otherwise.
- [ ] **Step 5: Run registry + panel tests and frontend typecheck/build**.
- [ ] **Step 6: Commit** as `feat(agent-room): open the Agents command-center door`.

## Final Verification

Run from `gateway/kitty-chat`:

```bash
npm test -- --run \
  tests/agentRoomGateway.test.ts \
  tests/AgentWorkspacePanel.test.tsx \
  tests/AgentWorkspacePanel.conflict.test.tsx \
  tests/AgentWorkspacePanel.stale-room.test.tsx
./node_modules/.bin/tsc --noEmit --incremental --tsBuildInfoFile .next/cache/gar-ui-verify.tsbuildinfo
```

Then run `git diff --check`. Once Task 3 is unblocked, include `tests/views.test.ts`, build the frontend, and browser-verify desktop plus iPhone-class layouts. Do not claim the UI is user-visible before Task 3 lands.
