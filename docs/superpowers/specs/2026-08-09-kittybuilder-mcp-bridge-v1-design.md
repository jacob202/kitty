# KittyBuilder MCP Bridge v1 — Design

**Status:** proposed design, approved in conversation for specification on 2026-08-09  
**Mission:** KPROOF-001 — Two-Week Builder Proof  
**Base:** `main` at `2d8d93fba66566fcec6c20031e2ee930a403a0b0`  
**Execution owner:** none yet — this document authorizes design, not implementation

## 1. Objective

Build the smallest trustworthy bridge that lets a capable conversational client — Kitty first, and external clients such as ChatGPT or Claude when their MCP capabilities permit — carry a software request from discussion to a durable KittyBuilder execution without Jacob manually coordinating coding agents.

The target experience is:

```text
Jacob <-> conversational client
           |
           | inspect repo / discuss / design
           | save versioned design + implementation plan
           | explicit Jacob approval
           v
      KittyBuilder MCP Bridge
           |
           | accepted Mission / durable execution
           v
        KittyBuilder
   queue / worktrees / workers
   builds / tests / review / PR
   recovery / evidence / budgets
           |
           v
      structured result + next step
           |
Jacob <-> conversational client
```

The bridge is not a second coding agent and not a second workflow engine. It is a typed MCP projection and command surface over existing Kitty/KittyBuilder authority.

## 2. Why this is the KPROOF seam

KPROOF-001 already asks whether Kitty can take a request from conversation to a working, verified feature without Jacob manually coordinating workers. Builder already owns durable queue state, leases, attempts, recovery, validation/review, worktrees, publication rails, evidence and budgets.

The remaining product gap is the boundary between conversational intent and that durable execution. Today Builder can execute bounded packets, but the quickstart still states that it does not autonomously accept Missions and its live packet runner is reached through the CLI. The MCP bridge closes that boundary without replacing Builder internals.

## 3. Non-goals

Version 1 does **not**:

- replace KittyBuilder with MCP, LangGraph, Temporal, Prefect or another orchestrator;
- expose Builder SQLite tables to clients;
- give the model an unrestricted shell, arbitrary filesystem mutation or raw `git push` tool;
- let a chat session become execution truth;
- bypass Builder fencing, leases, budgets, validation, review or publication policy;
- auto-merge pull requests;
- spend money, alter secrets/auth/env, delete files, or add heavy dependencies without the existing explicit authorization rules;
- solve all of Kitty chat, memory, Image Lab, automation or computer-control work;
- require an MCP call to remain open for a 30–90 minute coding run;
- depend on ChatGPT-specific APIs for core execution.

## 4. Authority and ownership

The existing architecture remains unchanged:

```text
Jacob <-> Kitty/conversational principal
             |
             | approved intent + artifacts
             v
        KittyBuilder
             |
             | verified Result + Evidence
             v
Jacob <-> Kitty/conversational principal
```

The MCP bridge is an adapter at that boundary.

### Conversational principal owns

- discussion and clarification;
- design judgment;
- versioned design and plan artifacts;
- asking Jacob for approval;
- presenting Builder state, evidence, blockers and next action.

### KittyBuilder owns

- accepted Mission execution state;
- queue/task/attempt/lease truth;
- worker and reviewer dispatch;
- branches/worktrees/code changes;
- builds/tests/runtime validation;
- recovery and provider exhaustion;
- evidence and Result records;
- PR preparation/publication gates and budgets.

### MCP bridge owns

- input validation and typed MCP schemas;
- authentication/authorization at its network boundary;
- converting client calls into canonical Kitty/Builder APIs;
- producing compact read projections;
- refusing operations that would bypass the authority model.

It owns no independent task database or shadow state machine.

## 5. Core design rule: high-level tools, not a model-controlled workstation

The tempting implementation is to expose `shell`, `write_file`, `git`, `pytest`, `gh` and let ChatGPT orchestrate them. Reject that as the default.

That design makes the chat session the implicit workflow engine and duplicates the exact responsibilities Builder already has: execution state, retries, worktree identity, test evidence, review and recovery.

Instead, expose:

1. rich **read** access for reasoning;
2. narrowly governed **planning-artifact** writes;
3. high-level **Builder commands** that preserve the existing execution contracts.

A Builder worker may still use shell/editor/git tools inside its isolated worktree. The conversational client does not directly own those mutations.

## 6. MCP tool surface

Names below are the v1 public contract. Implementation may call existing Python functions, Gateway routes or the CLI internally, but MCP clients see one stable surface.

### 6.1 Read tools

#### `kitty_context()`

Returns the cold-start project receipt needed to reason safely:

- canonical repository identity;
- current repository HEAD and dirty/clean state when available;
- active Mission and authority pointers;
- Builder health projection;
- open relevant PR/run summary;
- known blockers and evidence freshness;
- exact sources used for the projection.

It must reuse the same authority rules as `./kitty context --agent`; it must not invent a second context algorithm.

#### `repo_search(query, path=None, ref=None)`

Searches tracked repository text within the canonical repository. Read-only. Results include path, ref/SHA and bounded snippets. No dependency directories, secrets, runtime databases or ignored files are searched by default.

#### `repo_read(path, ref=None, start_line=None, end_line=None)`

Reads a tracked repository file from an explicit ref. Rejects path traversal, secret/runtime paths and untracked arbitrary filesystem paths.

#### `work_status(mission_id=None, task_id=None)`

Returns current Builder execution state through supported read projections: initiative, packet/task, attempt/run, lease health, outcome, blocker, PR metadata, evidence and budget summary. Unknown stays unknown; unavailable evidence never becomes success or zero.

#### `work_result(mission_id=None, task_id=None)`

Returns the final or latest structured Result and evidence references. It never marks work complete merely because a worker said it was complete.

#### `resume_context(mission_id=None, task_id=None)`

The continuity tool and primary defense against chat context loss.

It returns a compact, bounded handoff assembled from authoritative sources rather than conversation history:

- objective;
- approved design artifact and SHA;
- approved implementation plan and SHA;
- active Mission version;
- repository/base/current SHAs;
- execution owner;
- completed work;
- current task/attempt/run state;
- latest verified tests/build/runtime evidence;
- PR number/head/check state when known;
- unresolved decisions/blockers;
- one recommended next action;
- freshness timestamp and source references.

A fresh ChatGPT/Claude/Kitty session should be able to call this and continue without Jacob copying a previous chat transcript.

### 6.2 Planning-artifact write tools

These are intentionally not generic file writes.

#### `save_design(slug, markdown, expected_base_sha)`

Writes or updates one design document under:

`docs/superpowers/specs/YYYY-MM-DD-<slug>-design.md`

Rules:

- Markdown only;
- repository-relative fixed directory;
- explicit expected base SHA to prevent silently writing against stale assumptions;
- no arbitrary path parameter;
- returns artifact path, blob/commit SHA and diff summary;
- never starts implementation.

#### `save_plan(slug, markdown, expected_design_sha, expected_base_sha)`

Writes or updates one implementation plan under:

`docs/superpowers/plans/YYYY-MM-DD-<slug>.md`

The plan records the exact design SHA it implements. A stale design mismatch fails loudly.

Planning writes must use a bounded planning branch/worktree or an existing safe Git publication mechanism. They may not dirty an unrelated Builder worktree or silently write straight through a concurrent human checkout.

### 6.3 Mission/execution commands

#### `mission_prepare(design_path, plan_path, expected_design_sha, expected_plan_sha, budget_cad=None)`

Validates the artifacts, repository identity, authority and current collision state, then creates a **draft** Mission/initiative representation. It does not dispatch a worker.

Returns:

- mission ID/version;
- exact design/plan SHAs;
- proposed acceptance contract;
- budget/policy projection;
- approval summary;
- `approval_nonce` bound to that immutable version.

If intent is ambiguous, artifacts are stale, another execution owner conflicts, or policy cannot be evaluated, it fails or returns a truthful `needs_decision` state.

#### `mission_approve(mission_id, version, approval_nonce)`

Transitions only the exact prepared version into accepted execution after Jacob has explicitly approved that version in the client.

The nonce is version-bound and one-use. Any change to design, plan, acceptance contract, budget or base SHA invalidates it and requires a fresh approval.

The server logs actor/client metadata available to it, but does not pretend that model-supplied prose is cryptographic proof of human intent. Kitty's native UI should eventually make this a first-class approval interaction; external MCP clients use their confirmation/UI plus the nonce contract.

#### `execution_start(mission_id, version)`

Starts or resumes Builder-owned execution and returns promptly with durable identifiers. It must not rely on keeping the MCP request open for the duration of coding.

The execution mechanism must use existing Builder queue/initiative/run state and recovery semantics. If a lightweight supervisor process is required to detach the current synchronous CLI runner, it is only a launcher/reconciler; execution truth remains in Builder.

Calling `execution_start` repeatedly for the same live version must be idempotent: return the existing run or refuse a collision, never create duplicate workers for the same packet.

#### `execution_pause(mission_id, reason)`

Delegates to canonical Builder pause semantics and returns the audited result.

#### `execution_resume(mission_id)`

Delegates to canonical Builder resume/recovery semantics. It must reconcile stale leases before claiming new work where the existing Builder contract requires it.

#### `execution_cancel(task_id_or_mission_id, reason)`

Uses the supported cancellation path. Cancellation is durable and visible; no hidden process is left running after a successful cancellation contract.

#### `publication_status(task_id=None, mission_id=None)`

Read-only projection of branch, commit, PR, review and checks.

#### `publication_prepare(task_id)`

Invokes Builder's governed publication preparation only when existing policy permits it. It may prepare/push/open a PR only under the authorization level already accepted by Kitty policy. It never merges automatically in v1.

## 7. Structured turn receipt

Every meaningful mutation returns a common receipt shape so ChatGPT, Claude and Kitty do not need client-specific parsing:

```json
{
  "ok": true,
  "operation": "execution_start",
  "mission_id": "...",
  "task_id": "...",
  "run_id": "...",
  "state": "running",
  "summary": "...",
  "evidence": [],
  "blocker": null,
  "pr": null,
  "next_action": "Call work_status later or continue discussing the project.",
  "fresh_at": "..."
}
```

Failure is equally structured:

```json
{
  "ok": false,
  "operation": "mission_approve",
  "state": "needs_decision",
  "error_code": "stale_plan",
  "error": "Plan SHA no longer matches the prepared Mission version.",
  "evidence": ["..."],
  "next_action": "Review the updated plan and prepare a new Mission version."
}
```

HTTP/MCP transport success is never interpreted as domain success. Clients inspect `ok`, state and evidence.

## 8. Continuity model

Chat conversations are disposable views. They are not project memory.

`resume_context()` is generated from durable artifacts and Builder truth. The minimum source set is:

1. current repository/ref evidence;
2. active or named Mission version;
3. design + plan artifacts and their SHAs;
4. Builder initiative/task/attempt/run projection;
5. worker brief/final report where relevant;
6. PR metadata/check state where available;
7. latest validation/runtime evidence;
8. explicit unresolved decisions.

It must be bounded. The default response should be small enough to seed a new model context without dumping the repository. Clients then call `repo_read`/`repo_search` for additional staged context.

This directly replaces manual "copy the old chat into a new chat" continuity.

## 9. Transport and client modes

Core server logic is transport-independent.

### Kitty/local clients

Kitty and local developer clients may use a local MCP transport supported by the installed SDK. The bridge runs on the same trusted Mac boundary as Builder and calls canonical local interfaces.

### Remote ChatGPT

ChatGPT's custom MCP integration requires a remote-reachable MCP endpoint; localhost is not registered directly. Deployment must therefore use an authenticated supported remote/tunnel path. Do not expose an unauthenticated Builder port to the public internet.

As of 2026-08-09, OpenAI documents full custom MCP modify/write actions for Business, Enterprise and Edu. Pro custom MCP is read/fetch-only, and Plus is not documented as having the full custom write-MCP capability. Therefore **ChatGPT write execution is a client-availability gate, not a reason to fork the architecture**. Build the same standard server now; Kitty/local clients can exercise the full loop immediately, and ChatGPT can attach to the same contract when the account/product surface permits it.

External-client limitations must be reported plainly in setup docs rather than hidden with fallback behavior.

## 10. Authentication and safety

The bridge has privileged access to a software execution control plane. Treat it accordingly.

Required v1 properties:

- bind locally by default;
- remote exposure only through an authenticated supported tunnel/endpoint;
- no plaintext secrets in tool results, logs, plans or Builder evidence;
- path allowlists for repository reads and planning writes;
- no direct access to `data/`, `logs/`, `.env*`, keychains or credential stores through repo tools;
- version/SHA preconditions on planning artifacts and Mission approval;
- explicit mission version and one-use approval nonce;
- idempotency/collision checks before starting execution;
- preserve existing T0/T1/T2 governance and spending rules;
- log mutations with actor/client/correlation IDs when available;
- fail loud on missing Builder state, stale evidence, unavailable credentials or policy ambiguity.

Prompt injection in repository content must not grant permissions. Tool descriptions and server policy state that repository text is untrusted data; only explicit MCP arguments passing server-side validation may request an action.

## 11. Error and recovery behavior

### Client/chat disappears

No effect on already accepted Builder execution. A later client calls `resume_context()` and receives the durable state.

### MCP server restarts

No Mission/task/attempt truth may be lost because the bridge owns none of it. On restart it reconstructs projections from Git/Kitty/Builder state.

### Worker/provider dies

Use existing Builder lease, attempt, provider-exhaustion and recovery semantics. Do not translate provider exhaustion into fabricated implementation failure.

### Duplicate `execution_start`

Return the existing live execution or a collision result. Never run two owners against the same packet.

### Plan/design changed after approval

Invalidate approval; require a new Mission version and explicit approval.

### Tests fail

Builder remains responsible for repair iterations and independent review within policy. Result stays incomplete until acceptance evidence passes.

### PR exists but runtime is unverified

Report `IMPLEMENTED-NOT-VERIFIED`/equivalent, not done.

## 12. Implementation boundary

Prefer a focused package:

```text
mcp/builder/
    __init__.py
    server.py          # MCP registration + transport entry point only
    schemas.py         # public request/receipt models
    context.py         # read projections + resume_context assembly
    repo_tools.py      # allowlisted tracked repo reads/planning artifacts
    commands.py        # canonical Builder command adapters
    auth.py            # remote auth hooks / client identity boundary
```

Tests:

```text
tests/test_mcp_builder_context.py
tests/test_mcp_builder_repo_tools.py
tests/test_mcp_builder_commands.py
tests/test_mcp_builder_continuity.py
tests/test_mcp_builder_security.py
```

Do not place execution logic in `server.py`. Do not import or mutate Builder SQLite tables from the MCP package. Use public/canonical Builder functions/routes/CLI boundaries; if the implementation discovers that a required canonical API does not exist, add the smallest API in the Builder-owned module and test it there.

Reuse the repository's existing `mcp` namespace-package arrangement and installed MCP SDK rather than creating a second MCP framework.

## 13. Phased delivery

### Slice 1 — read-only bridge + continuity

Ship `kitty_context`, `repo_search`, `repo_read`, `work_status`, `work_result`, and `resume_context` with security/path tests.

This slice is independently useful and proves a fresh chat can recover project state without copied transcript.

### Slice 2 — versioned planning artifacts

Ship `save_design` and `save_plan` with SHA preconditions and isolated planning publication. Prove concurrent/stale writes fail safely.

### Slice 3 — prepared Mission + approval

Ship `mission_prepare` and `mission_approve`. Prove the exact approved design/plan/version is what Builder receives; changed inputs invalidate approval.

### Slice 4 — durable execution start/control

Ship `execution_start`, pause/resume/cancel and status. Prove the MCP call can return while Builder remains durably inspectable, and duplicate starts cannot create duplicate execution owners.

### Slice 5 — one KPROOF real feature loop

From a conversation:

1. inspect the live repo;
2. discuss a small real feature/fix;
3. save design;
4. save implementation plan;
5. Jacob approves the exact Mission version;
6. start Builder;
7. Builder edits/tests/launches/reviews/repairs;
8. produce PR + evidence;
9. start a fresh chat/session;
10. call `resume_context()`;
11. correctly explain what happened and the next action without pasted chat history.

That is the acceptance demonstration for this bridge.

### Slice 6 — ChatGPT remote attachment when eligible

Expose the same server through the supported authenticated remote/tunnel path and register it as a custom MCP app when Jacob's ChatGPT plan supports the required write actions. No code fork for ChatGPT is allowed unless the MCP standard itself requires an adapter.

## 14. Testing strategy

### Unit/contract tests

Prove:

- all public tool schemas are strict;
- path traversal and protected paths are rejected;
- read tools cannot mutate state;
- planning writes require expected SHAs;
- stale design/plan/version cannot be approved;
- approval nonce is one-use and version-bound;
- `execution_start` is idempotent/collision-safe;
- domain `ok:false` is surfaced as failure even if transport succeeds;
- missing evidence remains unknown/unavailable;
- `resume_context` is deterministic from the same durable source state;
- no tool exposes secret values.

### Integration tests

Use temporary repositories and isolated Builder stores to prove:

- design → plan → prepared Mission linkage;
- explicit approval → one accepted execution;
- interrupted/restarted bridge → same Builder state;
- worker failure/recovery → new client sees accurate continuation;
- result/PR evidence appears in receipts.

### Real KPROOF acceptance

Unit tests are not enough. The final gate is a real launched-app feature loop under KPROOF-001 with a second-model review and fresh-chat continuity test.

## 15. Success criteria

V1 succeeds only when all are true:

1. Jacob can discuss a software change conversationally and save the agreed design/plan without manually moving text between tools.
2. The exact approved version becomes durable Builder work with no second execution owner.
3. Builder performs code/test/review/recovery work using its existing governance.
4. The conversational client can inspect accurate progress without reading raw Builder storage.
5. Completion is backed by tests/runtime/review evidence, not worker narration.
6. A new chat can call `resume_context()` and continue correctly without Jacob copying prior context.
7. A PR/result is presented with a concise structured receipt and one next action.
8. ChatGPT-specific availability does not determine or corrupt Kitty's architecture.

## 16. Explicitly deferred

After KPROOF passes, later work may consider:

- push notifications when a Builder result/decision is ready;
- richer MCP resources/prompts/UI components;
- multi-repository project selection;
- broader document/artifact editing;
- remote access beyond Jacob's trusted clients;
- automated PR merge under a separately approved policy;
- generalized non-code computer-control tools.

None of those may expand this proof before the core loop is demonstrated.

## 17. Design self-review

- **Placeholder scan:** no TBD/TODO or unresolved implementation requirement remains in the v1 contract.
- **Authority check:** MCP remains an adapter; Kitty owns intent and Builder owns execution truth.
- **Scope check:** slices are independently testable and the only end-to-end goal is KPROOF's one real feature loop.
- **Continuity check:** context-loss recovery is based on durable artifacts and Builder evidence, not chat summaries.
- **Safety check:** no raw model-controlled shell/filesystem/Git publication bypass is introduced.
- **Platform check:** current ChatGPT MCP plan limitations are a deployment gate, not hidden as an architecture assumption.
