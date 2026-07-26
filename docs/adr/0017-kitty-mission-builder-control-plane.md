# ADR 0017: Kitty → Mission → KittyBuilder Control-Plane Boundary

- **Status:** Accepted; amended 2026-07-26
- **Date:** 2026-07-17
- **Decision owner:** Jacob
- **Supersedes:** the no-write/read-only Builder integration claim in the prior
  blueprint
- **Amended by:** ADR 0020 for planning ownership; ADR 0021 for proactive
  execution

## Context

Kitty contains the conversational product, durable personal stores, model
routing, tools, and a governed Builder with queues, initiatives, attempts,
leases, isolated worktrees, validation, recovery, review, and publication
rails. A permanent separate project-manager agent would split intent,
authority, and continuity across runtimes.

The durable boundary is therefore a versioned Mission between the principal
product agent and the existing execution control plane.

## Decision

The accepted flow is:

```text
Jacob ↔ Kitty → approved Mission and authored packets → KittyBuilder
  → verified Result/Evidence → Kitty ↔ Jacob
```

Kitty is the principal agent and intent compiler. KittyBuilder is the execution
control plane. A Mission is their durable command boundary.

### Kitty and planning responsibilities

Kitty, Jacob, or an explicitly assigned strong-model planning session:

1. maintains the conversation and user-facing project model;
2. retrieves relevant context and records missing, stale, or contradictory
   context explicitly;
3. challenges material assumptions and distinguishes facts from proposals;
4. defines the desired outcome, constraints, risks, non-goals, acceptance
   evidence, and unresolved decisions;
5. owns architecture judgment, priorities, initiative decomposition, and packet
   authoring under ADR 0020;
6. classifies packets for free, paid-author, paid-exec, or human handling; and
7. surfaces only relevant outcomes, blockers, and authorization requests.

Kitty does not own Builder task/run truth and must not infer it from chat,
handoffs, logs, or worker claims.

### KittyBuilder responsibilities

KittyBuilder:

1. validates and durably records accepted Missions, initiatives, packets, and
   policy versions;
2. rejects malformed, impossible, unauthorized, or unverifiable contracts;
3. selects the next eligible approved packet under ADR 0021;
4. selects replaceable workers/models and packages minimum sufficient context;
5. enforces allowed paths, authority, attempts, leases, isolation, timeouts,
   provider policy, and stopping rules;
6. records execution, validation, independent review, recovery, publication,
   and cost when known;
7. continues unrelated eligible work after a packet failure; and
8. returns structured result/evidence references rather than narrative claims
   of completion.

Builder does not invent the roadmap, make unresolved architecture decisions,
own personal stores, or permit a worker to approve its own work.

## Mission object

A versioned Mission contains:

```text
Mission
  identity and origin
    schema_version, mission_id, revision, repository, base_sha,
    conversation/project references, context receipt
  objective
    outcome, rationale, non_goals
  context
    selected references, missing facts, contradictions, assumptions
  execution
    approved initiatives, packets, dependencies, allowed paths,
    forbidden operations, routing and model classes
  authority
    risk tier, approvals, policy version, expiry
  resources
    attempt limits, per-attempt timeouts, concurrency and provider budgets
  evidence plan
    acceptance criteria, validation commands, required artifacts,
    independent review and merge policy
  state
    proposed | awaiting_approval | approved | accepted | running |
    blocked | succeeded | failed | cancelled | superseded
```

References point to owning stores; the Mission does not copy whole
conversations, repositories, Builder rows, secrets, or personal data. A
material objective, scope, authority, evidence, or base change creates a new
revision and may require re-approval.

## Authorization boundaries

- Read-only inspection, diagnosis, drafting, and Mission preparation may occur
  without mutation authority.
- Approval of a Mission authorizes only its stated scope and policy.
- Builder-owned branch push, PR transitions, and low-risk evidence-gated merge
  follow ADRs 0018 and 0021.
- Secrets, auth, external messages, real-money spending, destructive data
  changes, and material scope expansion remain explicit Jacob gates.
- Access, retrieval, monitoring, memory, action, publication, and merge
  permissions are evaluated separately.

## Cost and model routing

Workers are replaceable. Routing starts with the cheapest approved route that
can satisfy the packet's capability and risk constraints. Paid use is explicit,
never an accidental fallback. A model name, price, exit code, PR URL, or worker
assertion is not evidence of completion.

## Result and evidence flow

Builder returns a versioned result linked to the Mission revision, exact base
and result SHAs, attempts, worker receipts, changed paths, validation results,
review verdict, artifacts, costs when known, and publication state. Kitty
communicates the verified outcome, limitations, failures, and decisions still
needed. Working detail remains in durable evidence rather than chat.

## Failure and recovery

- Missing required context, authority, or runnable evidence blocks execution or
  acceptance with a specific next action.
- Builder distinguishes infrastructure, implementation, validation, review,
  identity, cancellation, exhaustion, authority, and provider-availability
  failures.
- Provider exhaustion and rate limits produce a resumable pause rather than
  lost work or fabricated failure.
- Recovery reconstructs from durable Builder and Git evidence, never worker
  memory or handoff prose.
- Contradictory authorities fail loudly and return to Kitty/Jacob.

## Independence guarantees

Kitty remains useful when Builder is unavailable. Builder runs headless and
keeps execution truth in its existing durable stores. Kitty and Builder share
versioned identifiers and interfaces, not database ownership. Orca and model
providers remain adapters whose loss cannot erase durable work.

## Consequences

- Jacob has one conversational principal.
- Planning judgment remains above Builder; execution workers remain bounded and
  fungible.
- Cost routing can change without moving truth into model sessions.
- Mission, packet, result, and recovery contracts require versioned acceptance
  tests before new autonomy is considered trustworthy.
