# KITTY AUDIT — CHUNK 2 PARALLEL TRUST REPORT

Scope: MCP / plugin / Skill / reachable subprocess trust seams only  
Mode: READ-ONLY audit  
Repository: `/Users/jacobbrizinnski/Projects/kitty`  
GitHub: `jacob202/kitty`

## Executive conclusion

**VERIFIED CURRENT TRUTH:** there is **no currently reachable prompt-to-MCP-subprocess execution path on current main**. The dangerous-looking `gateway.mcp_tool_bridge.invoke()` function exists, but current Kitty has no production caller or API route for it, no `.mcp.json`, no production plugin registrations, and no advertised MCP tool schemas. Chat also explicitly treats tool execution as caller-owned when a caller supplies tools, and otherwise tells the model tools are unavailable.

The real trust debt is therefore **dormant activation debt, not a current remote-code-execution finding**. Before MCP/third-party capability activation, five boundaries need to remain inside the already-open #545 convergence lane: credential scoping/redaction, per-server/tool approval identity, process cleanup, durable capability identity for enable state, and explicit trust/activation for third-party Skill instructions.

Do **not** create a new architecture or another broad security lane. Issue #545 already owns the correct convergence target. Issue #554/PR #577 already established reusable ActionQueue/grant call-identity semantics, while explicitly leaving MCP server/tool/schema identity for the later MCP bridge work.

No language/framework rewrite is warranted.

---

## Repository truth inspected

### VERIFIED CURRENT TRUTH

Primary source inspection was performed at:

- inspected checkout SHA: `cd1e4d692706c71cbbdfcf44d3ea70b63d20c0ae`
- checkout branch at completion: `fix/native-ui-hierarchy-20260823`
- current local `origin/main`: `35a7e9fab5ec0563027ce08a15f84889ce45a73d`
- live GitHub `main`: `35a7e9fab5ec0563027ce08a15f84889ce45a73d`

The checkout moved onto an unrelated frontend branch while this parallel audit was running. I did not change branches or touch that work.

### Local-vs-origin/main difference

At completion the checkout SHA is two commits behind `origin/main`.

Security/trust target blobs are **byte-identical** between inspected SHA `cd1e4d69` and current `origin/main` `35a7e9fa` for:

- `gateway/mcp_tool_bridge.py`
- `gateway/plugin_registry.py`
- `gateway/skill_registry.py`
- `gateway/skill_import.py`
- `gateway/context_assembler.py`
- `gateway/routes/integrations.py`
- `gateway/routes/completions.py`
- `gateway/auth.py`

`gateway/routes/extended.py` changed after the inspected SHA only in Image Lab generation/provenance sections around `studio_generate`; the Skill routes near the top of the file are unchanged.

Therefore the trust findings below are verified against **current main**, not merely the earlier SHA.

### Dirty state observed, not touched by this audit

At the final check the working tree contained unrelated modifications/untracked work including:

- `config/providers.json`
- `docs/README.md`
- `gateway/kitty-chat/src/components/HomeState.tsx`
- `gateway/kitty-chat/src/components/ProjectsPanel.tsx`
- `docs/audit/README.md`
- `docs/audit/post_audit_support_2026-08-23/`

The audit did not modify these files.

---

## GitHub collision / historical truth

### VERIFIED CURRENT TRUTH

**Issue #545 — OPEN**  
`Adopt Agent Skills + official MCP client/registry; retire custom plugin packaging`

This already owns:

- replacement of the hand-rolled MCP protocol/client path;
- official MCP client lifecycle;
- explicit installed/enabled/trust/provenance state;
- credential references rather than raw secrets in manifests;
- requested secret/env visibility before install;
- scoped approval around MCP tool calls;
- version pinning and integrity verification;
- retirement/shrinking of the empty custom plugin packaging layer.

**Issue #554 — CLOSED / COMPLETED**  
`Converge approvals into scoped grants around the existing action gate`

It explicitly includes MCP server / skill / tool scope and states installation and invocation are separate grants.

**PR #577 — MERGED**  
`feat(actions): bind one-shot approvals to exact call identity`

Its own description explicitly says MCP schema/tool/server identity remains a later MCP-bridge concern because native ActionQueue does not currently own MCP schema identity.

**Issue #539 — CLOSED / COMPLETED; PR #541 MERGED**  
Archived skills were previously surfaced as active capabilities. Current main excludes top-level `_archive` from active discovery.

**PR #566 — MERGED**  
Agent Skills frontmatter/import was made spec-compatible; executable `scripts/*.py` remain rejected by the bundle importer.

**Issue #546** is already marked duplicate of #545.

### Open PR collision check

`gh pr list --state open` filtered for MCP / skill / plugin / capability / grant / approval returned **no relevant open PRs** at the time of this audit.

Several stale local/remote branches with MCP/skill/approval names still exist, but none were current open PRs. Do not treat those stale branch names as in-flight ownership.

---

# Findings

## PAR-SEC-001 — MCP credential handling is inverted: discovery exposes configured env values, while execution ignores the scoped env and inherits Gateway ambient env

- **status:** ALREADY TRACKED
- **category:** credentials / subprocess trust boundary
- **severity:** MEDIUM current dormant risk; HIGH impact if MCP execution is activated without fixing it
- **confidence:** HIGH
- **recommendation class:** REQUIRED before MCP activation

### Exact files / functions / routes

- `gateway/mcp_tool_bridge.py`
  - `list_servers()`
  - `invoke()`
- `gateway/routes/integrations.py`
  - `GET /mcp/servers`
- `gateway/auth.py`
  - `BearerAuthMiddleware`

### Evidence

`list_servers()` reads `.mcp.json` and places each server's raw `env` mapping directly in the returned server dictionary.

`GET /mcp/servers` returns `list_servers()` directly.

`invoke()` calls `asyncio.create_subprocess_exec(command, *args, ...)` **without an `env=` argument**.

A hermetic mock probe confirmed:

- `raw_env_present_in_list_servers = True`
- `subprocess_env_kwarg_present = False`
- `shell_used = False`

Python subprocess semantics with no `env=` mean the child inherits the parent process environment. In Kitty that means an activated MCP process would inherit the Gateway's ambient environment rather than the server's explicitly configured scoped environment.

Current `.mcp.json` is absent and current plugin MCP server count is zero, so no child is being launched today.

### Reproduction

Hermetic only; no real process was started:

1. Create `/tmp/.../.mcp.json` containing a sentinel env key.
2. Patch `gateway.paths.PROJECT_ROOT` to that temp directory.
3. Call `list_servers()` and observe the sentinel value is returned.
4. Patch `asyncio.create_subprocess_exec` and call `invoke()`.
5. Observe no `env` keyword was supplied.

### Realistic Kitty failure path

Once MCP is activated, an untrusted or compromised MCP server process can inherit unrelated Gateway secrets (provider/API credentials, service tokens, etc.) simply because the child gets the complete ambient Gateway environment.

Separately, a configured secret placed directly in `.mcp.json` can be returned through `/mcp/servers` to any authenticated Gateway client and may be copied into frontend state/diagnostics.

### User impact

Credential compromise can cause unauthorized provider use, spend, or account abuse.

### Ops impact

A server can fail authentication despite an apparently correct per-server `env` block because that block is currently ignored at execution time.

### Security impact

Over-broad secret exposure to child processes and unnecessary raw-secret exposure at the discovery API boundary.

### Existing issue / PR collision

**#545 already owns this.** It explicitly requires credential references rather than raw secrets in manifests, requested secret/env inspection, and a proper MCP client lifecycle. Do not open a duplicate broad issue.

### Smallest fix direction

Inside #545:

1. Replace the hand-rolled process/client path with the official MCP client as already decided.
2. Build a **minimal per-server environment** from an explicit safe baseline plus approved server-specific secret references.
3. Never return secret values from capability discovery; return only required secret names/status such as `configured: true/false`.
4. Do not pass the Gateway's entire environment to an untrusted MCP process.

### Regression test type

Hermetic subprocess/client test asserting:

- unrelated Gateway sentinel secrets are absent in the child environment;
- only explicitly approved server env keys are present;
- `/mcp/servers` never returns secret values.

---

## PAR-SEC-002 — Dormant MCP invocation has no approval/call-identity boundary and accepts any tool name a selected server will honor

- **status:** ALREADY TRACKED
- **category:** MCP privilege escalation / approval boundary
- **severity:** MEDIUM dormant risk
- **confidence:** HIGH
- **recommendation class:** REQUIRED before MCP activation

### Exact files / functions / routes

- `gateway/mcp_tool_bridge.py`
  - `invoke(server_name, tool_name, arguments)`
  - `list_tools(server_name)`
- `gateway/action_queue.py` / `gateway/action_grants.py` — existing policy primitives, but **not called by MCP bridge**
- `gateway/routes/completions.py` — current chat tool-execution ownership boundary

### Evidence

`invoke()`:

1. finds a server by `name`;
2. obtains configured `command` and `args`;
3. serializes caller-provided `tool_name` and `arguments` into `tools/call` JSON;
4. launches the process and sends the call.

It does **not**:

- validate `tool_name` against `server["tools"]`;
- bind approval to server identity/version;
- bind approval to tool schema/version;
- bind approval to exact arguments;
- consult ActionQueue or standing grants;
- deny a tool that exists on the server but was never advertised to Kitty.

Static production reference search found **no caller of `mcp_tool_bridge.invoke()`** and no invoke route.

Current Chat does not secretly bridge into it. `gateway/routes/completions.py` states that when the caller supplies tool schemas, the **caller owns execution**. If the caller does not supply tools, Kitty strips tool fields and adds a system instruction that tools are unavailable.

### Reproduction

Static trace:

- `rg` found no production references to `mcp_tool_bridge.invoke` or direct imports of it.
- Inspect `invoke()` and observe there is no grant/ActionQueue/tool-list validation.

No live MCP invocation was performed because no production path is reachable today.

### Realistic Kitty failure path

If a future UI/agent dispatcher wires `invoke()` directly, a model/caller could select a high-risk server tool or changed arguments without crossing Kitty's durable approval boundary.

A server could also expose an undocumented/hidden tool and a direct caller could name it even though Kitty never advertised it.

### User impact

Unexpected filesystem/network/destructive actions once MCP becomes active.

### Ops impact

Invocation evidence would be disconnected from Kitty's existing durable action/approval receipts.

### Security impact

Capability privilege escalation and bypass of per-tool deny semantics.

### Existing issue / PR collision

- **#545:** explicitly requires scoped approvals and proper MCP client integration.
- **#554:** established MCP server/skill/tool scopes in the shared grant model.
- **PR #577:** exact action call identity is merged and explicitly says MCP server/tool/schema identity remains later MCP work.

Do not invent another permission system.

### Smallest fix direction

At the final MCP execution boundary, before `call_tool`:

- resolve an installed, enabled, pinned server identity;
- resolve a discovered tool/schema identity;
- canonicalize the exact arguments;
- evaluate the existing grant/policy semantics for that exact server/tool/call;
- fail closed if server/tool/schema changed after approval.

### Regression test type

Hermetic MCP server tests:

- unapproved tool call denied;
- explicit per-tool deny beats server-level allow;
- hidden/non-discovered tool denied;
- changed arguments invalidate one-shot approval;
- changed server/tool schema invalidates stale approval.

---

## PAR-SEC-003 — MCP timeout returns an error without terminating or reaping the child process

- **status:** ALREADY TRACKED
- **category:** stale autonomous state / subprocess lifecycle
- **severity:** LOW today; MEDIUM once MCP execution is active
- **confidence:** HIGH
- **recommendation class:** REQUIRED before MCP activation

### Exact files / functions

- `gateway/mcp_tool_bridge.py`
  - `invoke()` timeout handling

### Evidence

`invoke()` wraps only `proc.communicate(...)` in `asyncio.wait_for(..., timeout=120)`.

On `asyncio.TimeoutError` it immediately returns:

`{"error": "MCP tool invocation timed out"}`

There is no:

- `proc.terminate()`;
- `proc.kill()` fallback;
- `await proc.wait()` / reap;
- transport/session context cleanup in this hand-rolled path.

Hermetic timeout probe with a fake process confirmed:

- timeout result = `MCP tool invocation timed out`
- `timeout_proc_killed = False`
- `timeout_proc_terminated = False`

### Reproduction

Mock the process object's `communicate()` to hang and mock `wait_for()` to raise `asyncio.TimeoutError`. Observe the function returns without invoking terminate/kill.

No real child was launched.

### Realistic Kitty failure path

When MCP becomes active, a hung or malicious stdio server can remain alive after Kitty reports a timeout. It can retain inherited credentials/file handles and consume resources outside Kitty's visible execution state.

### User impact

Repeated failed calls can leave hidden processes consuming memory/CPU.

### Ops impact

Stale process accumulation and misleading "timed out" state even though work continues out of band.

### Security impact

A process that Kitty considers failed can retain ambient authority after the request lifecycle ends.

### Existing issue / PR collision

The exact timeout symptom is not separately ticketed, but **#545 replaces this hand-rolled MCP lifecycle wholesale with the official SDK**. Opening another broad issue would duplicate the same implementation lane.

### Smallest fix direction

Make clean cancellation/transport shutdown an acceptance requirement of #545. If this function survives temporarily, timeout must terminate, escalate to kill if needed, and reap the process before returning.

### Regression test type

Hermetic fake-process lifecycle test asserting timeout causes:

1. terminate;
2. bounded wait;
3. kill fallback if still alive;
4. final reap/closed transport.

---

## PAR-SEC-004 — Plugin enable state is keyed only by plugin name, not version/source/capability identity

- **status:** ALREADY TRACKED
- **category:** stale authorization state / plugin trust
- **severity:** LOW current because registry has no production plugin registrations; MEDIUM if third-party plugins become real
- **confidence:** HIGH
- **recommendation class:** REQUIRED only if this registry survives; otherwise DELETE

### Exact files / functions / routes

- `gateway/plugin_registry.py`
  - `register()`
  - `enable()`
  - `disable()`
  - `is_enabled()`
  - `_load_db_settings()`
  - `_save_db_settings()`
- `gateway/routes/integrations.py`
  - `POST /plugin/{name}/enable`
  - `POST /plugin/{name}/disable`

### Evidence

The in-memory definition contains:

- name;
- version;
- skills;
- hooks;
- MCP servers.

Durable state stores only:

`plugin_name -> enabled bool`

`is_enabled(name)` applies the existing boolean to whatever definition is currently registered under that name. It does not bind the enable decision to version, source, hash, requested capabilities, MCP servers, or credential scope.

Current production source search found **no plugin registrations**. Runtime discovery therefore has no live plugin capability ecosystem to exploit today.

### Reproduction

Static trace is sufficient:

- inspect the `plugin_settings` read/write shape;
- inspect `is_enabled()` using only the name key;
- inspect `register()` allowing a definition/version independent of persisted identity.

### Realistic Kitty failure path

If a plugin named `foo` was previously enabled and later a different source/version reuses `foo`, stale enabled state can silently apply to the changed capability set.

### User impact

A capability the user never reviewed in its current form can appear enabled because an old same-name version was trusted.

### Ops impact

Difficult-to-explain capability state after upgrades/rollbacks/name collisions.

### Security impact

Stale authorization can survive a materially changed executable/tool surface.

### Existing issue / PR collision

**#545 directly owns this** and already requires installed/enabled state plus source/version/pin/trust/provenance. It also recommends shrinking/deleting the custom plugin packaging layer because it has no real ecosystem.

### Smallest fix direction

Prefer **DELETE** of the custom plugin bundle abstraction if Skills + MCP + Kitty-local installed-capability state cover the real need.

If a registry record survives, enable/trust must bind to an installed capability identity including source + pinned version/hash + requested capability set. Material identity changes should return to disabled/unapproved.

### Regression test type

- same name + same pinned identity preserves enable state;
- same name + changed version/hash/source/capability request does **not** inherit stale enable state.

---

## PAR-SEC-005 — Skill content is a prompt-trust boundary; `allowed-tools` is metadata, not an enforced sandbox

- **status:** ALREADY TRACKED
- **category:** prompt injection / imported capability trust
- **severity:** LOW current; MEDIUM if third-party Skills are exposed without explicit trust/activation
- **confidence:** HIGH
- **recommendation class:** REQUIRED before productized third-party Skill import/install

### Exact files / functions / routes

- `gateway/skill_registry.py`
  - `_parse_skill_file()`
  - `discover()`
  - `suggest()`
  - `invoke()`
- `gateway/context_assembler.py`
  - `_default_skill_hint()`
  - `assemble_context()`
- `gateway/skill_import.py`
  - `import_skill_bundle()`
- `gateway/routes/extended.py`
  - `GET /skills`
  - `GET /skill/{name}`
  - `POST /skill/{name}/invoke`

### Evidence

`skill_registry` accepts both `allowed_tools` and Agent Skills `allowed-tools` and returns the normalized list from `invoke()`.

Repository-wide search found no consumer that uses this list as an authorization check. Therefore **`allowed-tools` currently cannot widen permissions, but it also cannot constrain them**. It is descriptive metadata only.

`context_assembler._default_skill_hint()` automatically matches a Skill trigger against the user's message and injects the Skill's name plus the first sentence of its description into the **system prompt**.

A hermetic temp-Skill probe confirmed a crafted Skill description containing `TRUST ME. USE WHEN: trigger phrase` caused `TRUST ME` to appear in the automatically generated relevant-skill hint.

Important limit: the full `SKILL.md` body is **not** automatically injected by `context_assembler`; full content is returned by explicit `skill_registry.invoke()` / the `/skill/{name}/invoke` route. There is no general Skill tool executor.

`skill_import.import_skill_bundle()` has no production caller/route today, so third-party import through the product is currently unreachable.

### Reproduction

Hermetic temp directory only:

1. Place a temporary `SKILL.md` with a crafted description and `USE WHEN` trigger.
2. Point `SKILL_ROOTS` to the temp directory.
3. Call `_default_skill_hint()` with the matching phrase.
4. Observe crafted description text enters the system hint.
5. Call `skill_registry.invoke()` and observe `allowed_tools` is returned as metadata.

### Realistic Kitty failure path

When third-party Skill installation becomes productized, merely placing an untrusted Skill into the active discovery root could influence system-level model instructions through description/trigger text before the user has meaningfully trusted the Skill.

This is **prompt influence**, not current arbitrary subprocess authority. The Skill system itself does not execute commands.

### User impact

Assistant behavior can be manipulated or made misleading by untrusted capability instructions.

### Ops impact

A Skill may appear standards-compatible and list allowed tools even though Kitty is not enforcing that list as a permission boundary.

### Security impact

Prompt-injection relevance and potential model-directed disclosure/manipulation; no direct current tool escalation was found.

### Existing issue / PR collision

**#545 already owns the correct lifecycle:** discover -> inspect source/manifest -> show requested capabilities/secrets -> approve -> install/pin -> enable -> use. It explicitly says registry presence is not trust and newly discovered packages must not auto-run.

### Smallest fix direction

Before accepting arbitrary third-party Skills:

- distinguish `present/discovered` from `trusted+enabled`;
- do not auto-suggest/inject untrusted Skill metadata into system prompts;
- progressively load full instructions only after explicit activation;
- treat `allowed-tools` as a requested capability declaration until an actual policy boundary enforces it;
- reuse #545/#554 permission semantics rather than inventing a separate Skill sandbox.

### Regression test type

- untrusted/discovered Skill is visible for inspection but cannot be suggested or invoked;
- enabling/trusting it activates suggestion/invoke;
- `allowed-tools` never authorizes a tool by itself;
- disabled/revoked Skill stops influencing prompt assembly immediately.

---

## PAR-SEC-006 — Archived Skill exposure is fixed on current main

- **status:** FIXED CURRENT MAIN
- **category:** stale capability lifecycle
- **severity:** historical MEDIUM; current NONE
- **confidence:** HIGH

### Exact files / functions

- `gateway/skill_registry.py`
  - `_scan_directories()`

### Evidence

Current scanner skips a Skill when the first relative path component under the Skill root is `_archive`.

Read-only discovery evidence during the audit:

- all `SKILL.md` files: 21
- archived files: 8
- non-archive files: 13
- active discovered skills: 13
- archived names present in active registry: `[]`

Focused hermetic tests also passed.

### Existing issue / PR collision

- Issue #539: CLOSED / COMPLETED
- PR #541: MERGED

### Smallest fix direction

None. Preserve the regression test. Broader disabled/trust lifecycle remains #545, not #539.

### Regression test type

Existing archive discovery/suggest/invoke tests are appropriate.

---

# Disproven concerns / non-findings

## No current prompt-to-arbitrary-subprocess path

**VERIFIED CURRENT TRUTH:** `mcp_tool_bridge.invoke()` has no production caller and no API route. Current MCP server count/tool schema count is zero and `.mcp.json` is absent.

A normal Kitty prompt cannot currently cause this function to run.

## No shell injection in the MCP launcher

`invoke()` uses `asyncio.create_subprocess_exec`, not a shell. Configured `command` and `args` are passed as argv. `tool_name` and tool arguments are serialized to JSON on stdin; they are not interpolated into a shell command.

This does **not** make an untrusted server safe, but it disproves direct shell metacharacter injection through tool arguments in this bridge.

## Prompt/repository content cannot currently choose the MCP executable through the invocation API

`server_name` selects a preconfigured server; the executable and argv come from server configuration/plugin definition. `tool_name` and arguments do not overwrite `command`/`args`.

A repository change could of course modify Python source itself, which is ordinary code-review trust, not a special MCP escape.

## No current MCP ActionQueue bypass in production

The dormant `invoke()` function lacks a gate, but because nothing calls it, there is no presently reproducible production bypass. This becomes a required activation gate, captured above as PAR-SEC-002.

## Plugin enable/disable routes are not unauthenticated

All mounted Gateway routes are protected by `BearerAuthMiddleware` except `/health`. Missing `GATEWAY_SECRET` fails closed with 503 outside explicit test mode.

No network-auth bypass specific to `/plugin/{name}/enable|disable` was found.

## Plugin registry currently has no production capability ecosystem

Static source search found no production `plugin_registry.register(...)` calls. `get_enabled_skills()` and `get_enabled_hooks()` have no production consumers. The plugin layer is therefore mostly an empty/legacy shell today, not a hidden execution ecosystem.

## Skill importer has strong structural archive defenses

`gateway/skill_import.py` currently rejects:

- absolute paths and `..` traversal;
- executable/nested archive extensions;
- renamed PE/ELF/ZIP/GZIP/OLE binary prefixes;
- oversized entries/bundles;
- extreme compression ratios;
- multiple/nested `SKILL.md` files;
- partial installs on extraction failure.

It also rejects executable `scripts/` payloads because executable extensions are not allowed.

No zip-slip/binary-script execution issue was reproduced.

## `allowed-tools` does not itself grant authority

It is metadata only. A malicious Skill cannot gain a tool merely by naming it in frontmatter. The corresponding weakness is the absence of enforcement if future callers mistakenly treat the metadata as a sandbox; that is captured in PAR-SEC-005.

## No current Skill-to-subprocess execution engine

`skill_registry.invoke()` renders prompt text and metadata. It does not execute shell commands, Python scripts, MCP tools, or filesystem operations.

## No duplicate execution/spend mechanism found in these seams

The dormant MCP bridge performs one process/call attempt and has no retry loop. The timeout leak can leave a stale child, but no automatic duplicate tool call or provider-spend retry was found in this scoped path.

## Legacy plugin JSON migration is not active from a current source file

`plugin_registry` contains a one-time compatibility migration from `data/plugin_settings.json`; the nominal read path can perform that migration. No such legacy source file exists under the default current repository data path, so no current stale-enable import source was found.

---

# Dead-code / reachability classification

| Component | Classification | Evidence |
|---|---|---|
| `mcp_tool_bridge.list_servers()` | ACTIVE | `GET /mcp/servers`; native frontend fetches it |
| `mcp_tool_bridge.get_tool_schema_for_llm()` | ACTIVE read surface | `GET /mcp/tools`; native frontend fetches it |
| `mcp_tool_bridge.list_tools()` | LIKELY DEAD | no production caller found |
| `mcp_tool_bridge.invoke()` | LIKELY DEAD / DORMANT | no production caller/import/route found |
| `plugin_registry.list_plugins()/enable()/disable()` | ACTIVE state surface | Gateway routes + native frontend |
| plugin registry package/bundle model | LEGACY BUT STILL REACHABLE | state/UI routes remain, but zero production registrations; #545 plans shrink/delete |
| `plugin_registry.get_enabled_mcp_servers()` | ACTIVE support seam | read by MCP discovery |
| `plugin_registry.get_enabled_skills()` | LIKELY DEAD | no production consumer found |
| `plugin_registry.get_enabled_hooks()` | LIKELY DEAD | no production consumer found |
| `skill_registry` discovery/search/suggest/invoke | ACTIVE | context assembler + Skill routes + selected legacy task use |
| `.agents/skills/_archive/**` as capabilities | CONFIRMED DEAD | filtered from active registry on current main |
| `skill_import.import_skill_bundle()` | LIKELY DEAD / library-only | tests exist; no production caller/route found |
| plugin legacy JSON migration | COMPATIBILITY SHIM | one-time migration path retained; current source JSON absent |

---

# Threat-model answers

## Can prompt/repository content widen permissions?

**Current prompt:** NO direct MCP/Skill permission widening was found. `allowed-tools` is not authorization. MCP invoke is not reachable from chat.

**Future third-party Skill/MCP content:** YES if #545 activation lifecycle is wired without explicit trust/grants. This is already tracked.

## Can prompt content choose commands?

**Current main:** NO. There is no prompt -> MCP invoke dispatcher. Even inside `invoke()`, the process executable/argv come from installed/configured server state, not tool arguments.

## Can these seams leak secrets?

**Current active execution:** no live MCP server path exists.

**Dormant MCP bridge:** YES when activated unless fixed: the child would inherit Gateway ambient env, while discovery can return raw configured server env values. PAR-SEC-001.

## Can they invoke arbitrary subprocesses?

**Current product path:** NO.

**Dormant MCP bridge:** it can start any executable present in trusted MCP configuration/plugin definition. No shell is used. Therefore install/config trust is the critical boundary.

## Can they bypass ActionQueue/approval policy?

**Current product path:** no reproducible bypass because MCP invocation is unreachable.

**Dormant `invoke()`:** it contains no ActionQueue/grant check, so wiring it directly would create a bypass. PAR-SEC-002.

---

# Testing and measurements performed

## Focused hermetic tests

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 ./venv/bin/python -m pytest \
  -p no:cacheprovider \
  --basetemp=/tmp/kitty-audit-chunk2-pytest \
  tests/test_skill_registry.py \
  tests/test_skill_suggest.py \
  tests/test_ported_skills.py \
  tests/test_skill_runtime_discovery.py \
  tests/test_aim42_skill.py \
  tests/test_dth05_skill_import.py \
  tests/test_plugin_registry.py \
  tests/test_storage_router.py \
  tests/test_integrations_routes.py -q
```

Result:

- **128 passed**
- 1 unrelated Starlette/httpx deprecation warning
- pytest cache disabled
- temp base under `/tmp`
- no dependency installation

## Hermetic MCP process-boundary probe

Used `unittest.mock` and temp config under `/tmp`; no real child was executed.

Observed:

```text
raw_env_present_in_list_servers=True
invoke_succeeded_with_mock=True
subprocess_env_kwarg_present=False
shell_used=False
timeout_result=MCP tool invocation timed out
timeout_proc_killed=False
timeout_proc_terminated=False
```

## Hermetic Skill prompt probe

Used a temp Skill root under `/tmp`.

Observed:

```text
skill_description_auto_injected_into_hint=True
allowed_tools_returned=['read']
```

## Static reachability

Searches confirmed:

- no production reference to `mcp_tool_bridge.invoke()`;
- no production import of `skill_import.import_skill_bundle()`;
- no production plugin registration;
- no ActionQueue/grant reference inside the MCP/plugin/Skill implementation files;
- `allowed_tools` has no authorization consumer.

---

# Safety note about audit execution

No source/config/Git/GitHub changes were intentionally made. Tests were directed to `/tmp` and did not use canonical plugin DB paths.

One earlier read-only runtime-count probe called `plugin_registry.list_plugins()`. That function internally calls Kitty's migrate-on-read compatibility path. No repository change occurred and the current legacy `plugin_settings.json` source is absent, but because I did not capture a byte-level before/after checksum of canonical `kitty.db`, **whether that defensive migrate call performed a no-op write is UNKNOWN**. No further canonical registry calls were made after recognizing this behavior.

---

# Recommendation priority

## REQUIRED

Before any real MCP tool invocation is exposed:

1. complete #545 official MCP client replacement;
2. minimize/scoped child credentials and redact discovery output;
3. route every MCP call through existing scoped grant/call-identity semantics;
4. bind approval to pinned server + discovered tool/schema + exact arguments;
5. guarantee cancellation/timeout process cleanup;
6. ensure third-party Skills/MCP units have explicit trust/provenance/enable lifecycle.

If the custom plugin package abstraction is not needed after this, **delete it rather than hardening an empty ecosystem**.

## DEFENSE-IN-DEPTH

After the required boundaries exist:

- run MCP stdio children with an explicit controlled `cwd` rather than ambient process cwd where practical;
- expose redacted capability health/version/provenance in runtime diagnostics;
- cap stdout/stderr/result sizes so a malicious server cannot create unbounded memory/log pressure;
- record invocation receipts with server/tool/version/schema identity.

These are useful but should not delay the core #545 boundary work.

## ENTERPRISE HARDENING — NOT NEEDED

For Kitty's single-user, local-first threat model, do **not** add OPA/Cedar/Rego, Kubernetes-style isolation, a custom plugin PKI, seccomp/container orchestration for every local tool, or a new RBAC service unless future real multi-user/network deployment changes the threat model.

---

# Final disposition

The scoped trust surface is smaller than it appears:

- Skills are currently prompt content, not executable code.
- Plugin packaging is an almost-empty legacy shell.
- MCP discovery is visible, but MCP execution is dormant.
- The dangerous subprocess/credential/approval bugs are therefore **activation blockers**, not evidence that Kitty is presently executing arbitrary MCP commands from prompts.

The right move is **CONSOLIDATE + FIX inside #545 using the already-merged grant primitives, then DELETE obsolete plugin plumbing**. Do not create a competing architecture or duplicate broad issue.
