# Kitty and KittyBuilder Alignment Map

**Ratified:** 2026-07-26 by Jacob
**Authority:** architectural and execution frame under accepted ADRs

This map governs shape: what belongs where, what may be built, and in what
order. It does not override live repository, runtime, Git, GitHub, or Builder
evidence.

## North star

Kitty is the user-facing operating system and engineering partner.
KittyBuilder is Kitty's controlled execution engine — not a separate product,
independent authority, or competing source of truth.

The complete delivery chain is:

> Intent → grounded plan → bounded packet → leased execution → verified result
> → review evidence → merge decision → durable memory → clear UI

All proposed work must strengthen this chain.

## Authority order

When sources disagree, higher wins:

1. Live repository, runtime, Git, and GitHub evidence
2. Durable Builder records and immutable receipts
3. Versioned generated snapshots
4. Accepted ADRs and canonical governance documents
5. `docs/ROADMAP.md`, the active Mission, and approved executable contracts
6. Research, audits, old plans, and generated summaries
7. Agent narrative or chat history

## Architectural layers

### Intent and judgment

Kitty owns objectives, priorities, acceptance criteria, boundaries, risk
classification, and escalation to Jacob. Architecture judgment, decomposition,
and packet authoring belong to Jacob, Kitty, or an explicitly assigned strong
planning model under ADR 0020.

Workers execute bounded authority. They do not redefine the mission.

### Ground truth

Kitty inspects current repository and runtime reality before planning or acting.
Canonical facts include current SHA, branch, dirty state, worktrees, PRs,
Builder queue state, attempts, leases, evidence, manifests, tests, and actual
code structure.

### Planning

There is one active roadmap: `docs/ROADMAP.md`.

Initiatives describe coherent approved outcomes. Packets are executable
contracts, not the idea store or roadmap. Every packet has:

- one bounded outcome;
- explicit allowed paths;
- supported dependencies;
- runnable and falsifiable validation;
- acceptance criteria;
- stopping and escalation rules;
- a review and merge policy.

Impossible execution conditions become validation errors, not warnings.
Research, audits, old plans, prose packets, and unapproved manifests remain
preserved inputs but do not compete with the roadmap.

### Execution

Builder validates approved contracts and proactively selects the
highest-priority eligible approved packet. It owns orchestration, queueing,
worktrees, leases, retries, timeouts, cancellation, evidence, publishing, and
state transitions.

A failed or blocked packet does not stop unrelated eligible work. Provider
exhaustion produces a durable resumable pause. Builder does not invent packets
or make unresolved design decisions.

Claude, Codex, OpenCode, shell workers, and local models are replaceable
`WorkerSession` backends. Preserve all reliability behavior earned by the
existing shell adapter before replacing or abstracting it.

### Verification

Worker completion is not acceptance. Independently verify:

- exact diff and changed paths;
- task, attempt, branch, and commit identity;
- scope and authority;
- acceptance criteria and deterministic gates;
- architecture and duplication risk;
- base-branch and post-merge health.

Classify every claim as verified, inferred, blocked, unverified, pre-existing
failure, or newly introduced failure.

### State and recovery

Maintain one explicit Builder state machine and one narrow transition API.
Recover from crashed workers, stale leases, dirty worktrees, orphaned attempts,
missing outcomes, interrupted reviews, provider exhaustion, externally created
PRs, and disagreement between Builder, Git, and GitHub.

Recovery uses durable evidence, never worker memory or chat prose.

### Product surface

CLI, API, and UI consume the same canonical Builder state. Extend the existing
Builder snapshot, SSE infrastructure, and `BuilderSurface`; do not create
parallel systems.

The product surface shows objective, next action, packet state, workers,
leases, evidence, failures, review status, PR state, uncertainty, and operator
controls. Kitty remains useful when Builder is unavailable.

### Knowledge and continuity

Persist decisions, evidence, outcomes, failures, risks, and next steps. Chat
history and one long-running conversation are never the system of record.
Working detail belongs in repository documents and Builder artifacts; chat gets
the outcome and decisions Jacob must make.

### Governance

Keep governance small, canonical, and enforceable. Escalate when authority is
missing or a ratified decision would change — not merely because a file is
categorized as protected.

## Delivery sequence

### Phase 1 — Trust foundation and first complete proof

- restore functioning Python and frontend CI;
- finish the current manifest and governance PRs;
- repair contradictory planning and mission authorities;
- close Builder reliability and recovery by evidence;
- author verified `free-exec` manifest packets;
- prove proactive unattended execution in daylight;
- complete one real life-project resume loop end to end.

**Exit:** Builder accurately proves what happened, and Kitty turns one real
project's state into a delivered next move without archaeology.

### Phase 2 — Unified workers

- define `WorkerSession` from the existing adapter contract;
- encode shell-adapter behavior as contract tests;
- adapt worker backends without changing Builder semantics;
- unify attempts, receipts, logs, outcomes, and explicit model policy.

**Exit:** worker backends are interchangeable without moving truth into model
sessions.

### Phase 3 — Unified runtime and UI

- version the canonical Builder snapshot;
- extend SSE only where cursor, replay, filtering, or reconnect evidence
  requires it;
- refactor the existing `BuilderSurface` rather than building another cockpit;
- ensure CLI, API, and UI tell the same verifiable story.

**Exit:** every interface reports identical supported state.

### Phase 4 — Broader controlled autonomy

- overlap-aware cross-initiative scheduling;
- automated repair preparation and decision escalation;
- broader policy-controlled merge classes;
- adaptive model routing backed by quality/cost evidence.

Basic proactive selection of already-approved packets is not deferred to this
phase; it is the operating rule in ADR 0021. Phase 4 expands autonomy only after
the lower layers are proven.

## Non-goals until Phase 1 exits

Do not:

- create new queues, orchestrators, state stores, event systems, schedulers, or
  Builder cockpits;
- run overlapping initiatives without collision analysis;
- introduce autonomy to compensate for dead gates or ambiguous state;
- replace working shell behavior with an incomplete abstraction;
- treat reports, PR URLs, exit codes, or worker summaries as verified evidence;
- expand task scope without recording and reauthorizing the change;
- rely on chat continuity as durable memory;
- start broad new feature lanes because they appear in an older plan.

## Required analysis for every architecture proposal

Before implementation, record:

1. existing subsystem inventory;
2. problem proven by evidence;
3. canonical owner;
4. whether the proposal extends, replaces, or duplicates existing code;
5. state and authority implications;
6. failure and recovery behavior;
7. validation strategy;
8. migration and compatibility concerns;
9. scope and path-collision risk;
10. why the work belongs in the current phase.

Work that conflicts with this map is not implemented. Surface the conflict and
propose the smallest aligned alternative.

## Operating consequences

### Cost is a live planning constraint

Free and paid execution are explicit packet classes, not accidental fallbacks.
Paid reasoning is reserved for planning, patch-level authoring, judgment-heavy
execution, or high-risk review. Free execution is allowed only when a script
can decide correctness.

### Free execution and verification are one project

A weak model cannot be trusted to judge its own success. Acceptance therefore
must be deterministic, runnable, and falsifiable, or the packet is not
`free-exec`.

### Autonomy is gated on evidence

As of this ratification, Python dependency installation and frontend package
installation are broken on the base branch. Until both are restored, nightly
unattended execution cannot produce trustworthy acceptance evidence. The drain
is extended only after clean CI, verified packets, and one daylight proof run.
