# KH-PERF-01 — Live state invalidates queries by events instead of broad polling

**Initiative:** none — deliberately interactive  
**Owner:** ChatGPT/Codex interactive lane after fresh collision check  
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`  
**Depends on:** KH-ERRORS-01; activate after current ONE KITTY frontend shared-file lanes release  
**Status:** packet only — no implementation/runtime mutation performed

## Why there is no Builder manifest
This packet requires Node-only frontend verification, `.claude` compatibility-file mutation, security-sensitive live network configuration, or a combination that Builder's current packet runner cannot prove safely. Per `PACKET_STANDARD.md` F9/authority rules, it stays interactive rather than carrying fake Builder gates.

## What Jacob can do after this
Jacob can leave Kitty open on desktop or phone without dozens of periodic GET loops while active work still updates promptly and recovers after an SSE disconnect.

## Verified finding
Review counted 35 `refetchInterval` declarations in `queries.ts`/`work.ts`, including 3–5 second loops, while `/stream`, `/builder/events`, client SSE logic, and live repeated Gateway request traffic already exist. Raw count alone is not a bug; the issue is duplicated freshness mechanisms and unnecessary idle traffic.

## Intended scope
- `gateway/kitty-chat/src/lib/queries.ts`
- `gateway/kitty-chat/src/lib/work.ts`
- `gateway/kitty-chat/src/lib/sse.ts`
- `gateway/kitty-chat/src/components/builder/useLiveBuilderEvents.ts`
- `gateway/kitty-chat/src/components/AgentWorkspacePanel.tsx`
- `gateway/kitty-chat/tests/sse.test.ts`
- `gateway/kitty-chat/tests/ActionQueryPolling.test.ts`
- `gateway/kitty-chat/tests/agentRoomGateway.test.ts`


## Plan / hardened direction
1. Instrument a hermetic 60-second idle/active request-count baseline for Home/Work/Agents before changing intervals.
2. Map each high-frequency query to an existing event that actually proves invalidation; if no event exists, retain bounded polling rather than guessing.
3. Use SSE events to invalidate precise React Query keys. Active Builder/action work may retain short fallback polling; idle queries back off or stop.
4. Centralize SSE reconnect/backoff so components do not create independent reconnect storms. Preserve last-known data during transient disconnects.
5. Add a fallback refresh after prolonged SSE outage and on window focus/reconnect; event delivery is an optimization, not a single point of truth.
6. Target at least 50% fewer idle requests for the migrated query set while preserving current active-state freshness; record measurements instead of claiming battery/CPU gains without evidence.


## Acceptance criteria
1. For every removed interval there is a named event/fallback proving how the query becomes fresh.
2. The migrated idle request count drops at least 50% in the same hermetic 60-second scenario.
3. Active Builder/action state remains visibly fresh within the existing product expectation and does not wait for a minute-long poll.
4. SSE disconnect/reconnect preserves last-known data, uses bounded backoff, and does not multiply open EventSource connections.
5. Endpoints without authoritative events keep appropriate polling; the packet does not chase a zero-polling vanity metric.
6. No query becomes falsely healthy/stale because an event was missed; focus/reconnect fallback repairs it.


## Verification
- `cd gateway/kitty-chat && npx vitest run tests/sse.test.ts tests/ActionQueryPolling.test.ts tests/agentRoomGateway.test.ts --reporter=dot`
- `cd gateway/kitty-chat && npx tsc --noEmit`
- Hermetic request-count benchmark before/after plus browser smoke with SSE disconnect/recovery
- Independent mobile PA watching one live Builder/action transition and one room update.


The implementation must demonstrate a RED reproduction or measured baseline before production edits, then exact-head GREEN evidence. User-facing changes require desktop + iPhone-class acceptance and an independent reviewer who did not implement the change.

## Stop condition
If a query has no event that proves its source changed, keep its polling with a sensible idle interval; do not add a new event bus or duplicate backend scheduler just to remove a timer.

## Recovery / authority guard
No packet here authorizes paid provider calls, credential changes, push/PR/merge, destructive data operations, or edits to canonical while another lane owns the path. Re-read `workspace_global`, GitHub #490, current PRs/worktrees, and Builder state immediately before implementation. UNKNOWN remains UNKNOWN.
