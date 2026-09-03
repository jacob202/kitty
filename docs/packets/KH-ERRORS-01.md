# KH-ERRORS-01 — Gateway client preserves structured error truth

**Initiative:** none — deliberately interactive
**Owner:** ChatGPT/Codex interactive lane after fresh collision check
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`
**Depends on:** KH-JSON-01 + KH-IMPORT-01 before broad adoption
**Status:** packet only — no implementation/runtime mutation performed

## Why there is no Builder manifest
This packet requires Node-only frontend verification, `.claude` compatibility-file mutation, security-sensitive live network configuration, or a combination that Builder's current packet runner cannot prove safely. Per `PACKET_STANDARD.md` F9/authority rules, it stays interactive rather than carrying fake Builder gates.

## What Jacob can do after this
Jacob can get one typed client error carrying safe user copy, status/code, and diagnostic context instead of losing the Gateway response as `Gateway returned 500`.

## Verified finding
`gfetch()` currently throws on `!response.ok` before reading structured bodies. The Gateway already has a `KittyError` envelope, while legacy routes may return FastAPI `detail` or plain text. `failure-copy.ts` exists, but the client discards the information it would need to distinguish typed safe errors from raw diagnostics.

## Intended scope
- `gateway/kitty-chat/src/lib/gateway.ts`
- `gateway/kitty-chat/src/lib/gateway-error.ts`
- `gateway/kitty-chat/src/lib/failure-copy.ts`
- `gateway/kitty-chat/tests/failureCopy.test.ts`
- `gateway/kitty-chat/tests/gatewayError.test.ts`


## Plan / hardened direction
1. Create one `GatewayError` type/helper outside the 2,600-line `gateway.ts`; this is the targeted hotspot extraction for this seam.
2. On non-2xx, read a bounded body once. Parse the canonical `{error,message,details}` Kitty envelope first, then known typed route envelopes; preserve untrusted `detail`/plain text as diagnostic metadata only unless the server contract explicitly marks it safe.
3. Keep HTTP status, machine code, retryability when known, and request-abort/network distinctions.
4. Make `gfetch` and any duplicate core fetch helper use the same parser; do not migrate every consumer in this packet.
5. `describeFailure()` consumes the typed error and never needs to regex raw stack traces/server text.


## Acceptance criteria
1. Canonical KittyError `message` reaches `safeMessage` while machine code/status/details remain inspectable.
2. Legacy raw `detail`, HTML, stack trace, and plain 500 bodies are not automatically promoted to primary user copy.
3. Timeout/AbortError and network-unreachable remain distinguishable from HTTP application errors.
4. Error response bodies are bounded before parsing and malformed JSON cannot crash the client.
5. Core success payload behavior is unchanged.
6. The central error parser lives outside `gateway.ts`, reducing rather than increasing hotspot coupling.


## Verification
- `cd gateway/kitty-chat && npx vitest run tests/failureCopy.test.ts tests/gatewayError.test.ts --reporter=dot`
- `cd gateway/kitty-chat && npx tsc --noEmit`


The implementation must demonstrate a RED reproduction or measured baseline before production edits, then exact-head GREEN evidence. User-facing changes require desktop + iPhone-class acceptance and an independent reviewer who did not implement the change.

## Stop condition
If a legacy route needs raw exception text to remain useful, fix that route's server contract separately; do not mark arbitrary `detail=str(exc)` safe in the client.

## Recovery / authority guard
No packet here authorizes paid provider calls, credential changes, push/PR/merge, destructive data operations, or edits to canonical while another lane owns the path. Re-read `workspace_global`, GitHub #490, current PRs/worktrees, and Builder state immediately before implementation. UNKNOWN remains UNKNOWN.
