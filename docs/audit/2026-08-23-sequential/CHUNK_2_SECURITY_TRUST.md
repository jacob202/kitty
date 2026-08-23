# CHUNK 2 — Security / Trust Boundaries

Status: COMPLETE
Audit date: 2026-08-23
Current repository authority at close: `origin/main@d11febfb9974d41c00a836d0450a10916c72add1`
Primary inspected product-security blobs were unchanged from `cd1e4d692706c71cbbdfcf44d3ea70b63d20c0ae` except unrelated Image Lab pricing/provenance code in `gateway/routes/extended.py`.

## Executive conclusion

Kitty's canonical native chat is materially safer than the old architecture implied: it does not execute LLM tool calls itself when the caller supplies no executor, Gateway bearer auth is fail-closed, Gateway and the native product bind to loopback by default, cross-origin proxy POSTs are rejected, Skill imports reject executable/archive payloads, and the custom plugin/MCP execution ecosystem is currently dormant.

The important live trust defects are narrower:

1. a T2 Calendar create route bypasses the existing ActionQueue approval boundary;
2. session-scoped global standing allows can outrank narrower persistent denies;
3. outbound iMessage/notification routes can perform external communication without a durable action receipt/approval boundary;
4. the native secret-bearing proxy deliberately trusts originless loopback requests, so it must not be treated as an isolation boundary from lower-trust local processes;
5. the dormant hand-rolled MCP bridge has credential, approval-identity, and process-cleanup blockers that are already owned by #545 and must be fixed before activation.

No new architecture is warranted. Reuse ActionQueue/grants, finish #545, delete obsolete plugin plumbing where possible, and keep native chat's no-tool-executor boundary explicit.

## Findings

### AUTH-001 — T2 Calendar creation bypasses ActionQueue
- Status: NEW
- Category: approval boundary / external side effect
- Severity: HIGH
- Confidence: HIGH
- Recommendation: REQUIRED
- Location: `gateway/routes/calendar.py::calendar_create`, `config/action_tiers.json`, `gateway/action_queue.py`
- Evidence: `calendar.event.create` is T2 in the signed tier sheet and has an ActionQueue executor, but `POST /calendar/create` directly invokes `calendar_integration.create()`.
- Reproduction: isolated FastAPI test with mocked Calendar create returned 200, called the external-effect seam once, and created no ActionQueue proposal/receipt.
- Failure path: any authenticated Gateway/native-proxy caller can create a calendar event without the exact-call approval record required for T2.
- Fix direction: delete the direct create route if unused; otherwise make it propose/execute through the existing ActionQueue only.
- HIGH regression: isolated HTTP integration proving the direct route cannot invoke Calendar create without a fingerprint-bound approved action.

### AUTH-002 — Session-scoped global allow overrides narrower persistent deny
- Status: NEW
- Category: scoped grant precedence / authorization
- Severity: HIGH
- Confidence: HIGH
- Recommendation: REQUIRED
- Location: `gateway/action_grants.py::_winning_grant`, `_specificity`, `_applies`, `evaluate`
- Evidence: scope rank is global=0, server/project=1, tool=2, then any session-bound grant receives `+10`. This makes session lifetime outrank authorization scope.
- Hermetic repro: persistent project deny for `calendar.event.create` on project `42` plus session-only global allow for session `s1`; evaluating project `42` in `s1` returned `allow` from the global grant.
- Failure path: a broad session allow can silently defeat a narrower deny for the same capability.
- Fix direction: compare authorization scope specificity first; treat session as applicability/tie-break within the same scope rather than adding it to the scope rank.
- HIGH regression: project/tool deny must beat broader session-global allow; exact-scope session policy may only refine equal-scope policy.

### AUTH-003 — Direct outbound messaging routes bypass durable approval/receipt policy
- Status: NEW
- Category: external communication / approval boundary
- Severity: HIGH
- Confidence: HIGH
- Recommendation: REQUIRED
- Location: `gateway/routes/integrations.py::imessage_send`, `gateway/routes/extended.py::notify_send`, `notify_test`
- Evidence: `POST /imessage/send` directly invokes `gateway.imessage.send`; hermetic route repro returned 200 and called the sender with no ActionQueue rows. `POST /notify` does the same for Pushover. `GET /notify/test` is state-changing and sends a real notification when configured.
- Product-policy relevance: the signed UX rule keeps destructive/paid/external-send actions behind explicit approval; the Constitution requires work-causing operations to have durable receipts.
- Failure path: an authenticated client can communicate externally without a durable user-approved action identity. The state-changing GET also weakens browser-side trust assumptions.
- Fix direction: route consequential outbound sends through existing action policy/receipt machinery; make GET routes pure.
- HIGH regression: outbound transport seam must not be called before an approved exact action; retry must not duplicate external sends.

### SEC-001 — Native proxy is a credential-bearing loopback deputy, not a local-process isolation boundary
- Status: DESIGN QUESTION / NEW
- Category: local trust boundary / confused deputy
- Severity: MEDIUM
- Confidence: HIGH
- Recommendation: DEFENSE-IN-DEPTH unless lower-trust local agents are expected to be isolated from Gateway authority
- Location: `gateway/kitty-chat/src/lib/gateway-proxy-config.ts::isTrustedProxyRequest`, `src/app/proxy/[...path]/route.ts`
- Evidence: loopback Host with no Origin is explicitly accepted; the proxy injects the Gateway bearer secret and forwards arbitrary GET/POST/DELETE/PUT/PATCH paths. Live read-only probes showed unauthenticated direct Gateway `/projects` -> 401 while native `/proxy/projects` -> 200. A no-op provider-switch POST through the proxy also returned 200.
- Limits: cross-origin browser POSTs with Origin are rejected; this is not a remote-network auth break. Same-user unsandboxed processes may already be able to read `.env`, so do not overstate the privilege gain.
- Failure path: any future lower-trust local process that can reach loopback but cannot read the secret can still obtain Gateway authority through the proxy. Originless GET acceptance combines poorly with state-changing GET endpoints such as `/notify/test`.
- Fix direction: do not use loopback/origin checks as agent isolation. Either constrain the proxy to the explicit UI capability surface or sandbox lower-trust workers from the product loopback plane. Eliminate state-changing GETs.
- Regression: originless untrusted local requests cannot mutate arbitrary Gateway routes; GET endpoints remain side-effect free.

### PAR-SEC-001 — MCP credential handling is inverted
- Status: ALREADY TRACKED (#545)
- Severity: MEDIUM dormant / HIGH if activated
- Confidence: HIGH
- Summary: `/mcp/servers` can expose raw configured env values while `invoke()` ignores server-scoped `env` and would inherit the Gateway ambient environment.
- Required before activation: minimal child env, redacted discovery, official MCP client lifecycle.

### PAR-SEC-002 — Dormant MCP invocation lacks approval/call-identity binding
- Status: ALREADY TRACKED (#545 / existing grant primitives)
- Severity: MEDIUM dormant
- Confidence: HIGH
- Summary: `invoke()` accepts caller tool name/arguments and has no ActionQueue/grant binding. No production caller exists today.
- Required before activation: bind server/version/tool/schema/arguments to the existing approval identity.

### PAR-SEC-003 — MCP timeout does not terminate/reap child
- Status: ALREADY TRACKED by #545 replacement lane
- Severity: LOW dormant / MEDIUM if active
- Confidence: HIGH
- Required before activation: terminate -> bounded wait -> kill fallback -> reap/close transport.

### PAR-SEC-004 — Plugin enable state is keyed only by name
- Status: ALREADY TRACKED (#545)
- Severity: LOW current / MEDIUM if third-party plugins become real
- Confidence: HIGH
- Summary: stale enabled state can transfer to a changed same-name capability because version/source/hash are not part of durable identity.
- Preferred direction: DELETE custom plugin packaging if Skills + MCP cover the real need; otherwise bind trust to pinned identity.

### PAR-SEC-005 — Skill metadata is a prompt-trust boundary; `allowed-tools` is not an enforced sandbox
- Status: ALREADY TRACKED (#545)
- Severity: LOW current / MEDIUM if third-party Skill installation is productized
- Confidence: HIGH
- Summary: Skill descriptions can influence system-level hint text; `allowed-tools` is descriptive metadata with no authorization consumer. There is no Skill subprocess executor today.
- Required before third-party activation: discovered != trusted/enabled; untrusted Skill metadata must not auto-influence prompt assembly.

### PAR-SEC-006 — Archived Skill exposure
- Status: FIXED ON CURRENT MAIN
- Historical severity: MEDIUM
- Current severity: NONE
- Confidence: HIGH
- Collision: #539 closed, PR #541 merged.

## Disproven / bounded concerns

- Native chat does not execute LLM tool calls when no caller executor is supplied; it explicitly tells the model tools are unavailable.
- No current prompt-to-arbitrary-subprocess path was found through Skills/MCP/plugins.
- MCP launcher uses `create_subprocess_exec`, not shell expansion.
- No `.mcp.json` is present in the canonical checkout at the inspected point.
- No production plugin registrations were found.
- Skill bundle import rejects Zip Slip, zip bombs, executables, nested archives, renamed binary payloads, and `scripts/`.
- `allowed-tools` cannot itself grant authority.
- Cross-origin native-proxy POSTs are rejected; SEC-001 is a local-process/design-boundary issue, not a general remote auth bypass.

## Test / measurement evidence

- Parallel hermetic Skill/plugin/integration slice: 128 passed.
- Hermetic MCP boundary probe: raw env visible in discovery; child env kwarg absent; timeout returned without terminate/kill.
- Hermetic Skill probe: crafted Skill description entered the relevant-skill hint; `allowed_tools` remained metadata only.
- Hermetic grant precedence probe: project deny + session-global allow => incorrectly `allow`.
- Prior isolated direct-route repros: Calendar direct create and iMessage direct send invoked effect seams with zero ActionQueue record.
- Live read-only proxy probe: direct Gateway without bearer 401; native proxy 200; no-op same-provider POST accepted through proxy.

## Collision updates

- REL-003 AgentRunner restart gap is now ALREADY TRACKED as GitHub #592.
- Legacy task-runner deletion remains IN FLIGHT on PR #593 / branch `chore/delete-legacy-task-runner-20260822`; do not duplicate.
- MCP/Skill/plugin remediation is ALREADY TRACKED by #545; no competing architecture or broad issue should be opened.
- AgentRouter lane was reported DONE by Jacob during this chunk and should not remain in unresolved audit state.

## CHUNK 2 conclusion

The live security priority is to close the existing approval-boundary holes (AUTH-001, AUTH-002, AUTH-003), preserve fail-closed bearer/loopback behavior, and keep dormant MCP execution dormant until #545 satisfies credential, exact-call identity, and lifecycle requirements.

No source mutation was performed by the audit.
