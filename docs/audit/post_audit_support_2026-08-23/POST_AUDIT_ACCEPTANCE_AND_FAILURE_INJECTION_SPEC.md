# Kitty Post-Audit Acceptance + Failure-Injection Specification

Status: PRE-AUDIT / implementation-neutral
Created: 2026-08-22
Original observation baseline: `main` at `782b8ff64a27` with a pre-existing modification to `config/providers.json`.
Packaged into the repository on 2026-08-23 via the docs-only audit-support branch rebased onto `origin/main` `d11febfb9974d41c00a836d0450a10916c72add1`.
The original baseline is provenance only; the sequential auditor must re-verify current repository truth before using any case.

## Purpose

This document defines the evidence required to say **Kitty actually works** after the sequential audit and its resulting implementation work.

It is deliberately separate from the audit findings. It must not be used to prejudge which implementation is correct, which subsystem should be kept, or which audit findings are valid.

Primary goals:
- turn "tests passed" into product-level proof;
- catch failures that only appear when individually-correct components are composed;
- prove restart, retry, recovery, and cancellation behavior;
- prevent silent success, silent data loss, silent duplicate execution, and silent spend;
- give future coding agents a fixed acceptance target independent of implementation details.

Default engineering preference remains:
`DELETE > SIMPLIFY > CONSOLIDATE > FIX > OPTIMIZE > REWRITE`.

## Non-Interference Rules

Until the audit reaches its final execution plan, this specification is descriptive only.
Do not modify Kitty to satisfy it early.
Do not open PRs or issues solely from this document.
Do not use it to override verified audit evidence.

## Acceptance Philosophy

A journey passes only when the externally-visible result, durable state, and evidence all agree.

For every state-changing operation, verify three layers:
1. **Intent** — what the user explicitly requested or approved.
2. **Execution truth** — what actually ran and what side effects occurred.
3. **Durable product truth** — what Kitty reports after refresh and restart.

A green HTTP response is not sufficient evidence of success.
A passing unit test is not sufficient evidence of an integration contract.
A UI toast is not sufficient evidence of durable completion.

Every important test should be able to answer:
- What state existed before?
- What exact action was attempted?
- What side effects occurred?
- What state exists after?
- What survives process restart?
- What evidence proves the claim?

## Evidence Contract

Each acceptance run should capture:
- exact Git SHA and dirty/clean status;
- relevant service versions and configuration profile;
- test command and exit code;
- request/action identifiers where applicable;
- durable database/state evidence;
- user-visible result;
- logs or execution evidence sufficient to diagnose failure;
- provider cost/usage evidence for paid operations when applicable.

## Core Product Acceptance Journeys

### ACC-001 — Cold Launch to Ready
Precondition: Kitty services are not running.
Action: launch through the supported daily-driver entry point.
Pass criteria:
- canonical native UI becomes reachable;
- Gateway becomes genuinely healthy, not merely port-open;
- readiness does not depend on a process already shutting down;
- UI does not claim ready before required backend dependencies are ready;
- one refresh preserves a healthy state;
- evidence identifies which processes Kitty owns.

### ACC-002 — Basic Chat Truth
Action: send a normal chat request that requires no side effect.
Pass criteria:
- exactly one intended conversation turn is durably recorded;
- assistant response corresponds to the submitted request;
- refresh preserves the same conversation truth;
- Gateway restart does not lose the completed turn;
- provider failure is visibly distinguishable from a valid empty response.

### ACC-003 — Tool Read Path
Action: execute a representative read-only tool through the normal product path.
Pass criteria:
- tool identity and arguments are observable;
- read executes once;
- result is associated with the correct conversation/action;
- failure is surfaced truthfully;
- no unrelated durable state is mutated.

### ACC-004 — Explicit Side-Effect Path
Action: perform a representative approved state-changing action.
Pass criteria:
- authority/approval is explicit at the correct boundary;
- approved identity includes the operation and material arguments;
- post-approval mutation that changes meaning is rejected or requires new approval;
- execution occurs no more than once;
- durable result agrees with the real external/local side effect;
- failure cannot be represented as success.

### ACC-005 — Work Creation and Resume
Action: create one unit of Work through the canonical product path.
Pass criteria:
- exactly one durable Work identity is created;
- the UI and backend agree on state;
- refresh preserves state and history;
- Gateway restart preserves state;
- resuming does not create a second logical Work item;
- obsolete task surfaces do not become competing authorities.

### ACC-006 — Builder Execution
Action: send a bounded software-execution mission through the supported Builder path.
Pass criteria:
- one mission maps to traceable attempts;
- attempt ownership is explicit;
- progress shown in Kitty reflects durable Builder truth;
- validation/review evidence is attached to the correct attempt;
- terminal success means the requested artifact/change actually exists;
- terminal failure retains actionable evidence;
- refresh/restart does not invent a new attempt.

### ACC-007 — Approval Persistence
Action: create an operation requiring approval, approve it, then refresh/restart before execution completes.
Pass criteria:
- the approved operation remains exactly the approved operation;
- approval cannot silently broaden to another tool, target, or argument set;
- replay does not duplicate the side effect.

### ACC-008 — Restart Recovery
Action: establish active conversation + pending/active work, restart supported Kitty services, then reopen UI.
Pass criteria:
- completed work remains completed;
- active work resumes or becomes explicitly recoverable;
- stale workers cannot overwrite newer state;
- no duplicate execution begins merely because of restart;
- UI state converges to durable backend truth.

### ACC-009 — Notification Truth
Action: trigger one representative notification from a completed durable event.
Pass criteria:
- notification corresponds to a real event;
- it is emitted no more than once unless repetition is intentional;
- clicking/resuming resolves to the correct underlying object;
- restart does not regenerate already-consumed notifications without cause.

### ACC-010 — Memory Correction Freshness
Action: store a fact, retrieve it, explicitly correct/supersede it, then issue the same relevant query again.
Pass criteria:
- corrected truth is returned immediately or within the documented consistency boundary;
- an in-process cache cannot return the known-stale value as current truth;
- provenance/supersession remains inspectable;
- restart preserves the corrected state.

### ACC-011 — Backup and Restore Fidelity
Action: create a representative snapshot, restore into an isolated test state, and compare logical records.
Pass criteria:
- no silently truncated store;
- unsupported snapshot content fails before partial mutation;
- reported import counts equal actual imported records;
- restored state passes integrity checks and representative reads.

### ACC-012 — Paid Operation Accounting
Action: run a test-mode or deliberately low-cost paid operation through its supported product path.
Pass criteria:
- estimated cost is visible before execution when product policy requires it;
- reservation/authorization exists before provider submission;
- one logical request produces at most one unintended billable submission;
- actual cost reconciles against reserved/estimated cost when provider data exists;
- provider timeout does not automatically imply safe resubmission;
- final product state distinguishes unknown outcome from confirmed failure.

### ACC-013 — Image Lab Integration Seam
Scope: product-level integration only; do not use this specification to alter active Image Lab implementation work.
Action: after the Image Lab lane is complete, run one canonical reference-to-result journey.
Pass criteria:
- native Image Lab is the visible product authority;
- session/artifact identity survives refresh/restart;
- failure and cost states are truthful;
- reference/character association is durable;
- no duplicate paid generation is caused by recovery logic.

### ACC-014 — Canonical Authority Consistency
Action: inspect product docs, routes, UI navigation, and runtime ownership after convergence work.
Pass criteria:
- a coding agent can identify one canonical frontend without contradictory authoritative docs;
- Gateway vs Builder execution ownership is unambiguous;
- legacy surfaces are explicitly marked legacy or removed;
- there is no second durable authority for the same user concept without a documented reason.

## Failure-Injection Matrix

Failure tests must use disposable state, test doubles, or controlled local processes whenever the real side effect could be destructive or costly.
### FI-001 — Gateway Dies During Read Request
Inject: terminate Gateway while a representative read request is in flight.
Expected:
- client receives failure/unknown, never fabricated success;
- restart yields a healthy Gateway;
- no durable mutation appears.

### FI-002 — Gateway Dies After Local Mutation
Inject: terminate at the boundary after a local side effect but before response completion.
Expected:
- recovery can distinguish committed from uncommitted state;
- retry does not blindly repeat a non-idempotent operation;
- UI can represent outcome as unknown when certainty is impossible.

### FI-003 — Stop Then Immediate Ensure
Inject: stop the managed Gateway and immediately invoke the supported ensure/start behavior.
Expected:
- old shutting-down process cannot satisfy final readiness;
- ensure performs a stabilization/final health check;
- resulting Gateway remains alive after the old process fully exits.

### FI-004 — Builder Worker Dies Mid-Attempt
Inject: kill worker after attempt claim and before completion.
Expected:
- lease/heartbeat expires predictably;
- work is recoverable according to policy;
- old worker cannot later commit over a newer attempt;
- evidence clearly shows interrupted attempt.

### FI-005 — Duplicate Mission Submission
Inject: submit the same logical mission twice through the retry/reconnect boundary.
Expected:
- idempotency policy is explicit;
- duplicate execution is prevented where the product promises one logical action;
- otherwise duplicate intent is clearly surfaced to the user.

### FI-006 — Late Worker Response
Inject: let attempt A lose ownership, start attempt B, then allow A to report success late.
Expected:
- fencing prevents stale completion from replacing newer truth;
- evidence retains the stale response for diagnosis without accepting it as authority.

### FI-007 — External Success, Local Timeout
Inject: external system completes the side effect while Kitty times out waiting for confirmation.
Expected:
- state becomes unknown/reconciling rather than failed-with-safe-retry;
- retry policy accounts for possible prior success;
- reconciliation can discover the external result where supported.

### FI-008 — Local Success, External Follow-Up Failure
Inject: local durable transition succeeds but subsequent GitHub/provider/notification call fails.
Expected:
- state records which portion succeeded;
- retry targets only the failed stage;
- user is not told the entire operation succeeded.

### FI-009 — Approval Then Argument Mutation
Inject: approve operation A, then alter a material target/argument before execution.
Expected:
- execution is rejected or requires new approval;
- approval evidence remains bound to the originally approved call identity.

### FI-010 — Specific Deny vs Broad Allow
Inject: create policy conditions where a broad/session allow overlaps a more-specific deny.
Expected:
- documented policy precedence is deterministic and fail-safe;
- a narrower explicit deny cannot be accidentally weakened by incidental scoping.

### FI-011 — Provider 5xx/Transport Failure
Inject: fail provider before a confirmed response.
Expected:
- read-like requests follow bounded retry policy;
- non-idempotent paid operations do not blindly resubmit;
- failure/unknown is distinguishable from valid empty output.

### FI-012 — Cache Stale After Explicit Correction
Inject: warm a context/memory cache, then correct the underlying fact and repeat the same query.
Expected:
- correction invalidates or bypasses stale cached truth;
- stale content is not presented as current without an explicit consistency disclaimer.

### FI-013 — Unknown Restore Store
Inject: add an unsupported store key to an otherwise valid disposable backup snapshot.
Expected:
- entire snapshot is validated before any target mutation;
- restore fails cleanly with zero partial import.

### FI-014 — Large Backup Dataset
Inject: create more records than any common default list limit in disposable stores.
Expected:
- exported counts equal source counts;
- restore counts equal exported counts;
- no silent 1000-record or pagination truncation.

### FI-015 — Async Route With Slow Sync Dependency
Inject: make a synchronous dependency sleep while concurrently issuing another cheap Gateway request.
Expected:
- unrelated request remains responsive within the accepted latency budget;
- blocking work is isolated from the event loop where required.

### FI-016 — UI Refresh During Transition
Inject: refresh while work/action/Builder state is transitioning.
Expected:
- UI reconstructs from durable authority;
- transient optimistic state does not become permanent truth;
- duplicate requests are not created by mount/reconnect behavior.

### FI-017 — Whole-Machine Restart
Inject: controlled machine/service restart with recoverable active state.
Expected:
- durable truth survives;
- ownership/leases recover safely;
- no paid or destructive action repeats merely because process memory disappeared.

### FI-018 — Log/History Growth
Inject: use representative large generated history/log files in isolated test state.
Expected:
- hot paths do not require unbounded full-file reads when only a tail/window is needed;
- retention/rotation behavior is explicit where growth is unbounded.

## Required Test Layers

### Layer 1 — Unit
Use for pure policy, parsing, transition, ranking, cost, and validation behavior.
Unit tests are necessary but never sufficient for cross-subsystem findings.

### Layer 2 — Contract
Verify frontend/Gateway, Gateway/Builder, Gateway/provider, and storage adapter contracts.
Assert failure shapes as strongly as success shapes.

### Layer 3 — Integration
Use real application components with disposable state.
Required for:
- queue + executor registration;
- approval + execution identity;
- cache + write invalidation;
- export + import;
- supervisor + process lifecycle;
- frontend query + canonical backend state.

### Layer 4 — Failure Injection
Deliberately interrupt state transitions at meaningful commit boundaries.
Tests must prove both resulting durable state and side-effect count.

### Layer 5 — Product Journey
Exercise the supported user surface end-to-end.
This is the final defense against components that individually pass while the assembled product fails.

## Regression-Test Rule

Every verified High/Critical audit finding that is fixed must gain a regression test at the lowest layer capable of reproducing the real failure.
If the defect crossed a component boundary, a unit-only regression test does not satisfy this rule.

## Release Gate

Kitty is not considered post-audit converged until all applicable statements below are supported by evidence:

- canonical product authority is unambiguous;
- cold launch reaches stable readiness;
- normal chat survives refresh/restart;
- read-only tools cannot accidentally mutate unrelated durable state;
- side-effect authority is explicit and bound to the executed call;
- one logical non-idempotent operation cannot silently execute twice;
- Builder survives worker/service failure without stale completion winning;
- active durable work can be recovered after supported restart scenarios;
- UI state converges to backend durable truth after refresh/reconnect;
- explicit memory corrections are not masked by stale caches;
- backup/restore fidelity is demonstrated beyond default pagination limits;
- restore validation prevents known partial-mutation failure modes;
- paid-operation outcome and accounting are truthful;
- dependency/security checks classified as required actually gate CI;
- known obsolete duplicate authorities are removed or explicitly quarantined;
- representative hot paths meet measured budgets rather than theoretical expectations.

A waived item must include:
- reason;
- risk accepted;
- owner;
- expiry/revisit condition;
- evidence showing why the waiver is bounded.

## Audit Handoff Contract

After Chunk 10 reconciliation, map each acceptance/failure case to the verified finding IDs it addresses.
Do not change an acceptance criterion merely because the current implementation fails it.
If the audit disproves an assumption embedded here, amend this document explicitly and record why.
