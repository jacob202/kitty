# KH-ERRORS-02 — User-facing surfaces stop rendering raw Gateway diagnostics

**Initiative:** none — deliberately interactive
**Owner:** ChatGPT/Codex interactive lane after fresh collision check
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`
**Depends on:** KH-ERRORS-01
**Status:** packet only — no implementation/runtime mutation performed

## Why there is no Builder manifest
This packet requires Node-only frontend verification, `.claude` compatibility-file mutation, security-sensitive live network configuration, or a combination that Builder's current packet runner cannot prove safely. Per `PACKET_STANDARD.md` F9/authority rules, it stays interactive rather than carrying fake Builder gates.

## What Jacob can do after this
Jacob can see one plain failure explanation and next action across Kitty surfaces instead of raw status codes, `gateway error`, or exception messages.

## Verified finding
Many components already use `describeFailure`, but review still found direct `.error.message`/`Gateway request failed`/`gateway error` rendering in ProviderCenter, DocumentsPanel, WorkView, Tutor, ThreadGoal and other surfaces. The active mission explicitly forbids internal service names/status/paths as primary copy.

## Intended scope
- `gateway/kitty-chat/src/components/ProviderCenter.tsx`
- `gateway/kitty-chat/src/components/DocumentsPanel.tsx`
- `gateway/kitty-chat/src/components/WorkView.tsx`
- `gateway/kitty-chat/src/components/ThreadGoal.tsx`
- `gateway/kitty-chat/src/components/TutorPanel.tsx`
- `gateway/kitty-chat/src/components/TutorShell.tsx`
- `gateway/kitty-chat/src/components/ChatMessage.tsx`
- `gateway/kitty-chat/src/lib/failure-copy.ts`
- `gateway/kitty-chat/tests/failureCopy.test.ts`
- `gateway/kitty-chat/tests/ProviderCenter.test.tsx`


## Plan / hardened direction
1. Inventory every directly rendered fetch/query error in `gateway/kitty-chat/src/components`; classify technical/developer-only surfaces versus user-facing surfaces.
2. Migrate user-facing surfaces to `describeFailure`/typed `GatewayError`, preserving one relevant action (retry, restart, configure, reopen) when the component already knows it.
3. Keep full diagnostics available to logs/dev detail only; do not erase data needed for troubleshooting.
4. Remove literal `gateway error`, `Gateway returned`, raw HTTP status, env var, port, or Mac-path primary copy from the migrated surfaces.
5. Do not redesign visual layout; this is error semantics only.


## Acceptance criteria
1. No migrated user-facing component directly renders arbitrary `Error.message` from a network/query failure.
2. No primary failure copy contains `Gateway returned`, `gateway error`, raw status codes, env vars, ports, stack traces, or Mac paths.
3. Distinct not-found/auth/server/timeout/network/invalid-payload cases remain meaningfully different where the shared translator has evidence.
4. Retry/configuration controls preserve their existing action and re-enable after failure.
5. Desktop and iPhone widths show no new overflow or clipped error actions.


## Verification
- `cd gateway/kitty-chat && npx vitest run tests/failureCopy.test.ts tests/ProviderCenter.test.tsx --reporter=dot` plus focused tests for every touched component
- `cd gateway/kitty-chat && npx tsc --noEmit`
- Browser smoke injecting 401/404/500/timeout/network failures at desktop + iPhone widths
- Independent PA on at least Work, Settings/Providers, and one content surface.


The implementation must demonstrate a RED reproduction or measured baseline before production edits, then exact-head GREEN evidence. User-facing changes require desktop + iPhone-class acceptance and an independent reviewer who did not implement the change.

## Stop condition
If a component cannot provide an actionable message without a new backend error contract, stop that component and record the missing contract; do not invent a cause.

## Recovery / authority guard
No packet here authorizes paid provider calls, credential changes, push/PR/merge, destructive data operations, or edits to canonical while another lane owns the path. Re-read `workspace_global`, GitHub #490, current PRs/worktrees, and Builder state immediately before implementation. UNKNOWN remains UNKNOWN.
