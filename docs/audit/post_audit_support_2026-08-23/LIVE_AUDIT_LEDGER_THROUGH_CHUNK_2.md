# LIVE AUDIT LEDGER — Through CHUNK 2

This is the compact carry-forward authority for the active sequential whole-repository audit. Detailed evidence remains in chunk reports and current repository/GitHub/runtime truth always wins.

## Current repository/runtime truth at CHUNK 2 close

- Current remote main observed: `d11febfb9974d41c00a836d0450a10916c72add1`.
- Canonical checkout moved under other active UI work; do not assume its branch is the audit branch.
- Pre-existing/other-lane working-tree edits must not be staged by the audit.
- Audit-support worktree: `/Users/jacobbrizinnski/Projects/kitty-audit-support-20260823` on `docs/audit-support-20260823`.
- PR #600 is the docs-only sequential audit companion package.
- PR #593 owns legacy task-runner deletion.
- Issue #592 owns AgentRunner restart reconciliation.
- Issue #545 owns MCP/Skill/plugin convergence.
- AgentRouter: Jacob reports DONE.

## Stable findings

| ID | Status | Severity | Short title |
|---|---|---:|---|
| COR-001 | NEW | MEDIUM | Gateway freshness diagnostic is nonfunctional on actual macOS uvicorn runtime |
| DOC-001 | ALREADY TRACKED / DESIGN QUESTION | MEDIUM | Product-shell authority contradicts itself (OpenWebUI vs native canonical) |
| DOC-002 | NEW | MEDIUM | Current runnable architecture doc materially stale |
| REL-001 | ALREADY TRACKED #537 | MEDIUM | Desktop stop→ensure Gateway race in legacy/manual supervisor path |
| REL-002 | NEW | HIGH | ActionQueue `executing` state is unrecoverable/ambiguous across restart |
| AUTH-001 | NEW | HIGH | T2 calendar create bypasses ActionQueue via direct route |
| COR-002 | NEW | MEDIUM | approve+remember can return failure after approval already committed |
| REL-003 | ALREADY TRACKED #592 | HIGH | AgentRunner has no restart reconcile; canonical DB carried stale active sessions |
| COR-003 | NEW | MEDIUM | `./kitty up` can exit success after Gateway readiness failure |
| REL-004 | DESIGN QUESTION / NEW | MEDIUM | `./kitty down` kills unrelated occupants of Kitty ports |
| AUTH-002 | ALREADY TRACKED PR #579 follow-up | HIGH | session-scoped global allow can outrank narrower deny |
| AUTH-003 | NEW | HIGH | direct iMessage send bypasses approval/receipt boundary |
| SEC-001 | NEW / DESIGN QUESTION | MEDIUM | originless loopback caller can use secret-bearing native proxy |
| AUTH-004 | NEW | MEDIUM | `/deploy` can write Dockerfile to arbitrary writable target without receipt |
| COR-004 | NEW | LOW/MEDIUM | `GET /notify/test` performs external Pushover side effect |
| PAR-SEC-001 | ALREADY TRACKED #545 | MEDIUM dormant | MCP discovery/env handling exposes secrets / ambient env risk |
| PAR-SEC-002 | ALREADY TRACKED #545 | MEDIUM dormant | MCP invocation lacks call-identity/approval boundary if activated |
| PAR-SEC-003 | ALREADY TRACKED #545 | LOW dormant | MCP timeout does not terminate/reap child |
| PAR-SEC-004 | ALREADY TRACKED #545 | LOW current | plugin enable trust keyed only by plugin name |
| PAR-SEC-005 | ALREADY TRACKED #545 | LOW current | Skill prompt trust; allowed-tools metadata is not enforcement |
| PAR-SEC-006 | FIXED ON CURRENT MAIN | — | archived Skill exposure fixed |

## High-risk items to preserve through later chunks

1. REL-002 — crash after ActionQueue claim creates outcome-unknown external effects; never blindly retry.
2. AUTH-001 — calendar T2 bypass.
3. REL-003/#592 — AgentRunner durable state lies across restart and tests polluted canonical DB historically.
4. AUTH-002 — deny precedence can be defeated by session specificity.
5. AUTH-003 — direct external messaging bypasses approval/receipt boundary.

## Required later cross-checks

- CHUNK 3 Builder: determine worker/subprocess network and secret isolation, especially whether SEC-001 is an actual privilege escalation for model-controlled workers.
- CHUNK 3 Builder: inspect restart/recovery/idempotency, branch/worktree scope, subprocess env sanitization, GitHub mutation boundaries, publish/review SHA integrity, budget enforcement.
- CHUNK 8: revisit the isolated launcher test failure caused by live pidfile contamination; classify test isolation/build debt there, not earlier.
- CHUNKS 10–11: reconcile all NEW/ALREADY TRACKED/IN FLIGHT findings against current main and the PR #600 coverage crosswalk.

## Evidence already run

- Doctor freshness tests: 4 passed but expose unit gap versus actual uvicorn process naming.
- Launcher tests: 11 passed / 1 failed due live canonical pidfile contamination; deferred to CHUNK 8.
- Action/grant focused slice: prior evidence 95 passed.
- MCP/Skill/plugin sidecar: 128 focused hermetic tests passed.
- Hermetic direct-route repros: iMessage sender invoked without action gate; deploy created temp Dockerfile.
- Live safe proxy proof: unauth direct Gateway rejected; originless local native proxy POST reached protected route while causing no state change.
- Hermetic grant precedence repro: session-global allow defeated narrower deny.

## Operating rule from here

Proceed sequentially. One chunk owner at a time. A sidecar may be used only for a narrow, non-overlapping evidence task within the current chunk. At every chunk boundary, update this ledger and produce the next chunk's compact handoff; do not pass entire chat history forward.
