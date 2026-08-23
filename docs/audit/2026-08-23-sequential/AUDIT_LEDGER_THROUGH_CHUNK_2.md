# Sequential Audit Ledger — Through CHUNK 2

Authority at close: `origin/main@d11febfb9974d41c00a836d0450a10916c72add1`
Audit chunks completed: 0, 1, 2

| ID | Status | Severity | Summary |
|---|---|---:|---|
| COR-001 | NEW | MEDIUM | Gateway freshness diagnostic is nonfunctional on actual macOS uvicorn runtime |
| DOC-001 | ALREADY TRACKED / DESIGN QUESTION | MEDIUM | Constitution/OpenWebUI shell authority conflicts with accepted native-product ADR |
| DOC-002 | NEW | MEDIUM | Current runnable architecture doc is materially stale |
| REL-001 | ALREADY TRACKED #537 | MEDIUM | Desktop supervisor stop->ensure Gateway race; legacy/manual path |
| REL-002 | NEW | HIGH | ActionQueue can strand `executing` actions across restart with ambiguous external effect |
| AUTH-001 | NEW | HIGH | T2 Calendar direct route bypasses ActionQueue |
| COR-002 | NEW | MEDIUM | approve+remember can return failure after durable approval succeeded |
| REL-003 | ALREADY TRACKED #592 | HIGH | AgentRunner active sessions have no restart reconciliation; canonical DB had 623 stale active rows |
| COR-003 | NEW | MEDIUM | `./kitty up` can exit success when Gateway never becomes healthy |
| REL-004 | DESIGN QUESTION / NEW | MEDIUM | `./kitty down` kills unrelated occupants of Kitty ports |
| AUTH-002 | NEW | HIGH | Session-global allow can outrank narrower persistent deny |
| AUTH-003 | NEW | HIGH | Direct iMessage/notification sends bypass durable approval/receipt policy |
| SEC-001 | DESIGN QUESTION / NEW | MEDIUM | Secret-bearing native proxy trusts originless loopback local requests |
| PAR-SEC-001 | ALREADY TRACKED #545 | MEDIUM dormant | MCP discovery exposes env while execution ignores scoped env / inherits ambient env |
| PAR-SEC-002 | ALREADY TRACKED #545 | MEDIUM dormant | Dormant MCP invoke lacks approval/call identity |
| PAR-SEC-003 | ALREADY TRACKED #545 | LOW dormant | MCP timeout does not terminate/reap child |
| PAR-SEC-004 | ALREADY TRACKED #545 | LOW current | Plugin enable trust bound only to name |
| PAR-SEC-005 | ALREADY TRACKED #545 | LOW current | Skill prompt trust + non-enforced `allowed-tools` metadata |
| PAR-SEC-006 | FIXED ON CURRENT MAIN | NONE current | Archived Skills no longer surface as active |

## High-risk items currently open

1. REL-002 — ActionQueue crash-after-claim ambiguity.
2. AUTH-001 — direct Calendar T2 bypass.
3. REL-003 — AgentRunner restart/orphan state; now tracked by #592.
4. AUTH-002 — grant precedence lets broad session allow defeat narrow deny.
5. AUTH-003 — direct external messaging bypasses durable approval/receipt policy.

## In flight / collisions

- PR #593 / `chore/delete-legacy-task-runner-20260822`: delete legacy task_runner lane; do not duplicate.
- #545: official MCP client + Agent Skills/capability trust convergence; owns PAR-SEC-001..005.
- #592: AgentRunner restart reconciliation; owns REL-003.
- AgentRouter: DONE per Jacob during CHUNK 2; remove from unresolved lane list.
- Existing unrelated native UI and provider-config edits in the canonical checkout are not audit work and were not staged/touched.

## Next sequential chunk

CHUNK 3 — KittyBuilder.

Start from current repository/GitHub/runtime truth, then inspect Builder mission -> initiative -> packet -> attempt -> worker -> validation/review/publish lifecycle, lease/restart recovery, idempotency, branch/worktree isolation, approval boundaries, evidence/receipts, cancellation/timeouts, stale workers, duplicate execution/spend, and current operator surface. Reconcile every finding against current issues/PRs/branches before promoting it.
