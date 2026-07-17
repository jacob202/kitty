# ADR 0017: Kitty → Mission → KittyBuilder Control-Plane Boundary

- **Status:** Accepted
- **Date:** 2026-07-17
- **Decision owner:** Jacob
- **Supersedes:** the no-write/read-only integration claim in
  `docs/BLUEPRINT.md` section 2 and the design-complete claim in
  `docs/NORTH_STAR.md` section 3

## Context

Kitty already contains a conversational product, durable product stores, model
routing, tools, and a governed Builder with queues, initiatives, attempts,
leases, isolated worktrees, validation, recovery, review, and publication
rails. The documented boundary still says Kitty may only observe Builder. That
prevents the intended product loop: Jacob explains an outcome to Kitty, Kitty
turns it into an approved mission, and Builder executes without manual context
transfer.

A separate permanent project-manager agent would split intent, authority, and
continuity across runtimes. Worker models would again become accidental owners
of project truth. The boundary instead needs a durable contract between the
principal product agent and the existing execution organization.

## Decision

The accepted flow is:

```text
Jacob ↔ Kitty → approved Mission → KittyBuilder → verified Result/Evidence → Kitty ↔ Jacob
```

Kitty is the principal agent and intent compiler. KittyBuilder is the execution
control plane. A Mission is their only durable command boundary. This ADR
defines that contract; it does not enable autonomous submission or mutation.

### Kitty responsibilities

Kitty:

1. maintains the conversation with Jacob and the user-facing project model;
2. retrieves only context relevant to the current intent and records missing,
   stale, or contradictory context explicitly;
3. challenges material assumptions and distinguishes facts from proposals;
4. defines the desired outcome, evidence needed, constraints, risks, and
   unresolved decisions;
5. selects an execution strategy: direct reasoning, retrieval, research,
   tools, records, experts, or an approved Builder mission;
6. explains decisions and results in a way that increases Jacob's capability;
   and
7. surfaces only relevant progress, blockers, and authorization requests.

Kitty does not own Builder task/run truth and must not infer it from chat,
handoffs, logs, or worker claims.

### KittyBuilder responsibilities

KittyBuilder:

1. validates and durably records accepted missions and their policy version;
2. decomposes work into bounded packets and dependencies;
3. selects replaceable workers/models and packages the minimum sufficient
   context;
4. enforces allowed paths, authority, budgets, attempt limits, leases, and
   isolation;
5. records execution, validation, independent review, recovery, and
   publication state;
6. stops or escalates when evidence, authority, budget, or context is
   insufficient; and
7. returns structured result/evidence references rather than a narrative claim
   of completion.

Builder does not own Jacob's conversational intent, product memory, personal
stores, or final authorization. No worker approves its own work.

## Mission object

A versioned Mission contains:

```text
Mission
  schema_version, mission_id, created_at, approved_at
  origin
    conversation_id, message_refs[], project_id
    repository, base_sha, context_receipt_ref
  objective
    outcome, rationale, non_goals[]
  context
    required_refs[], selected_refs[], missing[], contradictions[]
    assumptions[{claim, evidence, disposition}]
  execution
    strategy, packets[], dependencies[]
    allowed_paths[], forbidden_operations[]
    worker_constraints, routing_policy
  authority
    risk_tier, policy_version, approvals[], expires_at
  budgets
    max_attempts, max_time, max_tokens, max_cost
  evidence_plan
    acceptance_criteria[], validation_commands[], required_artifacts[]
    independent_review
  state
    proposed | awaiting_approval | approved | accepted | running
    | blocked | succeeded | failed | cancelled | superseded
```

References point to owning stores; the Mission does not copy whole
conversations, repositories, Builder rows, or secrets. Approval binds the
objective, scope, authority, budgets, evidence plan, base SHA, and receipt. A
material change creates a new revision and may require re-approval.

## Human authorization boundaries

- Kitty may inspect, retrieve, diagnose, draft, challenge assumptions, and
  prepare a Mission without approval when those actions are read-only.
- Existing repository/user policy decides whether an approved Mission may be
  submitted automatically or requires a human action. This ADR does not grant
  that submission authority.
- Push, merge, destructive changes, auth/secrets/env, paid or heavy
  dependencies, external messages, and broad scope expansion remain explicit
  Jacob gates.
- Approval is scoped and expiring. Approval of a Mission or one publication
  action never becomes general authority.
- Access, retrieval, monitoring, memory, and action permissions are evaluated
  separately; possession of one never implies another.

## Cost and model routing

Workers are replaceable. Routing optimizes for 90–95% of the achievable quality
at materially lower cost while preserving the evidence threshold. Builder
starts with the cheapest route that can satisfy the packet's capability and
risk constraints. It escalates only when a recorded failure, evaluation,
context limit, or safety classification justifies it. High price or model name
is not evidence of quality, and a cheap worker's assertion is not evidence of
completion.

## Result and evidence flow

Builder returns a versioned result linked to the Mission revision, exact base
and result SHAs, attempts, model/worker receipts, changed paths, validations,
review verdict, artifacts, costs when known, and publication state. Unknown
cost is `unknown`, never zero. Kitty reads this through supported projections,
checks it against the evidence plan, and communicates:

- verified outcome;
- what changed and why;
- evidence and limitations;
- decisions or actions still needed; and
- concise teach-back that helps Jacob understand or reproduce the result.

Only accepted validation and review evidence can satisfy completion. Exit code,
worker prose, a PR URL, or an absent error cannot.

## Failure and stale-context handling

- Missing required context blocks acceptance or execution with a specific
  reason. Optional missing context is recorded as an explicit assumption.
- A changed base SHA, branch, worktree, authority policy, approval expiry, or
  invalid context receipt invalidates the affected Mission revision before
  further mutation.
- Builder distinguishes implementation, validation, review, identity,
  infrastructure, cancellation, exhaustion, and authority failures.
- Retry is bounded and visible. Infrastructure failure does not silently become
  implementation failure or consume budget unless policy says so.
- Recovery reconstructs from durable Builder records and Git evidence, never
  from a worker's memory or handoff prose.
- Contradictory authorities fail loudly and route back to Kitty/Jacob for
  resolution.

## Independence guarantees

- Kitty remains useful when Builder is unavailable and reports delegated work
  as unknown/unavailable rather than empty.
- Builder runs headless without Kitty UI and keeps execution truth in its
  existing durable stores.
- Kitty and Builder share identifiers and versioned contracts, not database
  ownership or implicit mutable state.
- Orca and model providers remain adapters. Their loss cannot erase the Mission
  or Builder execution state.
- A clean replacement model can resume from repository authorities, a context
  receipt, the Mission, and Builder evidence without private session memory.
- The system favors agency: teach-back and user control remain available, and
  proactivity is gated by relevance and permission.

## Why the prior read-only constraint is superseded

The old constraint correctly protected personal stores and prevented direct
cross-database coupling. It incorrectly prohibited the governed command needed
for delegation. The replacement preserves storage isolation and independent
failure while allowing one explicit write: submission of a validated,
authorized Mission through a supported Builder interface. Results return
through supported read projections. Direct table access and autonomous
mutation remain prohibited.

## Consequences

- Positive: Jacob has one conversational principal; workers remain fungible;
  context transfer, authority, evidence, and recovery become explicit.
- Positive: cost routing can improve without moving truth into model sessions.
- Cost: Mission schemas and approval/result bridges require versioning and
  acceptance tests before runtime automation is safe.
- Constraint: until that runtime is implemented, Kitty may prepare mission
  artifacts but must not autonomously submit them.
