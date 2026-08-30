# CHUNK 2 — Security / Trust Boundaries — Completed 2026-08-23

## Audit pin

- Canonical checkout inspected: `/Users/jacobbrizinnski/Projects/kitty`
- Security-sensitive source inspected at `cd1e4d692706c71cbbdfcf44d3ea70b63d20c0ae`.
- Current `origin/main` at close: `d11febfb9974d41c00a836d0450a10916c72add1`.
- Relevant CHUNK 2 files are unchanged between those revisions; later changes were CI/Image Lab only.
- Canonical working tree contained unrelated user/other-lane edits. Audit did not touch them.
- AgentRouter lane: user reports DONE; it is not an unresolved audit lane.

## Executive conclusion

Kitty's canonical native chat is materially safer than the legacy shell: when the caller does not supply a tool executor, `gateway/routes/completions.py` explicitly tells the model tools are unavailable, and current native chat does not execute model tool calls itself.

The highest-confidence current trust defects are not "LLM can run arbitrary tools". They are policy-boundary defects around direct side-effect routes and standing-grant precedence. MCP/plugin/Skill execution debt is mostly dormant and already owned by #545.

## Promoted findings

### AUTH-002 — session-scoped global allow can outrank a narrower deny
- Status: **ALREADY TRACKED** — explicitly called out as a follow-up in merged PR #579, but still unfixed.
- Severity: **HIGH**. Confidence: **HIGH**. Recommendation: **REQUIRED**.
- Evidence: `gateway/action_grants.py::_specificity()` assigns global=0, mcp_server=1, tool=2, then adds `+10` for any session-bound grant. `_winning_grant()` chooses the maximum specificity before deny/ask/allow tie-breaking.
- Hermetic isolated-DB repro: narrower deny id=1 + session-bound global allow id=2 produced `outcome=allow`, `grant_id=2`.
- Failure path: a temporary broad allow can defeat an enduring "never allow here/tool" restriction.
- Fix direction: session lifetime/applicability must not outrank scope specificity; preserve fail-closed deny semantics.
- Required regression: project/tool deny + session-global allow => DENY; exact one-shot approval semantics remain unchanged.

### AUTH-003 — direct iMessage send bypasses the approval/receipt boundary
- Status: **NEW**. Severity: **HIGH**. Confidence: **HIGH**. Recommendation: **REQUIRED**.
- Location: `gateway/routes/integrations.py::POST /imessage/send` -> `gateway/imessage.py::send()` -> `osascript` Messages send.
- No ActionQueue/grant/receipt call exists in the route.
- Hermetic route repro patched `is_available()` and `send()`: HTTP 200 and one sender invocation, with no action row/approval involved.
- This conflicts with the accepted rule that consequential outbound communication remains explicitly approved and that work-causing operations have durable receipts.
- No frontend caller was found, but the HTTP route is active and bearer-authenticated.
- Fix direction: prefer DELETE if unused; otherwise route through the existing action/approval boundary, not a new gate.
- Required regression: direct route cannot dispatch; exact approved action dispatches once and records receipt/call identity.

### SEC-001 — secret-bearing native proxy trusts originless loopback callers
- Status: **NEW / DESIGN QUESTION**. Severity: **MEDIUM** today. Confidence: **HIGH** on behavior; exploitability depends on lower-trust local-process network reachability.
- Location: `gateway/kitty-chat/src/lib/gateway-proxy-config.ts`, `src/app/proxy/[...path]/route.ts`.
- `isTrustedProxyRequest()` accepts a loopback Host with no Origin. The proxy then injects the Gateway bearer secret and forwards GET/POST/DELETE/PUT/PATCH to arbitrary Gateway paths.
- Live non-mutating proof: direct unauthenticated Gateway request => 401; originless request through native `/proxy` => protected route succeeds. A same-target provider-switch POST returned 200 without changing provider state.
- Browser cross-origin requests and LAN/tailnet Hosts are correctly rejected; this is specifically a local-process confused-deputy boundary.
- CHUNK 3 must determine whether Builder/model subprocesses are actually network-confined. If they are not, this becomes a REQUIRED boundary; if they already have equivalent ambient authority, treat it as defense-in-depth/design debt rather than a standalone privilege escalation.
- Regression if remediated: an uncredentialed lower-trust local worker cannot use native proxy to acquire Gateway authority.

### AUTH-004 — `/deploy` is an active arbitrary-directory filesystem write without receipt/approval
- Status: **NEW**. Severity: **MEDIUM**. Confidence: **HIGH**.
- Location: `gateway/routes/integrations.py::POST /deploy`, `gateway/deploy.py::_deploy_docker()`.
- Caller supplies `target_dir`; for `platform=docker`, Kitty creates `Dockerfile` in any existing writable target that lacks one.
- Hermetic temp-dir repro returned `dockerfile_ready` and created the file.
- No ActionQueue/receipt is involved; no frontend caller was found.
- Fix direction: prefer DELETE if obsolete; if retained, constrain target roots and put mutation behind the existing recorded action boundary.
- Regression: arbitrary outside-root target rejected; retained supported target produces a durable receipt.

### COR-004 — `GET /notify/test` performs an external side effect
- Status: **NEW**. Severity: **LOW/MEDIUM**. Confidence: **HIGH**.
- Location: `gateway/routes/extended.py::GET /notify/test` -> `gateway.notify.send()` -> Pushover HTTP POST.
- A GET request can therefore send a real push notification when configured.
- Fix direction: make it POST or remove it; do not keep state-changing GET semantics.
- Regression: GET is read-only/absent; explicit POST test action records the attempted send.

## MCP / plugin / Skill sidecar dispositions

A dedicated read-only sidecar ran 128 focused hermetic tests and static reachability checks. Its important result: **no current prompt-to-MCP-subprocess execution path exists on current main**. `mcp_tool_bridge.invoke()` has no production caller/API route, `.mcp.json` is absent, and no production plugin registrations exist.

### PAR-SEC-001 — MCP env handling leaks raw configured env on discovery while execution would inherit Gateway ambient env
- Status: **ALREADY TRACKED #545**. Current severity MEDIUM dormant / HIGH if activated. REQUIRED before MCP activation.

### PAR-SEC-002 — dormant MCP invoke lacks approval/server/tool/schema/argument identity binding
- Status: **ALREADY TRACKED #545**. MEDIUM dormant. REQUIRED before activation.

### PAR-SEC-003 — MCP timeout returns without terminating/reaping child
- Status: **ALREADY TRACKED #545**. LOW dormant / MEDIUM if activated. REQUIRED before activation.

### PAR-SEC-004 — plugin enable state is keyed by name only, not source/version/hash/capability identity
- Status: **ALREADY TRACKED #545**. LOW current; prefer DELETE of empty custom plugin packaging unless retained.

### PAR-SEC-005 — Skill content is a prompt-trust boundary; `allowed-tools` is metadata, not an authorization sandbox
- Status: **ALREADY TRACKED #545**. LOW current / MEDIUM if third-party Skills are productized.
- Important non-finding: naming a tool in Skill frontmatter does not itself grant authority today.

### PAR-SEC-006 — archived Skill exposure
- Status: **FIXED ON CURRENT MAIN** via prior Skill archive work. Do not reopen.

## Important non-findings

- Gateway bearer auth fails closed when secret is missing outside test mode.
- Gateway canonical bind is loopback; CORS is narrowly scoped to local UI origins.
- Native canonical chat does not currently execute model tool calls.
- Current MCP subprocess execution is dormant/unreachable.
- No shell injection was found in MCP launcher construction (`create_subprocess_exec`, no shell).
- Skill bundle importer already rejects Zip Slip, zip bombs, executable/nested-archive payloads, and nested `SKILL.md` activation tricks.
- Plugin registry currently has no production capability ecosystem.
- No current Skill-to-subprocess execution engine exists.

## Collision updates

- REL-003 (AgentRunner orphan `autonomy_sessions`) is now **ALREADY TRACKED as #592**.
- Legacy `gateway/task_runner.py` deletion is **IN FLIGHT as PR #593**; do not duplicate it.
- #545 owns MCP/Skill/plugin convergence. Do not create a competing MCP security architecture.
- PR #579 explicitly records the AUTH-002 precedence defect as an unfixed follow-up.
- AgentRouter is reported DONE by Jacob and is not an active audit blocker.

## CHUNK 2 close verdict

Security architecture does not need a rewrite. Required convergence is narrow:
1. preserve deny precedence in grants;
2. remove or gate direct consequential side-effect routes;
3. verify lower-trust Builder subprocess network/secret authority in CHUNK 3;
4. complete #545 before activating MCP execution;
5. delete obsolete plugin/MCP plumbing rather than hardening an unused ecosystem.
