# Kitty and KittyBuilder Alignment Map

**Ratified:** 2026-07-26 by Jacob. This is the architectural and execution
frame for all further Kitty and KittyBuilder work.

Authority: this map governs *shape* — what belongs where, what may be built,
and in what order. It does not override live repository, runtime, or Builder
evidence (see the authority order below). It sits above initiative manifests
and plans, and below ratified ADRs.

## North star

Kitty is the user-facing operating system and engineering partner.
KittyBuilder is Kitty's controlled execution engine — not a separate product,
independent authority, or competing source of truth.

The complete delivery chain:

> Intent → grounded plan → bounded packet → leased execution → verified
> result → review evidence → merge decision → durable memory → clear UI

All proposed work must strengthen this chain.

## Authority order

When sources disagree, higher wins. Never let a lower-authority source
override higher-authority evidence.

1. Live repository, runtime, Git, and GitHub evidence
2. Durable Builder records and immutable receipts
3. Versioned generated snapshots
4. Ratified ADRs and canonical governance documents
5. Initiative manifests and active plans
6. Research reports and generated summaries
7. Agent narrative or chat history

## Architectural layers

### Intent and judgment

Kitty owns objectives, priorities, acceptance criteria, boundaries, risk
decisions, and escalation to the user. Workers execute bounded authority.
They do not redefine the mission.

### Ground truth

Kitty must inspect current repository and runtime reality before planning or
acting. Canonical facts include current SHA, branch, dirty state, worktrees,
PRs, queue state, attempts, leases, evidence, manifests, tests, and actual
code structure.

### Planning

Initiatives describe coherent outcomes. Packets are executable contracts.

Every packet must have: one bounded outcome; explicit allowed paths;
supported dependencies; runnable validation; acceptance criteria; stopping and
escalation rules; a review surface.

Impossible execution conditions must eventually be validation errors, not
warnings.

### Execution

Builder owns orchestration, queueing, worktrees, leases, retries, timeouts,
cancellation, evidence, publishing, and state transitions. Claude, Codex,
OpenCode, shell workers, and local models are replaceable `WorkerSession`
backends.

Preserve all reliability behaviours earned by the existing shell adapter
before replacing or abstracting it.

### Verification

Worker completion is not acceptance. Independently verify the diff, scope,
identity, acceptance criteria, tests, architecture, duplication risk, and
base-branch health.

Classify every claim as: verified, inferred, blocked, unverified,
pre-existing failure, or newly introduced failure.

### State and recovery

Maintain one explicit Builder state machine and one narrow transition API.
Support recovery from crashed workers, stale leases, dirty worktrees,
orphaned attempts, missing outcomes, externally created PRs, and disagreement
between database state and Git/GitHub.

### Product surface

CLI, API, and UI must consume the same canonical Builder state. Extend the
existing Builder snapshot, SSE infrastructure, and `BuilderSurface` rather
than creating parallel systems.

The UI must clearly show objective, next action, packet state, workers,
leases, evidence, failures, review status, PR state, uncertainty, and
operator controls.

### Knowledge and continuity

Persist decisions, evidence, outcomes, failures, risks, and next steps. Do
not use chat history or one long-running conversation as the system of record.

### Governance

Keep governance small, canonical, and enforceable. Escalate when authority is
missing or a ratified decision would change — not merely because a file is
categorized as protected.

## Delivery sequence

### Phase 1 — Trust foundation

- restore functioning Python and frontend CI
- finish PR #261
- repair invalid manifests and impossible gates
- establish canonical Builder state
- enforce leases, identity, scope, and transitions
- prove recovery behaviour

**Exit:** Builder can accurately state and prove what happened.

### Phase 2 — Unified workers

- define `WorkerSession`
- encode existing shell-adapter behaviour as contract tests
- adapt all worker backends to the contract
- unify attempts, receipts, logs, and outcomes
- centralize model and cost policy

**Exit:** worker backends are interchangeable without changing Builder
semantics.

### Phase 3 — Unified runtime and UI

- version the canonical Builder snapshot
- extend SSE with cursor, replay, filtering, and reconnect support
- refactor the existing `BuilderSurface`
- add reliable operator commands and receipts
- ensure CLI, API, and UI report identical state

**Exit:** every interface tells the same verifiable story.

### Phase 4 — Controlled autonomy

- safe packet selection
- bounded repair and retry
- overlap-aware initiative scheduling
- automated review preparation
- policy-controlled merge
- explicit decision escalation
- adaptive model routing

**Exit:** autonomy operates safely because the lower layers are trustworthy.

## Non-goals until the foundation is stable

Do not:

- create new queues, orchestrators, state stores, event systems, or Builder
  cockpits
- run overlapping initiatives without collision analysis
- introduce autonomy to compensate for unreliable state
- replace working shell behaviour with an incomplete abstraction
- treat reports or worker summaries as verified evidence
- expand task scope without recording the change
- rely on chat continuity as durable memory

## Required analysis for every future proposal

Before implementing any Builder or Kitty architecture change, report:

1. Existing subsystem inventory
2. Problem proven by evidence
3. Canonical owner of the responsibility
4. Whether the proposal extends, replaces, or duplicates existing code
5. State and authority implications
6. Failure and recovery behaviour
7. Validation strategy
8. Migration and compatibility concerns
9. Scope and path-collision risks
10. Why this work belongs in the current phase

Work that conflicts with this map is not implemented. Surface the conflict and
propose the smallest aligned alternative.

## Operating consequences

These follow from the map above and are recorded so they are not re-derived.

### Cost is a Phase 1 constraint, not a Phase 4 optimisation

The map places "centralize model and cost policy" in Phase 2 and "adaptive
model routing" in Phase 4. In practice Jacob's paid-model budget is exhausted
now, which means free-model execution is a *precondition* for reaching those
phases, not a reward for finishing them.

The resolution is not to move autonomy earlier. It is to make packets
executable by models that cannot reason — see
`docs/FREE_MODEL_PACKET_STANDARD.md`. That standard is a Phase 1 artifact
because it is a planning constraint, not a routing feature.

### Free-model execution and the verification layer are the same project

A model too weak to reason is also too weak to be trusted about whether it
succeeded. The map already says "worker completion is not acceptance." Under
free-model execution that stops being a discipline and becomes a hard
requirement: **acceptance must be decidable by a script, or the packet is not
free-model-ready.**

This is why "impossible execution conditions must eventually be validation
errors, not warnings" matters more than it appears. A warning is a message to
a human who is paying attention. A nightly unattended drain has no such human.

### Autonomy is gated on CI, not on ambition

Non-goal: "introduce autonomy to compensate for unreliable state." As of
2026-07-26 the repository has **no working Python gate at all** — dependency
resolution fails before any test runs — and the frontend job fails at install.
Until both are green, a validation command proves nothing, and an unattended
nightly drain produces unverifiable work at volume.

Scheduling the drain before CI is restored would violate this map.
