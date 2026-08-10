# KittyBuilder MCP v2 — Dogfood & Proof Design

**Status:** Approved design, implementation not yet authorized  
**Date:** 2026-08-10  
**Base:** `d54fd8966edd1f8a14802ed19e26a07917498caf` (KittyBuilder MCP v1)  
**Parent mission:** KPROOF-001

## 1. Decision this version must prove

V1 established a governed MCP boundary over KittyBuilder. V2 must prove that the boundary is usable as an operating system, not merely present in source code.

The decision is:

> Can Jacob start the KittyBuilder MCP path with one obvious command, diagnose it when it is unhealthy, drive one real approved software Mission through Builder, and continue that same work from a fresh conversational session without manually reconstructing context?

V2 succeeds only with runtime evidence from the canonical Mac checkout. Documentation, unit tests, commits, worker narration, and a successful MCP handshake are supporting evidence, not substitutes for the real loop.

## 2. Scope

V2 adds four bounded capabilities:

1. `kitty mcp up|down|status|doctor` — one operator surface for the existing v1 server.
2. Ordered end-to-end diagnostics that identify the earliest broken boundary and one corrective action.
3. `kitty mcp proof` — a proof runner/receipt path for one real KPROOF software Mission using the existing MCP and Builder contracts.
4. A fresh-session continuity proof that rehydrates the Mission through `resume_context()` without a pasted transcript.

V2 does **not** add another orchestrator, database, queue, worker protocol, generic shell, generic filesystem mutation, new model router, broad UI redesign, or a larger MCP tool surface unless implementation discovers a concrete missing primitive that makes the approved proof impossible. Such a discovery returns to design review rather than silently expanding scope.

## 3. Architecture

```text
Jacob / conversational client
           |
           | MCP
           v
  KittyBuilder MCP v1 server
           |
           | existing canonical tools
           v
      KittyBuilder
           |
           | durable state/evidence
           v
 queue -> worker -> validation -> review -> publication

Operator sidecar only:

./kitty mcp up/down/status/doctor/proof
           |
           +-- supervises MCP process
           +-- probes boundaries
           +-- records bounded proof receipts
           +-- never becomes execution authority
```

The `kitty` launcher remains the operator entry point. The MCP server remains the conversational adapter. KittyBuilder remains the sole execution authority.

No v2 component may decide that work is complete from process exit, log text, model output, or HTTP success. Completion comes from the existing durable Builder result/evidence contract.

## 4. Operator lifecycle

### `kitty mcp up`

Starts the v1 KittyBuilder MCP server in Streamable HTTP mode on loopback, using the repository Python environment and the configured local port.

Requirements:

- default host remains `127.0.0.1`;
- default port remains the v1 value unless already configured;
- writes a PID file under the existing Kitty runtime PID area and logs under the existing logs area;
- refuses to take over a port owned by an unrelated process or another Kitty worktree;
- repeated `up` is idempotent when the expected healthy process is already running;
- never installs dependencies implicitly and never exposes the server publicly.

### `kitty mcp down`

Stops only the MCP process proven to belong to this Kitty repository/worktree and removes its PID file. It does not kill an unrelated process merely because that process occupies the configured port.

### `kitty mcp status`

Returns a compact human view by default and structured JSON with `--json`.

Minimum facts:

- expected checkout/root;
- configured transport/host/port;
- process ownership/aliveness;
- listener state;
- MCP initialize/tool-list probe result;
- Builder durable-state availability;
- overall state: `healthy | degraded | stopped | conflict | unavailable`;
- one `next_action`.

Status is observational. It does not install, migrate, start, recover, or mutate Builder state.

## 5. Doctor: earliest broken boundary wins

`kitty mcp doctor [--json]` runs ordered checks. Later checks may be skipped when an earlier dependency makes them meaningless.

Order:

1. **Canonical checkout** — this is the expected Kitty repository and Git state is intelligible.
2. **Runtime** — configured Python exists and the pinned MCP dependency imports at the supported v1 API.
3. **Process ownership** — PID/listener state is coherent and not owned by an unrelated checkout/process.
4. **Transport** — an MCP client can initialize against the local server.
5. **Tool contract** — the expected v1 high-level tools are discoverable; forbidden raw tools are absent.
6. **Cold-start truth** — `kitty_context()` returns a usable/truthful receipt or an explicit attention state.
7. **Builder truth** — read-only Builder status can be obtained without creating/migrating storage.
8. **Repository execution prerequisites** — Git/worktree prerequisites required by Builder are available.
9. **GitHub publication prerequisites** — `gh`/repository publication readiness is reported when publication is part of the requested proof. Missing GitHub readiness must not make local MCP reads look unhealthy.
10. **Provider readiness** — report whether a free route is runnable; paid routes are informational only unless explicitly authorized elsewhere.

Every check emits a bounded record:

```json
{
  "id": "transport.initialize",
  "state": "pass|fail|blocked|warn|unknown",
  "summary": "...",
  "evidence": {"...": "bounded facts"},
  "next_action": "one concrete action or null"
}
```

Top-level output includes `ok`, `state`, `first_failure`, `checks`, and exactly one recommended `next_action`.

Doctor must distinguish **local defect** from **external/unavailable dependency**. For example, GitHub Actions runner allocation problems are not reported as a Kitty code failure.

## 6. MCP probing must use the real protocol

Doctor/proof must not prove MCP health by importing `mcp.builder.server` and calling Python functions directly.

For transport/tool checks it creates a real MCP client session against the configured loopback endpoint and performs, at minimum:

1. initialize;
2. list tools;
3. call a read-only tool such as `kitty_context()`;
4. validate the domain receipt (`ok/state/error`), not merely protocol success.

This proves the same serialization/transport/tool-registration seam an actual client depends on.

## 7. Proof runner

### `kitty mcp proof`

This is an evidence collector and gate runner, not a second workflow engine.

It operates on a **real explicitly approved Builder Mission**. It does not create a fake success path, bypass `mission_prepare/mission_approve`, auto-approve user intent, or mutate code itself.

The final KPROOF run must use a real product interaction/feature that satisfies KPROOF-001, not a toy `hello world` change. A synthetic fixture may be used in automated tests for deterministic error cases, but cannot satisfy the product proof.

The proof lifecycle is:

```text
preflight doctor
  -> resolve exact Mission ID
  -> prove approved design/plan/base linkage
  -> observe/start Builder through existing MCP command
  -> poll durable work_status (bounded cadence)
  -> inspect work_result
  -> require deterministic validation evidence
  -> require independent review evidence when the Mission contract requires it
  -> require runtime/product evidence required by KPROOF
  -> require PR/publication evidence when publication was approved
  -> write proof receipt
```

The runner may call existing MCP tools. It may not write Builder SQLite directly, parse worker prose as truth, merge a PR, authorize spend, or silently publish.

### Proof receipt

Runtime proof receipts live under ignored app-owned runtime data, for example:

`data/kittybuilder/mcp-proof/<proof-id>.json`

They are evidence, not a new state authority. All durable task facts inside them include source identifiers/SHAs so they can be recomputed from Builder/Git/GitHub.

Minimum receipt fields:

- proof schema/version and timestamp;
- v2 code SHA and canonical checkout identity;
- Mission ID + immutable manifest hash;
- approved design path/SHA;
- approved plan path/SHA;
- Builder task/attempt IDs;
- validation verdict/commands summary;
- independent review verdict/evidence when required;
- runtime/product validation evidence;
- PR number/head SHA/check state when applicable;
- blocker/unknowns;
- verdict `pass | fail | incomplete`;
- one next action.

`pass` is impossible if required evidence is unknown.

## 8. Fresh-session continuity proof

V1's `resume_context()` is the continuity primitive. V2 proves it through a fresh MCP client session.

After the real Mission reaches a meaningful durable state, the proof runner closes its MCP client session and opens a **new** session with no previous response object or transcript injected. The new session calls only:

`resume_context(mission_id="<id>")`

The proof compares the recovered receipt against durable expected identities, not against natural-language similarity.

Required equality/invariants:

- same Mission ID and manifest identity;
- same approved design path/SHA;
- same approved plan path/SHA;
- same original code base identity;
- current Builder task/attempt identity is truthful;
- validation/review evidence is present when durably available;
- PR identity/head is present when durably available;
- blocker/unknowns are preserved rather than erased;
- exactly one non-empty next action exists.

No copied conversation text is permitted in the new session setup. The proof receipt records that the continuity check used a newly initialized MCP session.

## 9. Client connection

V2 remains client-agnostic. It does not fork server behavior for ChatGPT, Claude, Open WebUI, or Kitty.

The required operational contract is a healthy Streamable HTTP endpoint plus a machine-readable connection summary from `kitty mcp status --json` containing the local endpoint and supported transport.

Where a client currently cannot invoke custom write-capable MCP tools, that is reported as a client/product deployment limitation, not worked around by weakening KittyBuilder's boundaries.

A first-party Kitty chat UI integration is **not** required for v2. The proof can be driven by any compatible conversational client plus the v2 protocol proof client. UI integration is a later product slice once the execution seam earns trust.

## 10. Safety and authorization

V1 authorization rules remain unchanged:

- free execution is the default;
- paid execution requires explicit authorization;
- Mission approval remains explicit and version-bound;
- publication requires its separate explicit confirmation;
- no merge tool is added;
- no deletes/account/security/auth changes are added;
- public MCP bind remains refused.

`kitty mcp proof` must stop with `incomplete` if it reaches an authorization gate it cannot cross. It reports the required decision instead of treating the gate as failure or bypassing it.

## 11. Failure handling

Failures are classified by boundary:

- `checkout` — wrong/ambiguous repository;
- `runtime` — Python/dependency mismatch;
- `process` — dead/stale/conflicting process;
- `transport` — MCP initialize/session failure;
- `contract` — expected tools/receipt shape mismatch;
- `context` — cold-start authority attention/unknown;
- `builder` — durable state unavailable/corrupt/blocked;
- `execution` — Builder cannot make progress under its own contract;
- `validation` — deterministic checks fail or are missing;
- `review` — required independent review fails/missing;
- `runtime_product` — launched-product behavior does not satisfy acceptance;
- `publication` — PR/GitHub readiness/evidence failure;
- `continuity` — fresh session cannot reconstruct durable truth;
- `external` — provider/GitHub/platform dependency unavailable.

The diagnosis should expose root evidence but keep the default human output short: what failed, why that matters, and the next action.

## 12. Testing strategy

Implementation follows TDD and separates deterministic tests from the final live proof.

### Deterministic tests

- CLI parsing/delegation for `mcp up/down/status/doctor/proof`;
- PID ownership and unrelated-port refusal;
- idempotent start/stop;
- no public bind;
- ordered doctor short-circuit/first-failure behavior;
- structured JSON schema and one-next-action rule;
- real MCP protocol initialize/list/call against an ephemeral local server;
- forbidden tool absence;
- proof receipt cannot pass with missing required evidence;
- proof runner never auto-approves/publishes/spends/merges;
- fresh-session continuity uses two distinct sessions and no carried transcript;
- external dependency outage is classified separately from local defect.

### Repository gates

Run the focused tests first, then the repository lint/typecheck/pytest/UI gates required by current main. If hosted GitHub Actions again fails before executing steps, canonical Mac execution is the verification authority and the unavailable CI condition is recorded explicitly.

### Live acceptance

The final live test occurs on Jacob's canonical Mac checkout and uses a real KPROOF feature/interaction. Runtime product behavior outranks the deterministic suite.

## 13. Acceptance contract

V2 passes only when all of the following are evidenced on the canonical Mac checkout:

1. `kitty mcp up` starts the correct loopback MCP server from a stopped state.
2. Repeating `up` does not create a duplicate owner.
3. `kitty mcp doctor --json` completes with no local blocking failure.
4. A real MCP client initializes, lists the governed v1 tools, and calls `kitty_context()` successfully/truthfully.
5. One real explicitly approved KPROOF software Mission is driven through existing KittyBuilder execution.
6. Builder produces deterministic validation evidence and required independent review evidence.
7. The relevant behavior works in the launched product/application, not merely in tests.
8. Publication/PR evidence is captured if separately authorized.
9. A newly initialized MCP client session recovers the same Mission/artifact/execution truth with `resume_context()` and no pasted transcript.
10. `kitty mcp proof` emits a `pass` receipt only after all required evidence exists.
11. `kitty mcp down` stops only its owned process and leaves unrelated processes untouched.

If the system still requires Jacob to manually coordinate workers/agents, reconstruct old context, or guess which subsystem failed, KPROOF has not passed.

## 14. Explicit non-goals for v2

- polished Builder dashboard or new chat UI;
- ChatGPT-specific account/product workarounds;
- automatic PR merge;
- additional provider routing architecture;
- new memory system;
- background notification framework;
- broad computer control;
- replacing FastMCP v1 solely for novelty;
- replacing KittyBuilder with another workflow engine;
- declaring the broader Kitty product proven from unit tests alone.

## 15. Expected implementation footprint

Keep implementation small and reuse the existing launcher/helpers where practical. Likely areas are:

- `kitty` — `mcp` command group and process lifecycle wiring;
- a focused Python operator module under `mcp/builder/` for protocol probes, doctor, and proof receipt logic;
- focused tests for lifecycle/doctor/proof/continuity;
- `docs/KITTYBUILDER_MCP.md` — operator commands and evidence semantics.

Do not move Builder state or MCP domain logic into the shell launcher. Shell owns dispatch/process lifecycle; Python owns structured diagnostics/protocol proof; Builder owns execution truth.
