# Feature-Adjacent Architecture Harvest — Kitty vs. Personal-AI, Memory, Agent-UI, Evaluation, Integration, and Ambient-Context Repositories

**Date:** 2026-07-20  
**Status:** Research-only audit — no Kitty runtime modified  
**Scope:** Kitty's personal-assistant product loop, memory/evidence model, KittyBuilder execution surface, model/harness control, runtime-to-UI contract, evaluation loop, provider integrations, and possible ambient context capture.

This audit complements rather than replaces:

- `docs/AUDIT_EXTERNAL_ARCHITECTURE_2026-07-14.md`
- `docs/AUDIT_FULL_ENGINEERING_2026-07-20.md`
- `docs/AUDIT_DEEPTUTOR_ARCHITECTURE_HARVEST_2026-07-20.md`
- `docs/AUDIT_IMAGELAB_ARCHITECTURE_HARVEST_2026-07-20.md`

It intentionally does **not** propose another agent framework, another task queue, another memory database, another chat application, or another general platform.

---

## 0. Repository identifiers and method

### Kitty starting state

| Item | Value |
|---|---|
| Kitty repository | `jacob202/kitty` |
| Inspected `origin/main` | `83f19fab64434d2bc97d5ecb15a362e4486d21ba` |
| Audit branch | `docs/audit-feature-adjacent-2026-07-20` |
| Runtime changes | None |
| New dependencies | None |

### External repositories pinned for this audit

| Repository | Inspected SHA | Repository-declared license | Audit disposition |
|---|---|---|---|
| `khoj-ai/pipali` | `a640d4492178728160e0a291bd178a09ce45b781` | Apache-2.0 | **Adapt** product-loop, skill, sandbox, and trajectory patterns |
| `khoj-ai/khoj` | `1e30154d1070c7b132f389638c008b490be1481b` | AGPL-3.0 | **Study/reimplement only**; do not copy server code into Kitty |
| `open-webui/open-webui` | `ecd48e2f718220a6400ecf49eafd4867a38feb10` | Custom Open WebUI license with branding restrictions | **Study/reimplement only** |
| `letta-ai/letta-code` | `cd60d627d8b3ef073434f2def3b8a485729ca8cb` | Apache-2.0 | **Adapt** memory-mutation semantics, not self-modifying runtime |
| `getzep/graphiti` | `77a3752a803fea94473ec1cecfaff7f13d45ba0e` | Apache-2.0 | **Adapt** temporal/provenance model, not graph infrastructure |
| `OpenHands/agent-canvas` | `7cf87336986dffe2144b39bf9aa9438f6f5dea9c` | MIT | **Adapt** frontend/backend and runtime-environment boundaries |
| `openinterpreter/openinterpreter` | `a4da0fc3cecef98f95264a9c66896ddb064dc377` | Apache-2.0 | **Adapt** harness and execution-policy contracts |
| `ag-ui-protocol/ag-ui` | `3a7433ef055aab96ee7c9ece97417d721b21dc76` | MIT | **Study/adapt partially**; do not adopt wholesale yet |
| `assistant-ui/assistant-ui` | `05770ec5dbb09d232d6fcfaf24ce2980315ed5af` | MIT | **Study/adapt** interaction and renderer patterns |
| `langfuse/langfuse` | `7e0b0bc11037c93eb810b631223f93bd87601cd2` | MIT core with separate enterprise areas | **Adapt** trace/evaluation data semantics only |
| `home-assistant/core` | `f7cdef1207c6a0afa1ea61b5adfc50153a7a1810` | Apache-2.0 | **Adapt** manifest, lifecycle, health, and diagnostics patterns |
| `screenpipe/screenpipe` | `cbdeede95dc998639340beff49079874493fc0b9` | Screenpipe Commercial License | **Study only**; no source reuse or product integration |

### Method

For each repository, this audit inspected implementation files at a pinned commit, not only marketing claims or README feature lists. Findings are classified as:

- **Adopt:** a small mechanism fits Kitty directly.
- **Adapt:** preserve the mechanism's invariant while implementing it in Kitty's existing architecture.
- **Study:** useful product or operational reference, but not implementation material.
- **Reject:** conflicts with Kitty's authority model, local-first constraints, scale, licensing posture, or simplicity doctrine.

No external source code was copied into Kitty.

---

## 1. Executive verdict

**Kitty does not need another personal-AI platform. It needs a small set of stronger contracts across systems it already owns.**

The adjacent repositories converge on seven useful ideas:

1. **One durable work lifecycle, many views.** A request should become a durable run, produce evidence and artifacts, surface attention when blocked, and remain linked to the originating conversation. Kitty must project this from existing Chat, Mission, Builder, automation, and artifact truth — not create a second task authority.
2. **Safety has two independent dimensions.** Technical sandbox boundaries and human approval policy must be represented separately. KittyBuilder currently needs this before more autonomous execution.
3. **Memory is a versioned claim with evidence, not a mutable blob.** Replacements should supersede prior facts, preserve when each claim was valid, retain source evidence, and remain undoable.
4. **Model choice and harness choice are different.** Provider/model transport, prompt/tool shaping, and execution permissions should be separate profiles with an explicit compatibility matrix.
5. **Runtime events are durable receipts.** Streaming is a transport. The source of truth should be a replayable, versioned event sequence covering runs, tools, approvals, artifacts, errors, and completion.
6. **Evaluation must attach to real traces.** KittyBench should compare exact model + harness + strategy combinations against versioned cases with cost, latency, success, evidence, and human or automated scores.
7. **Ambient capture is a separate privacy product.** Screen/audio capture must remain deferred until Kitty has a dedicated ADR, consent UX, retention controls, deletion/export, encryption, exclusions, and a threat model.

### Decisive recommendation

The next architecture packet from this audit should **not** be a new user-facing feature. It should be:

> **FAR-01 — Builder execution containment: explicit sandbox mode + approval policy, enforced fail-closed and recorded in every attempt receipt.**

This is independently supported by Pipali, Open Interpreter, Agent Canvas, and Kitty's own full-engineering audit. It removes a real safety ceiling that otherwise makes every future autonomous feature harder to trust.

After FAR-01, implement a small Kitty-native runtime event envelope. That event contract unlocks honest progress UI, approvals, cancellation, automation run history, artifacts, and later mobile clients without replacing Kitty's current gateway or Builder state machine.

---

## 2. Kitty baseline and non-negotiable boundaries

The following are already canonical in Kitty and must not be displaced by an adjacent repository:

- Kitty is the principal assistant and product surface.
- The gateway is the product; clients remain thin projections.
- KittyBuilder owns durable initiative, packet, task, attempt, lease, run, review, recovery, budget, and publication truth.
- Builder is an execution plane, not a second planner or product authority.
- New context reads through existing memory infrastructure; application writes follow existing storage authority.
- No new queue, graph database, vector database, scheduler, cloud control plane, or permanent project-management runtime without an ADR.
- Fail-loud behavior is preferred over plausible-but-false success.
- Local-first and user control outrank feature count.

Repository-wide searches at the inspected Kitty SHA did not find canonical contracts named or shaped like:

- a versioned run/tool/approval/artifact event envelope;
- `sandbox_mode` plus `approval_policy` as separate execution fields;
- temporal memory validity and evidence relations (`valid_at`, `invalid_at`, `reference_time`, `superseded_by`);
- a model-independent `harness_profile` compatibility layer;
- a durable schedule → run-history → conversation → artifact contract;
- a manifest-driven provider lifecycle with redacted diagnostics;
- trace-linked benchmark/evaluation records equivalent to dataset runs.

That does not mean Kitty lacks all related behavior. It means the behavior is not yet governed by one explicit cross-surface contract.

---

# Lane A — Personal assistant product loop

## 3. Pipali audit

### Inspected mechanisms

Pipali's implementation is a local React frontend connected over WebSocket to a Bun/Hono server with an embedded PGlite database. Its agent system uses a **director-actor** pattern:

- the director loops over model call → tool calls → actor execution → observations → next model call;
- actors isolate built-in tools, MCP tools, and confirmation-gated operations;
- actors may execute in parallel;
- a research runner owns conversation persistence around the loop.

Relevant evidence:

- `CONTRIBUTING.md` — project structure and architecture
- `src/server/processor/director/`
- `src/server/processor/actor/`
- `src/server/processor/research-runner.ts`

Pipali's skills are folders with `SKILL.md`, optional scripts, and references. Only the name and description are initially presented; full instructions are loaded when relevant. This is genuine **progressive disclosure**, not simply injecting every skill into every prompt.

Pipali also separates:

- **sandbox mode:** OS-enforced path and network restrictions;
- **direct mode:** broader host access requiring explicit approval.

Its documented defaults are read broadly except explicitly denied paths, write only to allowed paths, and network denied except allowlisted domains. macOS uses Seatbelt and Linux uses Bubblewrap. Conversation trajectories are stored in structured ATIF-shaped records rather than only rendered chat text.

### What Kitty should adopt or adapt

**Adapt now:**

1. Separate execution boundary from approval decision. A safe sandboxed command should not require the same interaction as a host-level escalation.
2. Keep allowed paths and allowed network destinations in the durable execution contract, not only in prompt prose.
3. Continue Kitty's skill registry direction but enforce progressive disclosure: summary first, full body only when selected.
4. Store structured run steps — model request, tool call, observation, result — as durable receipts, while keeping private reasoning private.
5. Surface a durable `needs_attention` condition when a run is blocked on approval, missing input, failed connection, or ambiguous authority.

**Study only:**

- the async task inbox and feedback loop;
- the polished-deliverable presentation model;
- teaching repeatable workflows as skills.

**Reject:**

- replacing Kitty's Python/FastAPI gateway with Bun/Hono;
- introducing PGlite beside Kitty's existing SQLite authority;
- adopting Pipali's remote model platform, billing, or authentication control plane;
- importing a second director/actor orchestration loop beside Kitty's existing gateway and Builder.

### Kitty-specific conclusion

Pipali is the closest product reference, but its most valuable contribution is not its stack. It is the idea that **background work remains visible, interruptible, reviewable, and attached to a deliverable**. Kitty should express that using existing Mission, Builder, automation, artifact, and chat records.

---

## 4. Khoj audit

### Inspected mechanisms

Khoj's automation path stores both the user's scheduling request and a normalized query to execute. It:

- validates the schedule;
- normalizes the executable query;
- creates a dedicated conversation for the automation;
- stores the conversation identifier with automation metadata;
- schedules in the user's local time zone;
- supports manual “run now,” edit, and delete;
- delivers results through a user-facing channel.

Relevant evidence:

- `documentation/docs/features/automations.md`
- `src/khoj/routers/api_automation.py`
- `post_automation`, `trigger_manual_job`, and `edit_job`

### What Kitty should adopt or adapt

**Adapt:**

1. Persist both:
   - the human scheduling request; and
   - the normalized executable instruction.
2. Bind every recurring automation to a durable conversation or result thread.
3. Record local time zone explicitly and show the next run in local time.
4. Provide `run_now`, pause/resume, edit, and delete without losing prior run history.
5. Link each completed automation run to artifacts and the exact chat/result it produced.

**Reject:**

- using an untracked background thread as the durable execution primitive;
- importing AGPL server code into Kitty;
- creating a separate scheduler state store when Kitty already has durable execution patterns that can be reused.

### Kitty-specific conclusion

The important pattern is **schedule → durable run → result conversation → artifact**, not “cron calls a prompt.” This is the minimum structure required for proactive Kitty behavior to remain trustworthy.

---

## 5. Open WebUI audit

### Inspected mechanisms

Open WebUI provides broad product coverage, but two implementation areas are particularly useful.

#### Memory operations

`backend/open_webui/models/memories.py` stores per-user memories with:

- stable ID;
- type;
- optional path;
- content;
- metadata;
- created/updated timestamps.

Its batch operation applies `add`, `replace`, `move`, and `remove` changes in one database transaction, with duplicate-add detection.

The same file also contains a pattern Kitty should **not** copy: several CRUD methods catch broad exceptions and return `None` or `False`. That conflicts with Kitty's fail-loud doctrine because storage failure can look like absence or a normal negative result.

#### Automations

`backend/open_webui/routers/automations.py` includes:

- feature and permission gates;
- maximum automation count;
- minimum recurrence interval;
- RRULE validation;
- user-time-zone-aware next-run calculation;
- durable latest-run and run-history records;
- create/update/enable/disable/run/delete events;
- explicit manual execution.

### What Kitty should adopt or adapt

**Adapt:**

1. Treat a group of memory edits as one atomic, reviewable change set.
2. Give automations durable run records, not only a mutable “last run” field.
3. Emit automation lifecycle events consistently.
4. Enforce frequency and count limits before scheduling.
5. Use RRULE or an equivalent normalized schedule format instead of preserving only free-form text.

**Reject:**

- broad exception swallowing;
- Open WebUI's platform breadth, enterprise authorization structure, and duplicate storage/RAG stack;
- adopting its custom-licensed UI or source as Kitty's base.

### Product-loop synthesis

Kitty should expose one **read-only unified work projection** over existing authoritative records:

- **Needs you:** approvals, missing input, failed connections, authority questions.
- **Working:** active Builder packets, automation runs, long tool operations, image/tutor jobs.
- **Done:** completed runs with result, evidence, cost, and artifacts.

This projection must not own scheduling or execution truth. It is a view over existing systems, with deep links back to the originating conversation, Mission, packet, automation, or artifact.

---

# Lane B — Memory, evidence, and truth over time

## 6. Letta Code audit

### Inspected mechanisms

Letta Code distinguishes default `persona` and `human` memory blocks and supports read-only memory classes. Its `memory_apply_patch` implementation requires:

- a non-empty reason;
- a bounded patch;
- a resolvable agent identity;
- a clean memory repository before writing;
- path-safe operations;
- rejection of modifications to read-only memory;
- a committed change with author and reason;
- a failure when a patch produces no effective change.

Relevant evidence:

- `src/agent/memory.ts`
- `src/tools/impl/memory-apply-patch.ts`
- `assertMemoryRepoCleanForWrite`
- `commitMemoryWrite`

### What Kitty should adopt or adapt

The valuable invariant is not “let the agent rewrite itself.” It is:

> Every memory mutation is attributable, reasoned, bounded, reviewable, and reversible.

**Adapt into Kitty's existing storage:**

- `change_id`
- actor (`user`, `assistant`, `tool`, `import`, `system`)
- reason
- operation (`add`, `supersede`, `correct`, `forget`, `restore`, `merge`)
- target fact(s)
- before/after representation
- source evidence
- timestamp
- `undo_of` / `supersedes`
- policy decision or approval receipt when required

**Protect as read-only or explicitly authorized:**

- constitutional/system behavior;
- identity/role boundaries;
- user-authored durable preferences marked as locked;
- safety policy;
- source records and evidence hashes.

**Reject:**

- creating a separate Git repository for personal memory;
- unrestricted self-editing of persona, prompts, skills, or policy;
- autonomous “dreaming” that silently changes durable user facts.

---

## 7. Graphiti audit

### Inspected mechanisms

Graphiti's `EntityEdge` records a fact together with:

- episode/source identifiers;
- `valid_at` — when the fact became true;
- `invalid_at` — when it stopped being true;
- `expired_at` — when the system invalidated it;
- `reference_time` — the source episode's time;
- arbitrary typed attributes;
- a fact embedding.

`EpisodicEdge` links raw episodes to derived entities. This provides provenance from a derived claim back to the source material.

Relevant evidence:

- `graphiti_core/edges.py`
- `EntityEdge`
- `EpisodicEdge`

### What Kitty should adopt or adapt

**Adapt the temporal claim model into existing SQLite storage:**

A minimal conceptual fact record should support:

- `fact_id`
- subject/entity key
- predicate/key
- structured value
- `valid_from`
- `valid_to`
- `observed_at` / source reference time
- confidence or verification state
- source evidence IDs
- `superseded_by`
- status (`active`, `superseded`, `forgotten`, `disputed`)

When a fact changes, Kitty should normally **supersede** the old claim rather than overwrite or delete it. “What is true now?” and “What did Kitty believe last month?” become different valid queries.

Contradictions should produce an explicit state:

- active claim selected;
- conflicting evidence retained;
- uncertainty visible;
- user correction able to resolve or lock the claim.

**Reject:**

- adding Neo4j, FalkorDB, Neptune, or another graph service now;
- moving all memory retrieval to graph traversal;
- requiring an LLM extraction pass for every stored interaction;
- creating a parallel memory authority beside Kitty's existing memory graph/storage router.

### Memory synthesis

Open WebUI contributes atomic multi-operation edits. Letta contributes attribution, reason, protected classes, and no-op failure. Graphiti contributes temporal validity and source lineage.

The Kitty-shaped result is:

> **A memory change set applied transactionally to versioned facts, with source evidence and first-class undo.**

This should extend the existing forget/undo work, not replace it.

---

# Lane C — KittyBuilder, execution environments, and cheap-model harnesses

## 8. OpenHands Agent Canvas audit

### Inspected mechanisms

Agent Canvas clearly states what its frontend owns and does not own.

The frontend owns:

- rendering conversation, terminal, browser, files, settings, and automation UI;
- UI state for conversations, backend selection, and profiles;
- translation of user actions into Agent Server API calls.

It does **not** own:

- execution;
- sandboxing;
- credentials outside the backend;
- scheduled execution without an automation backend.

It can connect to multiple Agent Server instances and switch among local, remote, or hosted environments. Runtime-service information is passed explicitly so agents do not guess service URLs. Development modes visibly distinguish safer Docker execution from dangerous host execution.

Relevant evidence:

- `docs/architecture.md`
- `src/api/`
- runtime modes in `package.json`/launch scripts

### What Kitty should adopt or adapt

**Adapt:**

1. Keep Builder UI a projection over Builder APIs; never execute commands from the frontend.
2. Represent execution environment explicitly (`local_host`, `local_sandbox`, `remote_worker`, future `cloud_sandbox`).
3. Display a persistent risk badge when a worker has host filesystem or network access.
4. Pass resolved runtime service information; never have the worker infer ports/endpoints from prose.
5. Keep backend registry/state separate from conversation UI state.
6. Support mock runtime adapters for deterministic UI testing.

**Reject:**

- replacing KittyBuilder with Agent Server;
- introducing ACP as a requirement before Kitty has a stable internal contract;
- copying Agent Canvas's full terminal/browser/files workspace into Kitty's primary personal-assistant UI.

---

## 9. Open Interpreter audit

### Inspected mechanisms

Open Interpreter's harness mode changes:

- model-facing system prompt;
- tool schemas;
- message conversion;
- response handling;

while keeping one native runtime. It maintains strict compatibility between provider transport (`responses`, `chat`, `messages`) and harness shape. It may infer a default harness from the selected model/provider, while an explicit override wins.

Relevant evidence:

- `docs/harness.md`
- `codex-rs/core/src/harness/`
- `codex-rs/core/src/harness/routing.rs`

Its safety documentation separates:

- **sandbox mode:** `read-only`, `workspace-write`, `danger-full-access`;
- **approval policy:** `untrusted`, `on-request`, `never`.

It documents macOS Seatbelt and Linux Bubblewrap/seccomp enforcement and states that inability to enforce a requested policy should fail closed.

Relevant evidence:

- `docs/sandbox.md`

### What Kitty should adopt or adapt

Kitty should separate three concepts that are too easy to collapse into “the model”:

#### Model profile

- provider
- model ID
- wire/API family
- context and modality capabilities
- supported reasoning controls
- estimated pricing
- privacy/locality characteristics

#### Harness profile

- system/developer prompt family
- tool naming and schemas
- message conversion
- response parser
- planning/todo behavior
- context compaction strategy
- provider-specific cache hints

#### Execution policy

- sandbox mode
- approval policy
- allowed paths
- allowed domains/network mode
- secrets exposure
- runtime and spend budget
- escalation rules

A compatibility matrix should reject invalid model/harness pairs before spending tokens. Explicit user/operator choice should override inferred defaults. Every result receipt should include all three profile versions.

This directly supports Kitty's North Star requirement to achieve most of the strongest-model quality at materially lower cost: inexpensive models may improve substantially under the right harness, but that claim must be measured, not assumed.

**Reject:**

- forking Codex/Open Interpreter;
- importing a Rust runtime solely to gain harness profiles;
- maintaining copied vendor prompts without version and license provenance;
- silently changing a harness mid-run.

---

## 10. Execution-containment conclusion

Kitty's full engineering audit already identifies host-level command execution as a severe risk. Pipali and Open Interpreter independently demonstrate the correct conceptual split, while Agent Canvas shows the UI boundary.

The next execution contract should include at least:

```text
ExecutionPolicy
  sandbox_mode: read_only | workspace_write | danger_full_access
  approval_policy: untrusted | on_request | never
  readable_roots[]
  writable_roots[]
  network_mode: off | allowlist | unrestricted
  allowed_domains[]
  secret_profile
  environment_id
  policy_version
```

Required invariants:

- default Builder repo work: `workspace_write` + `on_request`;
- network off or allowlisted unless the packet explicitly needs it;
- dangerous full access requires explicit operator authorization and a visible receipt;
- a requested sandbox that cannot be enforced fails closed;
- every escalation is attached to the attempt and preserved in evidence;
- validation commands and worker commands use the same or stricter containment;
- UI labels host access honestly.

---

# Lane D — Runtime-to-UI event contract

## 11. AG-UI audit

### Inspected mechanisms

AG-UI defines typed events for:

- message start/content/end/chunks;
- tool call start/arguments/end/result;
- state snapshots and JSON Patch deltas;
- activity snapshots/deltas;
- run started/finished/error;
- step started/finished;
- interrupt outcomes;
- reasoning lifecycle events.

`RUN_STARTED` carries thread and run identifiers. `RUN_FINISHED` supports a success or interrupt outcome. Events are transport-neutral.

Relevant evidence:

- `sdks/typescript/packages/core/src/events.ts`
- `EventType`
- `RunStartedEventSchema`
- `RunFinishedEventSchema`
- `StateSnapshotEventSchema`

### What Kitty should adopt or adapt

Do **not** adopt AG-UI wholesale yet. Kitty needs a much smaller stable envelope first:

```text
RuntimeEvent
  schema_version
  event_id
  thread_id
  run_id
  parent_run_id?
  sequence
  occurred_at
  type
  payload
  replayable
  producer
```

Initial event types:

- `run.started`
- `run.progress`
- `message.delta`
- `message.completed`
- `tool.started`
- `tool.progress`
- `tool.completed`
- `tool.failed`
- `approval.required`
- `approval.resolved`
- `artifact.created`
- `run.interrupted`
- `run.failed`
- `run.completed`

Rules:

1. Sequence numbers are monotonic within a run.
2. Durable events are committed before or atomically with the state transition they announce.
3. SSE/WebSocket is only delivery; reconnect replays from a cursor.
4. Unknown event types render through a safe fallback.
5. Private chain-of-thought is never required. “Reasoning” in the UI should be a safe status/summary or provider-supplied opaque artifact, not hidden model reasoning.
6. Legacy endpoints may be adapted into events incrementally; no flag-day rewrite.

---

## 12. assistant-ui audit

### Inspected mechanisms

assistant-ui composes a thread from primitives rather than one monolithic chat widget. Its thread supports:

- message list, composer, attachments, auto-scroll, and conditional states;
- send versus cancel based on whether a run is active;
- registered per-tool renderers;
- a generic fallback for unknown tools;
- grouping consecutive tool and reasoning parts;
- component overrides without replacing the runtime.

Relevant evidence:

- `apps/docs/content/docs/ui/thread.mdx`
- `ThreadPrimitive`
- `ToolFallback`
- `ToolGroup`
- `ReasoningGroup`

### What Kitty should adopt or adapt

**Adapt into kitty-chat, without replacing it:**

1. A typed renderer registry keyed by runtime event/tool type.
2. A safe generic fallback that always shows status, tool name, timing, and error.
3. Group contiguous low-level tool events behind a readable summary.
4. First-class approval and artifact cards rather than plain assistant text.
5. Correct send/cancel behavior and reconnect state.
6. Accessibility and scroll behavior as browser-test acceptance criteria.

**Reject:**

- replacing Kitty's visual identity with an assistant-ui starter;
- coupling frontend components directly to any external agent framework;
- displaying raw reasoning text by default.

### Event/UI synthesis

AG-UI provides a useful vocabulary; assistant-ui demonstrates how a UI consumes structured runtime parts. Kitty should own a smaller internal event contract and render it through Kitty-specific components.

---

# Lane E — Evaluation, receipts, and improvement

## 13. Langfuse audit

### Inspected mechanisms

Langfuse separates:

- traces/observations;
- prompt versions;
- model pricing records;
- evaluator templates and versions;
- evaluator job configuration and execution status;
- datasets and versioned dataset items;
- experiment/dataset runs;
- run items linked to exact traces and observations;
- numeric, boolean, categorical, and text scores;
- human annotation queues.

Particularly useful source structures include:

- `packages/shared/prisma/schema.prisma`
  - `Model`
  - `EvalTemplate`
  - `JobConfiguration`
  - `JobExecution`
  - `ScoreConfig`
  - `Dataset`
  - `DatasetItem`
  - `DatasetRuns`
  - `DatasetRunItems`
- `worker/src/features/evaluation/evalService.ts`
- `worker/src/features/experiments/`

Dataset items themselves have validity windows. Dataset-run items bind an exact case to a trace and optional observation, making results reproducible and comparable.

### What Kitty should adopt or adapt

Kitty should keep this local and much smaller. Suggested concepts, implemented in existing SQLite rather than a new platform:

```text
DeliberationRun
  run_id, task_class, mode, started_at, ended_at
  model_profile_version, harness_profile_version, strategy_version
  input_receipt_hash, output_receipt_hash
  token_usage, cost_estimate, latency_ms, outcome

RunSpan
  span_id, run_id, parent_span_id, kind
  tool/model/provider, start/end, status, error, metadata

BenchmarkCase
  case_id, suite_version, input, criteria, expected_or_reference, metadata

ExperimentRun
  experiment_id, case_id, deliberation_run_id

Evaluation
  evaluation_id, run_id, evaluator_version
  score_name, score_type, value, rationale_or_evidence, created_at
```

Required behaviors:

1. Every benchmark result links to the exact live trace or replayable run receipt.
2. Prompt, strategy, routing, and harness versions are captured.
3. Cost and latency are recorded beside quality.
4. Human feedback and deterministic checks remain distinguishable from model-as-judge scores.
5. Failed and interrupted runs remain in the dataset; they are not silently omitted.
6. A bad production result can be promoted into a regression case.

This is the missing bridge between KittyBench and the intended adaptive reasoning controller.

**Reject:**

- deploying Langfuse's full Postgres/ClickHouse/queue stack for a single-user local assistant;
- adding a large evaluation dashboard before the trace schema exists;
- optimizing prompts from unversioned or unrepresentative examples;
- treating model-as-judge as ground truth.

---

# Lane F — Provider and connector architecture

## 14. Home Assistant audit

### Inspected mechanisms

Home Assistant scales integrations through explicit manifests and lifecycle-managed configuration entries.

A representative manifest declares:

- stable domain/name;
- required and optional dependencies;
- config-flow support;
- documentation;
- integration type;
- connection class;
- pinned external requirements;
- code owners.

Relevant evidence:

- `homeassistant/components/google_generative_ai_conversation/manifest.json`

Config entries have explicit states including:

- loaded;
- setup error;
- migration error;
- setup retry;
- not loaded;
- failed unload;
- setup/unload in progress.

Some states are marked recoverable, allowing reload/retry while preserving truthful status.

Relevant evidence:

- `homeassistant/config_entries.py`
- `ConfigEntryState`
- `ConfigEntry`

Diagnostics utilities recursively redact configured keys and omit internal bookkeeping before exposing diagnostic payloads.

Relevant evidence:

- `homeassistant/components/diagnostics/util.py`
- `async_redact_data`

### What Kitty should adopt or adapt

A small Kitty integration/provider manifest should describe, without importing code at discovery time:

```text
IntegrationManifest
  id
  display_name
  category
  manifest_version
  implementation_version
  integration_type
  transport
  capabilities[]
  required_dependencies[]
  optional_dependencies[]
  config_schema_version
  setup_entrypoint
  unload_entrypoint
  health_checks[]
  diagnostics_entrypoint
  documentation
  owner
  license
  risk_level
```

Suggested lifecycle states:

- `not_configured`
- `setting_up`
- `ready`
- `degraded`
- `retrying`
- `auth_required`
- `migration_error`
- `unload_failed`
- `disabled`

Required invariants:

1. Stable integration IDs survive display-name changes.
2. Setup, migration, reload, and unload are explicit operations.
3. Capabilities are declared and verified, not inferred from provider name.
4. Health distinguishes unavailable, unauthorized, misconfigured, and degraded.
5. Diagnostics redact secrets by construction.
6. Product UI consumes normalized capabilities and health, not provider-specific schema.
7. Discovery does not execute arbitrary plugin code.

Start with Kitty's existing model, image, tool/MCP, and connected-service providers. Do not build Home Assistant's entire integration ecosystem.

---

# Lane G — Ambient context and computer memory

## 15. Screenpipe audit

### Inspected mechanisms

Screenpipe captures screen, accessibility/UI events, audio, app/window changes, and optional keyboard/click/clipboard events. Its current recording configuration exposes separate controls for:

- disabling audio, vision, screenshots, timeline, keyboard, clicks, or clipboard persistence;
- included and ignored windows/URLs;
- private/incognito-window filtering;
- pausing on DRM content;
- local or remote PII-redaction modes;
- selectable PII classes and columns;
- screenshot/image PII redaction;
- recording schedules;
- event-driven capture timing and visual-change thresholds;
- localhost binding versus remote access with API authentication;
- secret encryption.

Relevant evidence:

- `crates/screenpipe-engine/src/recording_config.rs`
- repository README event-driven capture description

The current repository is governed by the **Screenpipe Commercial License**, which prohibits embedding or integrating it into a competing product without a commercial agreement. It is therefore a behavioral reference only.

### What Kitty should learn

Useful principles:

1. Prefer event-driven capture over fixed-rate screenshot recording.
2. Treat accessibility metadata as primary and OCR as fallback where possible.
3. Make each capture modality independently disableable.
4. Provide app, URL, window, meeting, and audio exclusions.
5. Bind remote API exposure to authentication and an explicit listen address.
6. Design PII handling as a pipeline with visible scope, not a magic “private” badge.
7. Expose storage and retention cost before enabling capture.

### Decision: defer implementation

Kitty should not implement or integrate ambient capture until a dedicated ADR covers:

- explicit informed opt-in;
- persistent visible recording indicator;
- global pause and kill switch;
- per-app/window/URL/audio exclusions;
- private/incognito and password-manager exclusion;
- no raw keyboard capture by default;
- local encryption and key recovery posture;
- retention cap and storage budget;
- searchable export and permanent deletion;
- redaction before any cloud call;
- model/provider privacy routing;
- threat model for intimate personal data;
- recovery behavior after crashes;
- legal and license review.

A safer first research step would be **user-selected context receipts** — explicit screenshots, files, or bounded activity windows — rather than 24/7 capture.

---

## 16. Cross-repository synthesis

### Principle 1 — One authority, many projections

- Builder remains execution truth.
- Conversations remain interaction truth.
- Artifacts remain deliverable truth.
- Memory remains personal-knowledge truth.
- A “Needs you / Working / Done” surface is a projection joining those systems, not a new queue.

### Principle 2 — Events are receipts, not decoration

A progress bar backed only by an in-memory stream is not trustworthy. A durable event sequence allows reconnect, replay, mobile clients, incident diagnosis, and exact evidence.

### Principle 3 — Sandbox and approval are orthogonal

- Sandbox answers: **What can this process technically access?**
- Approval answers: **When must the user authorize an action?**

Neither replaces the other.

### Principle 4 — Memory corrections preserve history

A correction should normally invalidate/supersede an earlier claim while retaining its evidence and validity window. Forgetting is an explicit user-directed state transition with undo, not an unexplained delete.

### Principle 5 — Harness is not model

The same model may perform materially differently under different tool schemas, prompts, context management, and response parsers. Kitty should measure model + harness + strategy as a combination.

### Principle 6 — Automations produce durable work

Each automation run should have an identity, status, conversation/result, artifacts, cost, error, and event history. A scheduler callback alone is insufficient.

### Principle 7 — Integrations declare lifecycle and risk

Provider discovery, configuration, health, migration, reload, diagnostics, and unload should be normalized. Product UI should not need to understand every provider's private schema.

### Principle 8 — Ambient context is a separate consent boundary

Always-on capture changes Kitty's threat model and product ethics. It cannot arrive as a casual connector.

---

## 17. Adopt / adapt / study / reject matrix

| Mechanism | Source | Kitty disposition | Reason |
|---|---|---|---|
| Sandbox boundary separate from approvals | Pipali, Open Interpreter | **Adopt now** | Directly closes a verified Builder safety gap |
| Allowed path/domain policy | Pipali, Open Interpreter | **Adapt now** | Fits packet scope and local-first execution |
| Structured trajectory receipt | Pipali ATIF | **Adapt** | Needed for replay/evaluation; keep Kitty schema small |
| Progressive skill disclosure | Pipali, Letta | **Adopt** | Lowers context cost and avoids prompt bloat |
| Automation linked to conversation | Khoj | **Adopt** | Preserves origin and follow-up context |
| RRULE, limits, durable automation runs | Open WebUI | **Adapt** | Trustworthy proactive behavior |
| Atomic memory change set | Open WebUI | **Adapt** | Supports review and undo |
| Reasoned, attributed memory patch | Letta | **Adapt** | Strong provenance without Git-backed memory |
| Temporal facts + source episodes | Graphiti | **Adapt** | Handles changing personal facts honestly |
| Graph database | Graphiti | **Reject now** | New heavy authority with little current benefit |
| Multiple backend environments | Agent Canvas | **Study/adapt** | Useful for later local/remote workers |
| UI executes actions | Any | **Reject** | Violates thin-client boundary |
| Model-specific harness profiles | Open Interpreter | **Adapt** | Potential quality/cost leverage |
| Strict harness/transport compatibility | Open Interpreter | **Adopt** | Prevents invalid and wasteful runs |
| Full ACP adoption | Agent Canvas/Open Interpreter | **Defer** | Internal contract should stabilize first |
| Full AG-UI protocol | AG-UI | **Defer** | Larger than Kitty's immediate needs |
| Minimal event envelope | AG-UI-inspired | **Adopt** | Unlocks honest progress and replay |
| Tool/artifact renderer registry | assistant-ui | **Adapt** | Improves UI without replacing kitty-chat |
| Trace-linked datasets and experiments | Langfuse | **Adapt** | Required for evidence-based routing |
| Langfuse deployment | Langfuse | **Reject now** | Excess infrastructure for local single-user Kitty |
| Manifest + lifecycle + redacted diagnostics | Home Assistant | **Adapt** | Normalizes providers without a plugin free-for-all |
| Ambient capture engine/source reuse | Screenpipe | **Reject** | License, privacy, and threat-model conflict |
| Bounded explicit context receipts | Screenpipe-inspired | **Study** | Safer future path than always-on capture |

---

## 18. Verified gap register

| ID | Gap | Evidence at inspected Kitty state | Impact | Severity | Best reference |
|---|---|---|---|---|---|
| FAR-G1 | Builder execution policy does not expose an enforced canonical sandbox-mode + approval-policy pair | No matching canonical contract found; `AUDIT_FULL_ENGINEERING_2026-07-20.md` identifies host command execution and shell-backed validation risk | Autonomous execution safety ceiling; prompt restrictions can be bypassed by process access | **Critical** | Pipali sandbox; Open Interpreter sandbox/approvals; Agent Canvas environment boundary |
| FAR-G2 | No versioned, replayable cross-surface runtime event envelope | No canonical run/tool/approval/artifact event schema found | Progress, reconnect, cancellation, approvals, mobile, and evidence stay surface-specific | **High** | AG-UI event vocabulary |
| FAR-G3 | Provider/model choice is not governed separately from harness shaping and execution policy | No canonical `harness_profile`/wire compatibility contract found | Cheap models cannot be tuned or compared rigorously; invalid combinations waste time/tokens | **High** | Open Interpreter harness routing |
| FAR-G4 | Memory corrections lack one canonical temporal-claim + source-evidence contract | Existing forget/undo work is valuable, but no canonical validity/supersession/evidence fields found | Changed facts may overwrite history or lose why Kitty believed them | **High** | Letta mutation receipts; Graphiti temporal edges |
| FAR-G5 | No canonical schedule → durable run history → result conversation → artifacts contract was found | No matching automation-run/RRULE contract found in repository search | Proactive behavior can become invisible, untraceable, or hard to resume | **High** | Khoj + Open WebUI automations |
| FAR-G6 | No single manifest-driven provider lifecycle and redacted diagnostics contract was found | Existing providers expose differing configuration/health surfaces | UI drift, ambiguous outages, difficult migrations, accidental secret disclosure | **Medium** | Home Assistant manifests/config entries/diagnostics |
| FAR-G7 | KittyBench/evaluation concepts are not yet linked through one live trace/dataset/experiment schema | No canonical DeliberationRun/experiment/trace-linked case records found | Adaptive routing cannot prove quality/cost improvements | **Medium** | Langfuse traces, datasets, evaluations |
| FAR-G8 | No verified unified attention projection joins chat, Builder, automations, and artifacts | Existing surfaces expose their own state, but no canonical joined projection is documented | User must hunt for what needs attention or what finished | **Medium** | Pipali task attention; Open WebUI run history |
| FAR-G9 | Ambient context has no consent/retention/threat-model architecture | Correctly absent today | Premature capture would create severe privacy and storage risk | **Future critical** | Screenpipe controls, study-only |

---

## 19. Ranked implementation packets

### FAR-01 — Builder execution containment

**Priority:** P0 security  
**Model class:** strongest planner/reviewer; implementation may be bounded but requires human sign-off  
**Dependencies:** none

Add an explicit execution-policy contract to packet/attempt dispatch and enforce it fail-closed. Preserve policy and escalation receipts in durable evidence.

### FAR-02 — Kitty runtime event envelope

**Priority:** P0 trust/platform  
**Model class:** capable routine coding + strong review  
**Dependencies:** none; should remain compatible with current endpoints

Define and persist the minimal event envelope and adapt one existing long-running path end-to-end. Do not redesign all UI in the first packet.

### FAR-03 — Durable automation runs and result linkage

**Priority:** P1 product/trust  
**Dependencies:** FAR-02 preferred

Normalize schedules; create durable run records; link each run to its conversation/result and artifacts; expose pause/resume/run-now/history.

### FAR-04 — Memory change sets and temporal provenance

**Priority:** P1 memory/trust  
**Dependencies:** build on existing forget/undo behavior

Apply memory changes transactionally, preserve actor/reason/source/before/after, and add validity/supersession semantics without a new database.

### FAR-05 — Model + harness + strategy experiment contract

**Priority:** P1 reasoning/cost  
**Dependencies:** FAR-02; KittyBench baseline cases

Version model, harness, and strategy profiles; capture run traces, cost, latency, quality, and evidence; reject incompatible pairs before execution.

### FAR-06 — Integration manifest, lifecycle, health, and diagnostics

**Priority:** P1 architecture  
**Dependencies:** none

Introduce a small manifest schema and normalized lifecycle for existing providers. Start with two or three real integrations; do not create a generic plugin marketplace.

### FAR-07 — Typed tool, approval, and artifact render registry

**Priority:** P2 UX  
**Dependencies:** FAR-02

Render structured events through Kitty-native components with grouping and safe fallback. Preserve current visual identity.

### FAR-08 — Unified attention/work projection

**Priority:** P2 product  
**Dependencies:** FAR-02 and preferably FAR-03

Add the read-only `Needs you / Working / Done` projection over authoritative records. No new task queue or lifecycle authority.

### FAR-R1 — Ambient context ADR and threat model only

**Priority:** Research lane  
**Dependencies:** none

No capture implementation. Produce a go/no-go ADR covering consent, exclusions, retention, deletion/export, encryption, cloud routing, storage budget, and licensing.

---

## 20. First packet specification — FAR-01

### Objective

Make KittyBuilder's effective execution authority explicit, enforceable, and auditable by separating sandbox mode from approval policy.

### In scope

- Define a versioned `ExecutionPolicy` contract.
- Persist the effective policy on task/attempt/run evidence.
- Derive writable roots from packet-authorized paths and worktree boundaries.
- Default network to off or an explicit allowlist.
- Add at least one enforceable local sandbox adapter suitable for the primary macOS environment, or an isolated container adapter.
- Fail closed when the requested boundary cannot be established.
- Record approval/escalation events durably.
- Apply containment to worker execution and manifest validation commands.
- Add operator-visible policy/risk status.

### Out of scope

- Replacing KittyBuilder.
- Remote multi-user worker fleet.
- New general permission framework for all Kitty tools.
- UI redesign.
- ACP adoption.
- Bypassing existing authority or protected-zone rules.

### Acceptance criteria

1. Every dispatched attempt has an immutable effective policy receipt.
2. `read_only`, `workspace_write`, and `danger_full_access` are distinguishable and testable.
3. `untrusted`, `on_request`, and `never` approval policies are distinguishable and testable.
4. Workspace-write cannot write outside authorized roots.
5. Network-off cannot make outbound network connections.
6. An unavailable requested sandbox produces a loud preflight failure; it never silently downgrades to host execution.
7. Full-access execution requires an explicit operator decision and produces a durable warning event.
8. Worker and validation paths cannot use different, weaker containment accidentally.
9. Cancellation and timeout terminate the sandboxed process tree.
10. Existing Builder lease/attempt/recovery semantics remain authoritative.
11. Tests cover path escape, symlink escape, process-tree cleanup, network denial, escalation, and unsupported-environment failure.
12. Documentation states the actual boundary and remaining limitations without claiming perfect isolation.

### Suggested commit

`feat(builder): enforce sandbox and approval execution policy`

---

## 21. Decisions recorded for Jacob

Recommended decisions from this audit:

1. **Approve FAR-01 before further autonomous execution expansion.** Yes.
2. **Use a Kitty-native minimal event envelope rather than adopting AG-UI wholesale.** Yes; preserve an adapter path later.
3. **Extend existing SQLite memory authority with temporal/provenance semantics rather than adding a graph database.** Yes.
4. **Treat Khoj, Open WebUI, and Screenpipe as study-only because of license/product-boundary concerns.** Yes.
5. **Keep ambient screen/audio capture deferred behind a dedicated ADR and threat model.** Yes.
6. **Build a unified work surface only as a read-only projection over existing authoritative records.** Yes; no second task queue.
7. **Evaluate model + harness + strategy combinations together, with trace-linked quality/cost evidence.** Yes.
8. **Do not start implementation from this audit automatically.** Land the audit, select FAR-01 explicitly, then create a clean bounded packet.

---

## 22. Final conclusion

The repository scout did not reveal a missing platform Kitty should install. It revealed a consistent set of contracts mature systems use to remain understandable:

- durable runs;
- explicit attention states;
- sandboxed execution plus approvals;
- versioned memory changes;
- temporal evidence;
- model/harness separation;
- replayable events;
- trace-linked evaluation;
- manifest-driven integrations;
- strict consent boundaries for ambient data.

Kitty already owns enough infrastructure to implement these mechanisms without importing another product's weight. The correct move is to strengthen the seams between Kitty's existing systems, beginning with execution containment, then the event contract, then durable proactive work and evidence-backed memory/reasoning.
