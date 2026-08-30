# KittyBuilder Brain V1 — source harvest

Status: evidence-backed architecture decision, prepared 2026-07-25.

This document replaces the speculative assumption that Kitty needs another orchestrator. KittyBuilder already owns packet state, dependency eligibility, attempts, isolated worktrees, branch leases, validation, review, repair, evidence and publishing. External systems are candidates only for worker-session integration and operator visibility. They must not become a second queue or second source of truth.

## Decision

Build the cockpit inside Kitty. Keep KittyBuilder as the sole orchestrator. Integrate workers through a backend-neutral `WorkerSession` boundary. Implement the first production adapter against OpenCode's headless server/API, retain the current shell adapter, and prototype an Oh My Pi in-process/RPC adapter only if it provides a material reliability or observability advantage. Reimplement the cockpit in Kitty's React application; do not embed or fork a separate terminal application.

The initial implementation order is:

1. OpenCode server adapter and canonical worker events.
2. Canonical KittyBuilder runtime snapshot.
3. Replayable SSE event stream.
4. Native Kitty multi-pane cockpit.
5. Canonical operator commands.
6. Recommend-only decision engine.
7. Bounded autopilot.

## Existing Kitty authority — do not duplicate

The following areas remain owned by Kitty and are explicitly outside any imported worker framework:

- initiative manifests and packet dependency eligibility
- durable queue and attempt accounting
- isolated worktree creation and cleanup
- branch leases and worker identity verification
- allowed-path/scope enforcement
- validation and independent-review gates
- repair-loop budgets and stop classification
- commits, PR attachment, publishing and completion receipts

External code may report worker lifecycle and execution evidence into these systems. It may not mutate their storage directly or infer packet completion.

## Harvest register

### 1. OpenCode — ADOPT API; ADAPT event normalization

Repository: `anomalyco/opencode` (historical `sst/opencode` URL redirects)
Pinned inspection SHA: `7534d23551f665e65080809975b4ca5c7d63807b`
License: MIT

Concrete implementation surfaces:

- `packages/opencode/src/session/session.ts` — session lifecycle and session-level events
- `packages/opencode/src/session/status.ts` — typed `session.status` (verified: `Info` aliases `SessionStatusEvent.Info`; `idle` drops the session from the active map)
- `packages/opencode/src/session/message-v2.ts` and `packages/opencode/src/session/processor.ts` — messages, parts and tool activity
- `packages/opencode/src/bus/` — event publication/subscription
- `packages/opencode/src/server/server.ts` — server bootstrap only; it delegates routes to `./routes/instance/httpapi/server` and `./routes/instance/httpapi/public`
- `packages/opencode/src/server/routes/instance/httpapi/` — actual route definitions (`api.ts`, `handlers/`, `groups/`, `websocket-tracker.ts`)
- `packages/opencode/src/server/event.ts` — server event *schemas* (type contracts, not the endpoint)
- `packages/opencode/src/event-manifest.ts`, `packages/opencode/src/event-v2-bridge.ts` — top-level event catalogue and v2 bridge
- `packages/client/`, `packages/sdk-next/` — generated client SDKs, **TypeScript only**

Useful behavior:

- client/server separation already treats the TUI as only one possible client
- session events include create/update/delete/diff/error/status and message/part updates
- headless `opencode serve` is an intended integration surface
- server-side sessions preserve OpenCode's own transcript/tool semantics

Kitty destination:

- `gateway/builder_worker_session.py`: `OpenCodeServerSession`
- `gateway/builder_events.py`: normalize OpenCode events into Kitty envelopes
- process supervisor starts or attaches to one local OpenCode server and records its base URL/version

Do not port OpenCode's queue semantics or UI wholesale. Use its supported server API. Do not scrape TUI output except as fallback evidence.

Required adapter operations:

- health/version check
- create or resume session scoped to the packet worktree
- send the bounded worker brief
- subscribe to events
- normalize assistant text, reasoning metadata when exposed, tool start/end, file changes, status, error and idle
- abort/cancel
- fetch final transcript and diff references
- reconnect after temporary transport failure

Risk: event delivery is live transport, not proof of Kitty packet completion. Kitty must reconcile final state against its own attempt, git, validation and review authorities.

### 2. Oh My Pi — ADAPT selectively; prototype behind the same contract

Repository: `can1357/oh-my-pi`
Pinned inspection SHA: `667111575ebba136dadfd6989379e7f67e0d40d9`
License: MIT

Concrete implementation surfaces:

- `packages/coding-agent/src/sdk.ts` — `createAgentSession`, model/auth/tool discovery, `EventBus`, lifecycle wiring
- `packages/coding-agent/src/session/agent-session.ts` — session prompt/steer/follow-up/abort and event subscription
- `packages/coding-agent/src/session/session-manager.ts` — persistent and in-memory session management, list/open/continue/fork
- `packages/coding-agent/src/utils/event-bus.ts` — event bus primitive
- `packages/coding-agent/src/task/executor.ts` — subagent-oriented task execution
- `packages/coding-agent/src/task/output-manager.ts` — task output/artifact handling
- ACP/RPC implementation and `docs/sdk.md` — cross-process integration and permission routing

Useful behavior:

- a documented in-process SDK rather than an opaque CLI
- file-backed or in-memory sessions
- direct event subscription
- explicit `abort()`
- model/auth registry and tool allowlisting
- SDK options intended for orchestrators: output schema, yield requirement, task depth and parent task prefix

Kitty destination:

- optional `OhMyPiSession` implementation of the same `WorkerSession` interface
- use RPC/ACP rather than embedding Bun/TypeScript directly into the Python gateway unless measurements justify an in-process sidecar

Do not import its agent registry, task recursion or session persistence as Kitty's orchestration authority. Kitty should own the packet and worktree; OMP owns only the coding conversation it is running.

Decision gate: implement after OpenCode adapter only if a small spike proves better cancellation, reconnect, structured tool events or model routing with acceptable operational complexity.

### 3. oh-my-opencode-slim — ADAPT lifecycle ideas; do not make it the orchestrator

Repository: `alvinunreal/oh-my-opencode-slim`
Pinned source inspection SHA: `a6541cb154d168a2034099006dbe1c33a27d7c89`
License: MIT

Concrete implementation surfaces:

- `src/hooks/task-session-manager/event-router.ts` — routes `session.created`, disposal, idle/status, error and deletion
- `src/hooks/task-session-manager/idle-reconciliation.ts` — delayed reconciliation of ambiguous idle sessions
- `src/hooks/task-session-manager/pending-call-tracker.ts` — correlates parent calls with child sessions
- `src/hooks/task-session-manager/continuation-evaluator.ts` — bounded continuation decisions
- `src/hooks/task-session-manager/status-utils.ts` — truthful status derivation
- `src/hooks/task-session-manager/board-injection.ts` — compact background-job state projection
- `src/utils/background-job-store.ts` — task/job status records
- `src/agents/orchestrator.ts` — scheduler-oriented prompt policy
- `docs/background-orchestration.md` — intended lifecycle

High-value patterns:

- register a child session as soon as `session.created` arrives, before later hooks can be cancelled
- correlate parallel children using parent session plus agent identity
- delay idle reconciliation to avoid racing foreground ownership
- distinguish retryable/failover errors from terminal failures
- retain completed job summaries for injection into the parent
- make ambiguous state explicit instead of reporting false completion

Kitty destination:

- tests and algorithms in `builder_worker_session.py` and `builder_events.py`
- cockpit attention/status projection
- decision-engine rules for disconnected, idle-but-unreconciled and terminal-error states

Do not copy its prompt-driven scheduler into Kitty. Kitty's durable queue, leases, dependency graph and attempts are stronger. Reuse lifecycle lessons, not authority.

### 4. Architect — STUDY interaction model; independently implement

Repository: `forketyfork/architect`
Pinned inspection SHA: `772fd0a9df002fd16dc5d143fc344399d6314810`
Implementation language: Zig with SDL3 and `ghostty-vt`
Maturity: explicitly experimental

Concrete surfaces:

- `docs/ARCHITECTURE.md` — application/runtime/render boundaries
- `src/app/runtime.zig` — terminal/process runtime and agent-status handling
- `src/render/renderer.zig` — grid rendering and visual emphasis

What to keep:

- all active workers visible at once
- strong attention indication for approval/waiting/completed states
- one action to focus a worker without losing the grid context
- terminal identity remains separate from task identity

Kitty destination:

- React/CSS cockpit layout and accessible attention states
- no Zig, SDL or terminal-emulator dependency

Architect is a product-reference source, not a code dependency. Kitty already has a web app and requires remote/mobile access; embedding another native terminal would recreate the fragmentation this project is meant to remove.

### 5. Claurst — STUDY manager/executor semantics only

Repository: `Kuberwastaken/claurst`
License: GPL-3.0
Implementation: Rust

Concrete areas to inspect when refining decision rules:

- `src-rust/` managed-agent implementation
- manager/executor templates and message contracts
- chat-forking and memory-consolidation behavior
- `spec/` for behavioral decomposition

Decision: no code copying into Kitty. Its GPL license and clean-room Claude-Code focus make direct reuse inappropriate. Use it to test whether Kitty's planner/executor boundaries omit a useful state or handoff, then implement independently.

### 6. oh-my-openagent (omo) — STUDY agent architecture; ADAPT plugin lifecycle patterns

Repository: `code-yeongyu/oh-my-openagent` (npm: `oh-my-opencode`, dual-published as `omo`)
Pinned inspection SHA: `b5d56246f6c1b744fdb6238ea34b2c2215ad2e8d`
License: MIT (at pinned SHA; note: `dev` branch carries a Sustainable Use License — prefer the MIT-licensed tag)
Implementation language: TypeScript

Concrete implementation surfaces:

- `src/index.ts` — plugin entry, hooks wiring, agent registration, background automation
- `src/create-hooks.ts` — hook lifecycle registration
- `src/create-managers.ts` — manager initialization
- `src/create-tools.ts` — tool creation and registration
- `src/plugin-config.ts` — configuration loading and schema validation
- `src/plugin-state.ts` — plugin-scoped state management
- `src/plugin-interface.ts` — plugin type contracts
- `src/plugin-handlers/` — individual handler implementations
- Agents: Sisyphus (orchestrator) with Prometheus (Planner) and Metis (Plan Consultant)
- Background tasks with per-provider/model concurrency limits
- Category-based domain delegation (visual, business-logic, custom)
- 11 agents, 54 lifecycle hooks, 5 built-in MCPs
- `docs/` — SDK documentation

High-value patterns:

- background-task lifecycle with per-model concurrency limits — a primitive Kitty's queue already solves at the database layer, but the concurrency-per-model cap is a useful scheduling constraint Kitty's claim-next does not express
- category-based delegation — domain-specific task routing that could influence Kitty's model-selection policy without replacing the queue
- plugin-scoped state that survives configuration reload — relevant and feasible since the supervisor owns the session lifecycle
- LSP tool integration as a built-in MCP — a concrete path to structural code awareness

Kitty destination:

- study the background-task concurrency model as a scheduling input for KB-BRAIN-06 (decision engine)
- the plugin lifecycle hooks pattern may inform KB-BRAIN-01's `WorkerSession` event taxonomy
- category-based routing is a model-policy concern, not a queue replacement

Do not import the agent registry, task recursion subsystems, or multi-harness abstraction layer. Kitty does not need a plugin system for agents — it needs an event taxonomy and scheduling policy.

### 7. oh-my-claudecode — STUDY state-management and cross-reset persistence patterns

Repository: `Yeachan-Heo/oh-my-claudecode`
Pinned inspection SHA: `d0fdaa7b93a8930fd665c2d3115975b13b016d32`
License: MIT
Implementation language: TypeScript (32K stars, teams-first multi-agent orchestration for Claude Code)

Concrete implementation surfaces:

- `docs/ARCHITECTURE.md` — four-system architecture: Hooks → Skills → Agents → State
- `src/installer/index.ts` — installation into `~/.claude/` config directory
- `.omc/` state directory structure:
  - `.omc/state/autopilot-state.json` — autopilot progress tracking
  - `.omc/state/team/` — team task state
  - `.omc/state/sessions/{sessionId}/` — per-session state
  - `.omc/notepad.md` — compaction-resistant memo pad
  - `.omc/project-memory.json` — project knowledge store
  - `.omc/plans/` — execution plans
  - `.omc/notepads/{plan-name}/` — per-plan learnings, decisions, issues, problems
  - `.omc/autopilot/spec.md` — autopilot artifacts
  - `.omc/research/` — research results
  - `.omc/logs/` — execution logs

High-value patterns:

- state that survives context-window compaction through file-backed persistence — directly analogous to Kitty's need to preserve packet context across worker sessions
- per-plan knowledge capture (learnings, decisions, issues, problems) — a structured evidence artifact that Kitty's final-report mechanism already approximates but without the categorization
- autopilot progress as serialized state — a model for KB-BRAIN-07's bounded-autopilot checkpoint format
- compaction-resistant memo pad — a fallback channel for critical state when the primary context budget is exhausted, relevant to KB-BRAIN-01's `WorkerSnapshot` contract

Kitty destination:

- KB-BRAIN-01 `WorkerSnapshot` should include a structured evidence block with learnings/decisions/issues categories
- KB-BRAIN-07 autopilot checkpoint should serialize to a file that survives worker-process restart
- KB-BRAIN-02 runtime snapshot should capture compaction-level state

Do not copy the Claude Code hook system, agent registry, or installer. Kitty already has `builder_identity.verify_and_escalate`, `builder_queue.py`, and `builder_run.py` for these concerns.

### 8. OpenCode Swarm — STUDY plan-ledger and serial task execution

Repository: `ZaxbyHub/opencode-swarm`
Pinned inspection SHA: `4802189f`
License: MIT
Implementation language: TypeScript (408 stars, 6,000+ tests, 580 releases)

Concrete implementation surfaces:

- `src/index.ts` — plugin entry, pipeline tracker, system enhancer, compaction customizer, context budget handler, delegation gate, guardrails, automation manager
- `docs/architecture.md` — hub-and-spoke control model: Architect → Explorer → SME → Coder → Reviewer → Test Engineer → Critic
- `docs/plan-durability.md` — `.swarm/plan-ledger.jsonl` for crash-safe plan persistence
- Per-agent model configuration with heterogeneous model mixing
- Serial execution: one task at a time, phased planning with acceptance criteria
- Plan review gate (critic) before implementation
- Persistent `.swarm/` directory: `context.md`, `plan.md`, `history/`
- Background automation manager with PlanSyncWorker (`plan.json → plan.md` sync)
- Multiple swarm configurations with agent name prefixing

High-value patterns:

- plan-ledger as an append-only JSONL — the simplest possible durable plan format; a single-line append survives crashes that would corrupt a structured file
- phased planning with per-task acceptance criteria — mirrors Kitty's packet-level acceptance criteria but at a finer grain; relevant to KB-BRAIN-06's decision engine
- critic gate before execution — Kitty already has this as the independent-review gate (`builder_loop.py` stage `STAGE_REVIEW`)
- heterogeneous per-agent model selection — Kitty's `builder_runner.py` already supports per-packet model policy; this adds per-phase model selection as a future optimization
- serial execution by design — aligns with Kitty's single-worker-per-lease architecture

Kitty destination:

- KB-BRAIN-06's decision engine should produce a ranked next-action list, not an autopilot — the plan-ledger pattern shows how to persist that without a database migration
- Kitty's review gate is already stronger than Swarm's critic (independent worker, not a different model prompt)
- Swarm's heterogeneous-model mixing is not needed until Kitty supports per-phase model assignment

Do not import the agent framework, prompt templates, or task-execution loop. Kitty's queue, leases, and validation are already the stronger primitives.

### 9. DeepSeek-Coder and awesome-deepseek-agent — REJECT as orchestrator source; keep as model/provider research

Repository: `DeepSeek-AI/DeepSeek-Coder`, `deepseek-ai/awesome-deepseek-agent`

DeepSeek-Coder is primarily a model/training/inference repository. `awesome-deepseek-agent` is a curated index of integration guides, not implementation code. The index surfaces DeepSeek-native harnesses (`Reasonix`, `DeepSeek-TUI`, `Deep Code`) as terminal coding assistants — their value is model integration, not orchestration architecture.

Use DeepSeek models through existing provider adapters where they meet quality/cost requirements. Do not design KittyBuilder's state machine around model-specific repositories.

### 10. cmux (manaflow-ai/cmux, formerly coder/cmux) — REJECT for code; STUDY UX patterns only

Repository: `manaflow-ai/cmux` (redirects from `coder/cmux`)
Pinned inspection SHA: current `main` (no stable tag pinned — actively developed)
License: **GPL-3.0-or-later** — code cannot be copied into Kitty (MIT)
Implementation: Swift + AppKit, native macOS app using libghostty for terminal rendering

Concrete UX surfaces to study:

- vertical sidebar tabs showing git branch, PR status/number, working directory, listening ports, latest notification per workspace — the information density Kitty's cockpit sidebar should match or exceed
- notification rings around panes + unread badges + notification panel + macOS desktop notifications — Kitty's Repairs primitive already delivers structured alerts; cmux's visual-ring pattern is a UX refinement
- `Cmd+Shift+U` jumps to most recent unread agent needing attention — Kitty should have a single-key equivalent to focus the worker that last requested attention
- session restore: saved layout, working directories, scrollback, agent resume — Kitty's worktree and branch-lease system already preserves more state; cmux's UX for presenting restored sessions is the study target
- 1–8 jump-to-workspace keybindings — Kitty's cockpit should support keyboard navigation among workers
- in-app browser pane with scriptable API — out of scope for Kitty, which already has a web app
- split panes with directional focus — the cockpit grid layout should support focus management

Kitty destination:

- React/CSS cockpit layout at design phase — no cmux code, no Swift, no terminal-emulator dependency
- keyboard navigation and attention-state UX are the product-reference targets
- Kitty's web app already solves the remote/mobile requirement that cmux cannot

## Canonical WorkerSession contract

The implementation packet should start from this backend-neutral shape rather than importing a framework's object model:

```text
WorkerSession
  start(worktree, brief, model_policy) -> SessionIdentity
  resume(identity) -> SessionIdentity
  send_instruction(identity, text)
  events(identity, cursor?) -> ordered WorkerEvent stream
  snapshot(identity) -> WorkerSnapshot
  cancel(identity, reason)
  transcript(identity) -> evidence reference
  dispose(identity)
```

`WorkerEvent` must include:

- stable event id and timestamp
- backend/session identity
- packet and attempt correlation
- lifecycle state
- assistant text delta or completed message
- tool/command start, output summary and completion
- changed-path/diff signal
- model/provider and usage when available
- attention/permission request
- error, cancellation and idle
- raw backend payload reference for debugging

Backends may emit richer events. They may not emit `packet_completed`; that conclusion belongs to Kitty after git, validation and review reconciliation.

## Cockpit architecture

The cockpit is a Kitty route/mode backed only by gateway APIs:

- left: initiatives and packet dependency tree
- centre: worker grid or selected live transcript
- right: authoritative inspector for brief, attempt, model, branch, worktree, HEAD, changed paths, commits, validation, review, blockers and evidence
- bottom/expandable: ordered event timeline and raw-log link

Desktop supports a grid of workers. Mobile shows the worker list, one selected transcript and an inspector sheet. No frontend SQLite access, no direct tmux scraping and no worker-owned queue mutations.

## What should be implemented, not researched again

KB-BRAIN-01 should now implement the backend-neutral contract plus the OpenCode server adapter. Its worker does not need to repeat this ecosystem survey. It should verify the pinned API paths it touches, write focused adapter tests, and preserve the shell fallback.

An Oh My Pi spike should be a separate optional packet after OpenCode integration, not a blocker. OMO Slim's lifecycle cases should be converted into tests for the canonical adapter/event layer. Architect and Claurst should not become dependencies.

## Primary code-harvest verdict

- **OpenCode:** use the supported server/session/event API directly.
- **Oh My Pi:** best alternative adapter; prototype only after OpenCode.
- **OMO Slim:** harvest reconciliation and status logic as tests/algorithms.
- **oh-my-openagent (omo):** study background-task concurrency and category-based delegation; do not import the agent registry or multi-harness layer.
- **oh-my-claudecode:** study cross-compaction state persistence and autopilot checkpoints; do not import the Claude Code hook system.
- **OpenCode Swarm:** study plan-ledger durability and serial task execution; do not import the agent framework.
- **Architect:** reproduce the operator experience in Kitty React.
- **Claurst:** study only (GPL-3.0 — no code copying).
- **cmux (manaflow-ai/cmux):** study UX patterns only (GPL-3.0 — no code copying).
- **DeepSeek-Coder / awesome-deepseek-agent:** model options, not orchestration substrates.

This is enough evidence to unblock KB-BRAIN-01 without asking a coding worker to perform another broad repository survey.

## Review addendum — 2026-07-26

Added during review of commit `03cce01`. The external survey holds up; the
Kitty-side half of the packet objective ("Inspect Kitty's current Builder
runtime/UI") was never written down, and three citations were wrong.

### Citation corrections (verified at the pinned SHAs)

- `packages/opencode/src/session/index.ts` **does not exist**. The directory
  has no `index.ts`; the file is `session/session.ts`. Corrected above.
- `packages/opencode/src/server/server.ts` is bootstrap, not routes. The
  `GET /event` claim was the only integration surface in the document cited
  without a file path — and it is the surface the entire adapter
  recommendation rests on. Routes live under
  `server/routes/instance/httpapi/`. **Transport is unconfirmed**: that
  directory contains `websocket-tracker.ts`, so KB-BRAIN-03's "use SSE
  unless the harvest demonstrates a need for WebSocket" rests on an
  assumption the harvest never tested. KB-BRAIN-01 must confirm the actual
  event transport before the envelope design is frozen.
- OpenCode ships **no Python SDK** — `packages/client/` and
  `packages/sdk-next/` are TypeScript. Kitty's gateway is Python, so
  "use the generated SDK" is not available; the adapter must speak raw
  HTTP/stream against an API with no compatibility guarantee. That is a
  cost the ADOPT verdict should carry explicitly.

Verified as accurate: both pinned SHAs resolve, the `sst/opencode` →
`anomalyco/opencode` redirect is real, and every cited path in
oh-my-opencode-slim, oh-my-pi and architect exists. Licenses check out
(slim: MIT, architect: MIT).

### Kitty inventory the register omitted

The register names Kitty destinations but never inventories what Kitty
already has, so three of its destinations would duplicate live code:

| Harvest destination | Already exists | Consequence if ignored |
| --- | --- | --- |
| "replayable SSE event stream" (KB-BRAIN-03) | `gateway/sse.py` (`SSEBroadcaster`), `/stream` in `gateway/app.py`, `useSSE()` in `src/lib/sse.ts` | A second, parallel SSE stack |
| "canonical runtime snapshot" (KB-BRAIN-02) | `gateway/builder_status.py::build_status_snapshot()` — already `schema_version: 2` with an `integrity` partial/complete signal | A second read model over the same tables |
| "native Kitty cockpit" (KB-BRAIN-04) | `BuilderSurface.tsx` (1207 lines), polling `/runtime/manifest` every 5–15s | Rewrite framed as greenfield |

The existing `SSEBroadcaster` is a **bare broadcast bus**: keyed by session,
one queue per client, no cursor, no replay buffer, no per-packet filtering,
and `broadcast()` fans out to every connected client. It cannot satisfy
KB-BRAIN-03's reconnect/backpressure criteria as written. That is an
argument for *extending* it, not for building beside it — the packet's
`allowed_paths` have been corrected to include `gateway/sse.py` so the
worker can do that. Same for `builder_status.py` in KB-BRAIN-02.

### The shell adapter's earned behaviour is unspecified

"Retain the current shell adapter as a fallback" understates what
`scripts/kittybuilder_opencode_worker.sh` encodes. Its semantics are load-
bearing and were paid for in CP-08 dogfood failures:

- a free-model ladder with fallback **only on clean failure** — no result
  written *and* HEAD plus worktree unchanged (fingerprint comparison), so a
  second model never builds on the first one's debris
- refusing a result written by a model that exited non-zero
- committing on the worker's behalf, because models forget and publish then
  fails on a dirty worktree
- stamping `[<packet_id>]` into the commit subject, because
  `builder_identity.verify_and_escalate` rejects marker-less commits
  identically to foreign ones

A `WorkerSession` contract that does not reproduce these will regress
reliability while appearing more sophisticated. KB-BRAIN-01 should treat
this list as acceptance criteria, not background.

### Concurrency risk the manifests do not address

Branch leases in `gateway/builder_queue_branch_leases.py` are keyed with
`initiative_id` scoping, and the conflict query filters on
`initiative_id` in both clauses — so two initiatives can hold concurrent
leases by design. `warn_manifest` detects `allowed_paths` collisions only
*within* one manifest.

`kittybuilder-brain-v1` and `process-hardening-v1` are meant to run
independently (see the launch README) and both claim
`gateway/builder_loop.py` — KB-BRAIN-01/05 against PH-02/06. Nothing in the
tooling will notice. Under the ADR 0018 carve-out those campaign branches
auto-merge on green, so the second merge either conflicts or lands on a file
whose tests went green against the *previous* version.

Run these two initiatives sequentially, or split `builder_loop.py` out of
one of them, until cross-initiative path collision is detected in tooling.

## Completion addendum — 2026-07-28

All required repositories inspected and verified. The original initiative specified
12 sources; this document now covers every one at an immutable commit SHA with
license verification. Three previously underspecified secondary sources (oh-my-openagent,
oh-my-claudecode, opencode-swarm) have been elevated from a shared STUDY section to
dedicated file-level inspections.

### Verified repository table

| Repository | Inspected SHA | License | Verdict | Key contribution |
| --- | --- | --- | --- | --- |
| `anomalyco/opencode` (a.k.a. `sst/opencode`) | `7534d23` | MIT | ADOPT API; ADAPT events | Server API, session events, worker integration surface |
| `alvinunreal/oh-my-opencode-slim` | `a6541cb` | MIT | ADAPT lifecycle ideas | Event routing, idle reconciliation, pending-call tracking, board injection |
| `can1357/oh-my-pi` | `6671115` | MIT | ADAPT selectively | In-process SDK, structured session lifecycle, explicit abort |
| `forketyfork/architect` | `772fd0a` | MIT | STUDY | Grid rendering, attention states, one-focus-worker interaction |
| `Kuberwastaken/claurst` | pinned inspection only | GPL-3.0 | STUDY only; no code copy | Manager/executor semantics, chat-forking behavior |
| `code-yeongyu/oh-my-openagent` | `b5d5624` | MIT (at SHA; dev branch has additional terms) | STUDY agent architecture; ADAPT lifecycle patterns | Background-task concurrency, category delegation, plugin-scoped state |
| `Yeachan-Heo/oh-my-claudecode` | `d0fdaa7` | MIT | STUDY state persistence | Cross-compaction state, project-memory.json, autopilot checkpoints |
| `ZaxbyHub/opencode-swarm` | `4802189` | MIT | STUDY plan-ledger and serial execution | Plan-ledger.jsonl, phased planning, per-agent models |
| `manaflow-ai/cmux` (formerly `coder/cmux`) | `main` (active) | GPL-3.0-or-later | REJECT for code; STUDY UX | Sidebar info density, attention rings, keyboard navigation, session restore UX |
| `DeepSeek-AI/DeepSeek-Coder` | n/a (model repo) | MIT | REJECT as orchestrator | Model option, not orchestration |
| `deepseek-ai/awesome-deepseek-agent` | n/a (index) | n/a | STUDY index only | Surfaces Reasonix, DeepSeek-TUI as DeepSeek-native harnesses — model integration, not architecture |

### Ranked implementation map for KB-BRAIN-01 through KB-BRAIN-07

The original decision section prescribes an implementation order of 1–7. The harvest
addendum and secondary-source inspections confirm that order with one amendment:

| Packet | Task | Priority | Dependencies | Concrete harvest input |
| --- | --- | --- | --- | --- |
| KB-BRAIN-01 | Worker session adapter (OpenCode server + shell fallback) | 1 | None | OpenCode server API paths; shell-adapter earned semantics (free-model ladder, dirty-worktree refusal, marker commits); oh-my-pi SDK contract as comparison |
| KB-BRAIN-02 | Canonical runtime snapshot | 2 | KB-BRAIN-01 | Extend `builder_status.py::build_status_snapshot()`; oh-my-claudecode's compaction-resistant state categories as evidence fields |
| KB-BRAIN-03 | Live event stream (replayable, backpressure-aware) | 3 | KB-BRAIN-01 | Extend `gateway/sse.py` `SSEBroadcaster` with cursor and replay buffer; oh-my-opencode-slim event-router taxonomy; confirm OpenCode transport (SSE vs WebSocket) before freezing envelope |
| KB-BRAIN-04 | Multi-pane worker cockpit | 4 | KB-BRAIN-02, KB-BRAIN-03 | Extend `BuilderSurface.tsx`; cmux attention-ring UX, keyboard navigation (1–8 jump), sidebar info density; architect grid layout |
| KB-BRAIN-05 | Operator controls (canonical Builder APIs) | 5 | KB-BRAIN-04 | Expose existing Builder CLI commands through gateway routes; cmux sidebar metadata (git branch, PR status, ports) as UI inputs |
| KB-BRAIN-06 | Recommend-only decision engine | 6 | KB-BRAIN-02, KB-BRAIN-05 | opencode-swarm plan-ledger pattern for durable next-action list; oh-my-opencode-slim continuation-evaluator; oh-my-openagent category-based model routing |
| KB-BRAIN-07 | Bounded autopilot | 7 | KB-BRAIN-06 | oh-my-claudecode autopilot checkpoint as serialized state; opencode-swarm plan-ledger for crash-safe persistence; constrained to allowlisted execution modes only |

**Amendment from original plan**: KB-BRAIN-05 (operator controls) should ship before
KB-BRAIN-06 (decision engine), not after. Operator controls are a safety prerequisite —
no automated decision should execute without human-override controls already in place.
The original ordering had controls (5) after the cockpit (4) but before the engine (6),
which is correct; the table above preserves that ordering.

### What KB-BRAIN-01 should verify, not re-discover

1. OpenCode event transport: SSE or WebSocket? The `websocket-tracker.ts` file in
   `server/routes/instance/httpapi/` means the answer is not SSE by default.
2. Can the OpenCode server API be driven from Python HTTP without a TypeScript SDK?
3. Does the shell adapter's free-model-ladder logic work when models report success
   but write no changes?
4. Does `builder_identity.verify_and_escalate` reject marker-less commits correctly
   in the OpenCode adapter path?

### Resources referenced in this harvest

- `docs/reference/hatchet-patterns.md` — prior research on distributed task patterns
- `docs/reference/aider-repomap-study.md` — prior repository-map study
- `docs/ARCHITECTURE.md` — Kitty domain language and module boundaries
- `docs/FREE_WORKERS.md` — worker execution model and compute governor
- `docs/KITTYBUILDER_QUICKSTART.md` — Builder operational surface
- `docs/LEARNINGS.md` — prior engineering lessons (L-CAND-6 etc.)