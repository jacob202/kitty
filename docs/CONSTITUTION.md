# Kitty Constitution v1

**Ratified:** 2026-08-05
**Amended:** 2026-08-23 — ADR 0039 native product-surface authority incorporated explicitly
**Authority:** Highest-level design artifact. Every future Builder packet, ADR,
roadmap, feature, worker, reviewer, and planner must justify itself against this
document before it is accepted. No other document may contradict it.

---

## Preamble

Kitty is a local-first personal AI companion with one canonical native product
surface and replaceable commodity clients/adapters around it. It assembles
personal context, maintains honest runtime awareness, delegates governed work to
replaceable specialist agents, and demands evidence for every claim. It never
fabricates success, never masks failure, and never confuses unavailable with
unknown.

---

## Article I — The Architecture

Kitty is composed of four permanent subsystems with one owner each.

### I.1 — Gateway: The Intelligence Layer

The Gateway is the permanent product owner and single authority over Kitty's
behavior. It owns the truth about what is available, what is happening, what was
produced, and what evidence proves the result. Every client is a thin view over
the Gateway's query and command API.

The Gateway owns:
- Runtime truth (the Capability Manifest).
- Model routing and provider policy.
- Personal context, memory policy, and knowledge retrieval.
- Tool execution, tool constraints, and approval boundaries.
- Project ontology and durable work identity.

The Gateway never owns:
- Worker execution mechanics (leases, queues, worktree isolation).
- Generic provider abstraction (LiteLLM).
- Frontend presentation/rendering mechanics.

### I.2 — Native Kitty Frontend: The Canonical Product Surface

The native Kitty frontend under `gateway/kitty-chat/` is the canonical
user-facing product surface. It renders Gateway-owned truth and provides the
coherent Home/Chat, Projects, Image Lab, Work/evidence, and Settings experience.
It does not own routing, memory, policy, provider truth, or Builder execution.

Open WebUI remains optional commodity/reference software behind stable Gateway
contracts. It may be used for compatibility or comparison, but it is not the
product shell Kitty should design around and never becomes a second authority.

### I.3 — Builder: The Execution Coordinator

Builder is the governed execution engine. It is a coordinator of replaceable
specialist agents, not a coding agent. It receives approved intent, decomposes
into bounded packets, leases workers with isolated worktrees, and returns
structured results with evidence. It never owns product intent, never fabricates
a result, and never grants itself authority beyond its approved packet's scope.
Workers are replaceable and never own project truth.

### I.4 — LiteLLM: The Provider Abstraction

LiteLLM brokers model requests between the Gateway and upstream providers. It
handles streaming, rate limiting, fallback, and model aliasing. It is a
commodity proxy and may be replaced by any equivalent provider abstraction. It
does not own routing policy, model selection, or tool approval.

### I.5 — The Console

The Kitty Console is the operator surface: configuration, Builder state,
diagnostics, and approvals. It is a thin view over the Gateway's query and
command API. It is not a competing chat engine and does not manufacture
capability or success.

### I.6 — Ownership Boundaries

Every subsystem has exactly one owner. No two subsystems compete for the same
truth. There is no general event bus, no distributed worker system, no second
state machine, and no universal mega-table.

| Concern | Owner | Consumer (read-only) |
|---|---|---|
| Runtime truth | Gateway | All clients, shell, console, Builder |
| Product state and identity | Gateway | Home, Brief, Chat, Work, Notifications |
| Evidence and receipts | Gateway | Every surface, every claim |
| Approval policy | Gateway | Builder, shell, chat |
| Memory policy | Gateway | Context assembly, shell |
| Provider abstraction | LiteLLM | Gateway |
| Canonical product presentation | Native Kitty frontend (`gateway/kitty-chat`) | User |
| Governed execution | Builder | Gateway, native Work/evidence surfaces |
| Storage implementation | Gateway | All subsystems (through adapters) |

---

## Article II — Architecture Principles

### II.1 — One Owner Per Responsibility

Every fact — runtime truth, product state, execution state, memory policy,
model availability, tool availability, connection health — has exactly one
named owner. When two subsystems appear to own the same fact, the architecture
is broken and must be corrected before adding features.

### II.2 — Clients Are Thin Views

No client — web console, shell, Raycast, Telegram, Siri — owns product logic,
infers capability, fabricates model identity, or decides what is true. Every
client reads Gateway truth and renders it. A client that does otherwise is a
bug, not a feature.

### II.3 — Replaceable Shells, Replaceable Workers

The shell is replaceable. The workers are replaceable. The provider abstraction
is replaceable. Only the Gateway's intelligence — routing, memory policy,
context assembly, evidence rules, project ontology — is Kitty. Every replaceable
component integrates through stable, versioned Gateway contracts and may be
swapped without migrating Kitty's state or logic.

### II.4 — Local-First, Single-Machine

Kitty runs on one machine. It does not require a distributed system, a cloud
service, or a multi-node deployment. Any external service (providers, RunPod)
is accessed through explicit, bounded, paid, approved Gateway outbound calls.

### II.5 — Authoritative vs. Derived

SQLite is authoritative for application-owned state. Derived indexes (vectors,
embeddings, caches, summaries) accelerate retrieval but never author truth. A
derived index that disagrees with the authoritative store is wrong, and the
system must surface the mismatch rather than silently preferring the faster
path.

### II.6 — Additive Migration, Evidence Before Removal

Never destroy data or tables during a migration. Add new schemas alongside old,
backfill stable IDs, shadow-read old and new paths, and retire old paths only
after parity evidence and a documented rollback window. This applies to storage,
to APIs, to configuration, and to product surfaces.

---

## Article III — Product Principles

### III.1 — The Resume Loop

The primary product is the Resume Loop: open Kitty into the last active state,
see verified changes, current work, and the next best action, then resume
exactly where you left off. Chat persists. Work persists. Attachments persist.
Context persists. Every surface — Home, Chat, Work, Brief — serves this loop.

### III.2 — Home Is the Primary Surface

Home is not a dashboard. It is the first thing you see. It shows what changed,
what needs attention, what is active, and what to do next. Every item links to
its evidence. A missing source produces an explicit incomplete marker, not
invented content.

### III.3 — Chat Is a Command Surface

Chat is a durable work surface, not merely a streaming transport. Messages
persist before dispatch. Attempts record their actual model, location, cost,
and outcome. Interruptions are preserved, not lost. Retries are new attempts,
never silent overwrites. Attachments become durable artifacts with ingestion
receipts before the assistant may claim understanding.

### III.4 — Evidence Before Claims

Kitty may claim success only when a verified execution receipt exists with the
evidence required for that action kind. There is no "best effort" claim.
Failures stay failures. Stale state stays stale. Unknown stays unknown. No
amount of user-facing polish may substitute for absent evidence.

### III.5 — Honest State

Five distinct capability states: `available`, `unavailable`, `degraded`,
`stale`, `unknown`. Every dynamic value carries its state, observed time,
expiry, source subsystem, and evidence reference. A failed probe is not
`unavailable`. `unknown` is never rendered as a default. `$0` is never
displayed when cost data is absent.

### III.6 — Product Language

User-facing surfaces use `Work`, `Plan`, `Run`, `Needs approval`, `Local`,
`Cloud`, `Connected`, and `Evidence`. Implementation terms — queue, lease,
packet, MCP, manifest revision — are reserved for advanced diagnostics and
never exposed in normal operation.

---

## Article IV — Engineering Principles

### IV.1 — Fail Loud, Never Mask

Every error must surface with a clear cause. Never swallow exceptions, return
fake defaults, convert unavailable evidence into zero, or add silent fallbacks.
External calls may retry with a visible warning, then must raise the real
error with useful context. This is the prime directive.

### IV.2 — Adopt Before Build

When a mature open-source project provides a generic infrastructure concern
without requiring Kitty to surrender authority over product decisions, adopt it
as a dependency or replaceable shell. Build custom code only when the
capability is Kitty's unique product differentiation and no mature alternative
exists. A candidate is disqualified if adopting it creates two competing sources
of truth for the same concern.

### IV.3 — Small Packets, One Execution Owner

Every change is a small, independently publishable packet with a single
execution owner. No two lanes work on the same change. A packet that touches
more than one subsystem in a single PR is probably two packets.

### IV.4 — The Gate Decides

For autonomous packets, acceptance must be decidable by exit code. Every packet
declares validation commands that exit 0 only when the work is correct. A gate
that passes on the unmodified tree is worse than no gate. New behavior ships
with the test that proves it.

### IV.5 — Leave the Repo Working

After every change, every milestone, and every packet merge, the repository
builds, the tests pass, and the daily driver starts. A broken main branch is
the highest-severity incident. Never merge work that leaves technical debt to
be "resolved later" — if it can't ship green, it doesn't ship.

### IV.6 — Simplify, Never Duplicate

Every new feature, store, or abstraction must remove equivalent complexity from
somewhere else. Two code paths that do the same thing are a defect. Two stores
that hold the same fact are a defect. Two UIs that render the same state are a
defect. Simplification means removal, consolidation, or retirement — never
adding a parallel path next to the old one.

---

## Article V — Trust Principles

### V.1 — Execution Receipts

Every operation that causes work returns or resolves to an execution receipt
carrying the operation identity, action kind, executor, status, timing,
manifest revision, policy decision, evidence references, output artifacts, and
any error with a clear cause. An operation without a receipt is an operation
Kitty cannot claim it performed.

### V.2 — Approval by Class, Not by Judgment

Every proposed action is classified: act automatically, act and notify, request
approval, or refuse. Repository and user policy can make a default stricter.
The model cannot make it looser. Approvals are scoped, expiring, and recorded.
Approval of one push does not grant permanent push authority.

### V.3 — Write Boundaries Are Explicit

Builder is read-only from the chat shell unless separately authorized. The
shell may inspect bounded Builder projections. It does not create, approve,
publish, or merge work without an explicit operator decision. Any write
boundary crossing requires an approval record that survives restart.

### V.4 — No Ambient Authority

Secrets, credentials, API keys, and payment tokens live in explicit, versioned,
access-controlled configuration. They are never stored in code, logs, worker
output, or the shell's database. The shell process receives only the
environment required to operate. Any inherited environment that could shadow,
leak, or override intentional configuration is stripped before execution.

### V.5 — Honest Failure Beats Partial Success

A worker that cannot complete a packet correctly must report failure with
preserved partial evidence. A worker that fabricates completion when it is
unsure causes more damage than one that stops honestly. Partial work is
preserved for inspection but never accepted as complete.

---

## Article VI — Builder Principles

### VI.1 — Coordinator, Not Coder

Builder is a coordinator of replaceable specialist agents. It selects eligible
packets, leases workers with isolated worktrees, provides bounded context
bundles, validates deterministic checks, obtains independent review, and records
evidence. It never performs the specialist work itself, never judges without
evidence, and never claims a worker's output as its own judgment.

### VI.2 — Execution State Belongs to Builder

Builder owns initiative, packet, task, attempt, lease, run, review, recovery,
budget, and publication state. The Gateway and chat shell read these through
bounded, non-mutating projections. No other subsystem may join Builder's tables
into its own state machine or infer execution conclusions from partial
observations.

### VI.3 — Product Intent Belongs to Kitty

The Gateway — driven by the user through Chat, Work, and the Console — owns
Mission, acceptance criteria, allowed paths, forbidden operations, and approval
boundaries. Builder executes the Mission exactly as authorized. Builder never
reinterprets intent, expands scope, weakens gates, or grants itself authority
beyond the approved packet.

### VI.4 — Deterministic Validation, Independent Review

No packet completes on worker assertion or exit code alone. Completion requires
declared deterministic validation checks (exit 0 gates) plus an independent
review outcome. The worker that executes the change is never the reviewer that
accepts it. A validation gate that passes on empty work is rejected as false
evidence.

### VI.5 — Budgeted, Scoped, Recoverable

Every packet carries an attempt budget, allowed paths, forbidden operations,
and acceptance criteria. Exhaustion, stale leases, worker crashes, and provider
failures are handled through durable recovery: the packet's state is preserved,
the failure reason is recorded, and the block is explicit — never a silent
abandon or a fabricated fallback outcome.

---

## Article VII — The Policies

### VII.1 — Adoption Policy ("Buy Before Build")

When evaluating any new infrastructure capability:

1. Can mature open-source software provide it without surrendering Kitty's
   product authority (routing, memory policy, context assembly, personality,
   project ontology, evidence rules)?
2. If yes, adopt it as a replaceable dependency or shell. Integrate through
   stable Gateway contracts.
3. If no — the capability is Kitty's unique differentiation — build it inside
   the Gateway.
4. A candidate is disqualified if adopting it creates two competing sources of
   truth.

### VII.2 — Replacement Policy

Any replaceable component — shell, provider proxy, worker, vector store — may
be swapped when:

1. The replacement integrates through the same stable Gateway contracts.
2. Kitty's state, logic, and product identity remain unchanged.
3. A regression suite proves the replacement meets or exceeds the current
   component's behavior.
4. A documented rollback path restores the previous component within one
   command.

The Gateway is not replaceable. It is the product.

### VII.3 — Deletion Policy

Nothing is deleted without evidence that it is safe to delete:

1. Add the replacement alongside the existing implementation.
2. Shadow-read both paths and reconcile discrepancies.
3. Cut over one journey at a time, with a documented rollback per phase.
4. Retire the old path only after counts, hashes, journey checks, restart
   recovery, and a soak period confirm parity.
5. Delete the code, not just deprecate it. Dead code left in the repository
   is a maintenance liability.

### VII.4 — Complexity Budget

Kitty's complexity budget is fixed. Every addition must be offset by a removal
of equivalent weight:

- Adding a new store → retiring an old store.
- Adding a new module → removing a redundant or shallow module.
- Adding a new feature lane → removing the code it replaces.
- Adding a new abstraction → removing the direct path it supersedes.

Two code paths that do the same thing always count against the budget
regardless of whether one is "legacy" or "temporary." The budget is monitored
by counting modules, stores, UI surfaces, and redundant code paths. The
direction is always down.

### VII.5 — Amendment Policy

This Constitution may be amended by an Architectural Decision Record (ADR) that:

1. Cites the specific Article and Section it amends.
2. Demonstrates that the amendment does not create contradictory rules.
3. Records the evidence that necessitated the change.

A Constitution amendment is the highest-severity architectural decision. It
should be rare, explicit, and backward-compatible with existing rules unless
the amendment explicitly supersedes them.

---

## Ratification

This Constitution consolidates the architectural principles discovered across
the following ratified authorities:

| Source | Principle |
|---|---|
| ADR 0003 | Gateway is the product; clients are thin views |
| ADR 0017 | Builder owns execution; Kitty owns intent |
| ADR 0027, 0033 | Open WebUI compatibility and environment-isolation boundaries |
| ADR 0039 | Native Kitty frontend is the canonical product surface |
| ADR 0028 | Adopt before build |
| ADR 0029 | Capability Manifest is single source of runtime truth |
| ADR 0032 | Evidence-backed claims; no fabricated success |
| ADR 0034 | Memory policy is Kitty; storage implementation is replaceable |
| ADR 0036 | Builder infrastructure preserved, refactored for extraction readiness |
| Product Architecture (2026-07-10) | Four spines, honest state, approval classes, execution receipts |
| Architecture Honesty Audit (2026-07-24) | Fail-loud, honest state, no silent fallbacks |
| Free-Model Packet Standard | Gate decides, honest failure beats partial success |
| ROADMAP_V2 (2026-08-05) | Small packets, one owner, leave repo working |

These sources remain the detailed authority for their specific domains. This
Constitution is the unified statement of principles they collectively express.

All future work in this repository is governed by this document.
