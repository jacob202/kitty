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

- `packages/opencode/src/session/index.ts` — session lifecycle and session-level events
- `packages/opencode/src/session/status.ts` — typed `session.status`
- `packages/opencode/src/session/message-v2.ts` and session processor files — messages, parts and tool activity
- `packages/opencode/src/bus/` — event publication/subscription
- `packages/opencode/src/server/server.ts` — headless HTTP server and authentication
- server event route (`GET /event`) — SSE-style event delivery used by clients
- generated OpenCode SDK/client packages — session create/list/read/prompt/abort APIs

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

### 6. Oh My OpenAgent / Oh My ClaudeCode / OpenCode Swarm — STUDY; harvest prompts only after runtime proof

Repositories named in the original initiative:

- `code-yeongyu/oh-my-openagent`
- `Yeachan-Heo/oh-my-claudecode`
- `zaxbysauce/opencode-swarm`

These are secondary sources. Their likely value is role decomposition, continuation policy, model routing and operator ergonomics—not durable state. No component from them should enter the critical path until a file-level inspection demonstrates behavior that OpenCode/OMP/OMO Slim do not already provide.

Acceptance rule for any later adoption:

- identify exact runtime file and tests
- show a concrete missing Kitty capability
- prove the behavior is not merely encoded in a system prompt
- preserve Kitty's queue/attempt/lease authority

### 7. DeepSeek-Coder and DeepSeek agent collections — REJECT as orchestrator source; keep as worker/model research

Repository: `DeepSeek-AI/DeepSeek-Coder`

DeepSeek-Coder is primarily a model/training/inference repository, not the operator cockpit or durable worker-session substrate Kitty needs. DeepSeek agent indexes may identify useful coding harnesses, but model quality and orchestration architecture are separate decisions.

Use DeepSeek models through existing provider adapters where they meet quality/cost requirements. Do not design KittyBuilder's state machine around model-specific repositories.

### 8. cmux and other terminal multiplexers — STUDY interaction patterns only

Terminal multiplexers are useful for immediate local visibility, but they are not Kitty's durable source of truth and do not solve remote/mobile operation. Study pane focus, attention badges, persistence and keyboard navigation. Reimplement these interactions in Kitty's web cockpit. Do not make tmux/cmux parsing the canonical event source.

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
- **Architect:** reproduce the operator experience in Kitty React.
- **Claurst/cmux:** study only.
- **DeepSeek-Coder:** model option, not orchestration substrate.

This is enough evidence to unblock KB-BRAIN-01 without asking a coding worker to perform another broad repository survey.