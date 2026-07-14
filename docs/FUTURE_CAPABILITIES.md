# Kitty Future Capability Horizons

**Status:** product direction, not an implementation claim  
**Date:** 2026-07-14  
**Relationship:** extends `KITTY_PRODUCT_ARCHITECTURE.md` and Packet 028 without expanding Packet 028 V1

## Purpose

Kitty should not become a busier chatbot. It should become a trustworthy, continuous operating layer for a person's work and life: aware of what is true, able to resume meaningful work, deliberate about how it reasons and acts, and honest about what it used and what happened.

This document records the capabilities that can take Kitty several levels beyond a conventional assistant. They are future product horizons, not permission to build a giant framework or to bundle them into one PR.

For the detailed product principle that Kitty should feel like an unfair advantage, the first-class KittyBuilder tab, and the full model-harness efficiency roadmap, see `UNFAIR_ADVANTAGE_AND_HARNESS.md`.

## Product rules for all future capabilities

1. **Progressive disclosure.** Powerful information must be available without crowding every response or screen.
2. **Truth before theatre.** Never invent capability, certainty, completion, cost, memory use, or reasoning visibility.
3. **One connected product.** New features must extend the shared runtime-truth, product-state, artifact/evidence, and governed-execution spines.
4. **User outcomes over internal machinery.** Ordinary UI uses human language; provider IDs, traces, policies, and raw diagnostics live behind expansion or advanced views.
5. **No hidden autonomy.** Kitty may act proactively only inside explicit boundaries, with durable evidence and understandable stop conditions.
6. **Small vertical slices.** Each capability must ship as a complete, testable user journey rather than as a speculative platform layer.

---

## 1. Reasoning Policy Engine

### Product promise

The user chooses the kind of outcome they need; Kitty selects a bounded way to produce it.

### User-facing modes

- **Fast:** minimize latency and cost; no optional research or escalation.
- **Balanced:** normal quality, bounded verification, and moderate context.
- **Deep:** larger reasoning and verification budgets for genuinely difficult work.
- **Auto:** Kitty selects Fast, Balanced, or Deep from deterministic task signals and explains the selection in the receipt.

Model-native reasoning effort (`off | normal | deep`) is a subordinate capability, not the product mode itself. A mode can also govern tools, research depth, verification, memory budget, latency, cost, and escalation.

### Required contracts

- `ReasoningPolicy`: selected mode, task class, strategy, model tier, memory budget, tool policy, verification policy, privacy boundary, latency/token/cost limits, fallback and escalation rules.
- `ExecutionReceipt`: requested and resolved policy, models and tools used, evidence and memory references, verification performed, fallbacks, budget consumed, warnings, outcome.

### UI principle

Reasoning controls and receipts are **available but quiet**:

- a compact mode control near the composer;
- a small post-response status line or icon;
- full policy and receipt details only on expansion;
- no permanent wall of technical metadata under every answer.

Provider-exposed reasoning summaries or reasoning content may appear in a separate collapsed section. Kitty must never promise or reconstruct hidden chain-of-thought.

### Success criteria

- trivial prompts stay cheap and fast;
- current or high-stakes claims trigger appropriate verification;
- private requests cannot bypass privacy policy;
- policy choices are deterministic enough to test;
- budgets are enforced in code;
- every fallback and degradation is visible in the receipt.

---

## 2. Execution Receipts

### Product promise

Kitty can prove what it did without forcing the user to read internal machinery.

### Receipt contents

A receipt may include:

- selected execution mode and strategy;
- requested and resolved model/provider/location;
- tools invoked and their results;
- memories or artifacts used, by reference;
- sources and verification level;
- approvals requested or consumed;
- fallback and retry path;
- latency, token use, and estimated cost;
- confidence or quality warnings;
- final outcome and resulting artifacts.

### Presentation

Receipts should not automatically expand beneath every answer. Default presentation:

- one subtle status row such as `balanced · 2 sources · verified`;
- click/tap to open a structured receipt;
- advanced mode may show provider, token, latency, and policy details;
- failed or degraded runs expand enough to explain what went wrong.

### Why it matters

Receipts unify trust across chat, tools, research, Builder, Image Lab, background jobs, and proactive actions. They also become the durable evidence used by Home, the operational timeline, decisions, and later evaluation.

---

## 3. Home as an Operating Surface

### Product promise

Opening Kitty should answer within five seconds:

- What changed?
- What needs me?
- What was I doing?
- What is blocked or at risk?
- What should I do next?

### Design direction

This succeeds or fails on presentation. It should not become a dense enterprise dashboard.

Use a calm, hierarchical bento board:

- one dominant `Continue` or `What's next` card;
- a small `Needs you` area for approvals, failures, deadlines, and uncertainty;
- `What changed` as a concise verified activity digest;
- active work and long-running execution only when relevant;
- recent artifacts and useful captures, not a feed of everything;
- health/cost/system details collapsed unless degraded.

The home view is a projection over shared product state. It must not invent its own truth or duplicate domain stores.

---

## 4. Truth Layer

### Product promise

Kitty distinguishes what is known from what is guessed.

### Truth states

Information and claims may carry:

- `verified` — supported by current evidence;
- `user_provided` — stated by the user but not independently verified;
- `inferred` — reasoned from evidence, with the inference named;
- `assumed` — temporary premise required to proceed;
- `stale` — once known, but freshness has expired;
- `unknown` — Kitty could not establish the truth;
- `model_generated` — generated content, not an observed fact.

### Presentation

Do not decorate every sentence. Use:

- visible labels where stakes or ambiguity matter;
- source/evidence expansion for important claims;
- clear stale/degraded states;
- receipt-level summaries for ordinary work;
- stronger warnings before irreversible actions.

### Architectural role

The Truth Layer is metadata and enforcement across runtime truth, artifacts, memories, decisions, activities, and receipts. It is not a second database of duplicated facts.

---

## 5. Capability Manifest

### Product promise

Kitty always knows what it can actually do right now.

### Scope

The manifest should include:

- app/version/time/timezone;
- active project, repository, branch, and working-tree state;
- models, providers, execution location, and health;
- tools and approval requirements;
- memory status and freshness;
- Builder queue/runs/initiatives;
- Image Lab engines and queues;
- connected email, calendar, GitHub, browser, and files;
- degraded, stale, unavailable, and unknown states with evidence.

### UI

Ordinary UI uses compact language such as:

- `Kitty Auto · cloud`
- `local tools connected`
- `Builder paused — approval needed`

The full manifest belongs in diagnostics and receipts, not in every conversation.

---

## 6. Continuations

### Product promise

Kitty should feel like returning to ongoing work, not searching through old chats.

### Continuation object

A continuation captures:

- the project or life context;
- the last meaningful completed step;
- unresolved decisions and blockers;
- active runs and artifacts;
- the next suggested action;
- confidence and freshness;
- links back to source conversations, files, events, and receipts.

### Surfaces

- Home: one dominant `Continue` card.
- Chat: `continue this` and `continue yesterday's work` commands.
- Notifications: resume after an external event or completed run.
- Project view: canonical resume point per project.

### Guardrail

A continuation is generated from durable product state and evidence. It must not hallucinate progress from conversational tone or claim that work finished without a successful receipt.

---

## 7. Everything Becomes a Connected Object

### Product promise

Chats stop being isolated transcripts. Kitty understands durable relationships among work.

### Core object types

- projects;
- goals;
- people;
- conversations and turns;
- work items and initiatives;
- runs;
- decisions;
- ideas;
- research;
- artifacts and documents;
- images;
- memories;
- events and notifications.

### What this enables

- ask `what is connected to this?`;
- resume a project from any related artifact or conversation;
- see which decision created a task;
- trace an answer to the research and memories it used;
- understand that a Builder PR, a chat request, and a resulting artifact are one chain of work.

### Guardrail

Use typed relationships and stable IDs over existing domain stores. Do not create a universal mega-table or force every domain into one schema.

---

## 8. Operational Timeline

### Product promise

One coherent history of meaningful activity across Kitty.

### Timeline entries

- user decisions and approvals;
- chat turns that created durable work;
- tool and Builder runs;
- GitHub changes;
- research and source updates;
- artifact creation and modification;
- memory creation, correction, and deletion;
- email/calendar events when relevant;
- image generation runs;
- failures, interruptions, and recoveries.

### Interaction

- filter by project, object, actor, or event type;
- collapse low-value technical chatter;
- expand an event into its receipt, artifacts, and source links;
- resume from any interrupted or meaningful event;
- show only verified events as completed actions.

The timeline should feel like an intelligible work history, not a raw log viewer.

---

## 9. Memory Transparency and Control

### Product promise

Memory is useful because the user can see, correct, and govern it.

### Response-level presentation

A collapsed `Kitty remembered` section may show the specific memory items that materially influenced the response. It must not dump every retrieved item or reveal sensitive information unnecessarily.

### Controls

- keep;
- edit;
- forget;
- correct;
- explain why this surfaced;
- mark as sensitive or project-scoped;
- inspect source and freshness.

### Architecture

Memory visibility consumes the same references recorded in the execution receipt. Correction updates the authoritative source and invalidates/rebuilds derived indexes. It must not silently edit a rendered response without changing the underlying record.

---

## 10. Visible Builder

### Product promise

Builder becomes understandable without requiring terminal archaeology.

### User-visible state

- initiatives and packet dependencies;
- current and queued work;
- worker/model/provider;
- isolated branch/worktree;
- files changed;
- validations and independent review;
- run timeline and logs;
- blocked reason;
- retries, recovery, pause, cancel, and takeover;
- PR and merge state;
- final artifacts and receipt.

### Presentation

Default to a simple task-centre view. Raw logs, hashes, leases, and runner internals live behind expansion. The user should see what is happening, what needs them, and whether the result is trustworthy.

---

# Larger Differentiating Ideas

## 11. Reasoning Profiles

### Idea

Kitty learns how the user prefers different classes of problems handled, while keeping every policy choice inspectable and reversible.

A profile is not a personality prompt. It is a set of bounded preferences such as:

- favor concise answers for routine questions;
- require source verification for medical, legal, financial, or current claims;
- prefer local execution for private content;
- use deeper comparison before purchases or major decisions;
- draft first rather than ask unnecessary follow-up questions;
- prefer diagrams, tables, or stepwise plans in certain domains;
- cost and latency tolerance by task type.

### Learning model

Kitty may propose profile updates from repeated explicit choices or outcome data, but the user approves durable changes. Avoid opaque reinforcement from every click or emotional reaction.

### Receipt integration

Receipts name when a profile preference changed the selected policy. The user can temporarily override or disable a profile.

---

## 12. Decision Journal

### Idea

Major choices become durable decisions with context, alternatives, evidence, assumptions, and later outcomes.

### Decision record

- question and stakes;
- chosen option;
- alternatives considered;
- evidence and assumptions;
- predicted outcome;
- confidence and unresolved risks;
- review date or trigger;
- actual outcome and lesson.

### Why it matters

Kitty can later answer:

- `Why did we choose this?`
- `What assumptions turned out wrong?`
- `Are we repeating a failed pattern?`
- `Which recommendations have actually worked?`

This creates real learning from outcomes rather than merely accumulating memories.

---

## 13. World Model

### Idea

A living, typed graph of the user's relevant world: people, projects, commitments, places, organizations, documents, goals, constraints, and events.

### Boundary

The World Model is not an omniscient psychological profile. It contains explicit, sourced relationships and uncertainty. Sensitive inferences require stronger controls and should not silently become durable facts.

### Capabilities

- connect a person to conversations, commitments, and projects;
- understand that a deadline affects finances, travel, and a project;
- detect conflicts among plans and constraints;
- surface relevant context without loading unrelated history;
- create better continuations and proactive warnings.

### Architecture

Build on the canonical product entities and typed references. Use derived graph/search indexes for retrieval, but preserve SQLite records and source provenance as authoritative.

---

## 14. Simulation Mode

### Idea

Before a consequential decision, Kitty can compare bounded strategies rather than emit one confident answer.

### Example strategies

- fastest;
- cheapest;
- safest;
- highest-confidence;
- least disruptive;
- most reversible;
- best long-term outcome.

### Output

Simulation Mode produces:

- shared assumptions;
- strategy-specific plans;
- likely benefits and failure modes;
- resource and time requirements;
- reversible first steps;
- uncertainty and missing information;
- a recommendation with rationale.

### Guardrails

This is structured scenario analysis, not prediction theatre. Kitty must label assumptions and uncertainty, avoid fake numerical precision, and never present simulations as guaranteed outcomes.

---

## 15. Self-Evaluation and Routing Improvement

### Idea

Kitty learns which policies and routes work by measuring outcomes, not by secretly rewriting itself.

### Evaluation signals

- correctness against verified answers or later evidence;
- task completion and artifact acceptance;
- user correction or rejection;
- latency, token, and cost performance;
- fallback and failure frequency;
- citation and verification quality;
- whether the user resumed, abandoned, or redid the work.

### Evaluation loop

1. Store an immutable execution receipt.
2. Attach explicit or observed outcome signals.
3. Run offline evaluations over comparable task classes.
4. Propose routing or policy changes.
5. Validate them against benchmark and safety gates.
6. Promote only reviewed policy versions.

No live self-modifying prompts or silent policy drift.

---

## 16. Proactive Opportunity and Risk Detection

### Idea

Kitty should notice meaningful changes without becoming noisy or paternalistic.

### Examples

- a deadline approaching with no completed prerequisite;
- a Builder run blocked on approval;
- a job opening matching an active goal;
- an email that changes a plan;
- a recurring expense or benefit deadline;
- contradictory commitments across calendar and project state;
- a stale decision whose assumptions changed.

### Notification policy

Notify only when the event is actionable, sufficiently fresh, and materially relevant. Every proactive card includes why it appeared, the evidence, confidence, and a direct action or dismissal path.

---

## 17. Multi-Strategy Collaboration

### Idea

For difficult work, Kitty can coordinate specialized reasoning strategies without exposing a confusing swarm of agents.

Possible roles:

- researcher;
- critic;
- planner;
- verifier;
- domain specialist;
- synthesizer.

The user sees one coherent result and an optional receipt showing which strategies participated. Council remains the decomposition/supervision mechanism; the Reasoning Policy Engine decides when collaboration is justified and bounded.

---

## 18. Personal Automation Studio

### Idea

Turn repeated successful work into understandable, reusable automations.

A user can promote a completed sequence into a template with:

- trigger;
- required context;
- steps and tools;
- approval boundaries;
- budgets and stop conditions;
- expected artifacts;
- verification and notification rules.

Automations remain inspectable objects with versioned policies and receipts. Kitty should recommend automation only after a pattern has repeated and the user approves it.

---

# Recommended sequencing

## Horizon 1 — Trust and continuity foundation

1. Capability Manifest
2. Connected product objects and activity envelope
3. Continuations and resume projections
4. Execution Receipts
5. Operational Timeline foundation

These capabilities make the rest truthful and connected.

## Horizon 2 — Deliberate intelligence

1. Reasoning Policy Engine V1
2. Memory transparency
3. Truth Layer presentation
4. Decision Journal
5. Reasoning Profiles with explicit approval

## Horizon 3 — Visible execution

1. Builder task centre
2. unified long-running work centre
3. artifact/evidence navigation
4. Personal Automation Studio
5. proactive opportunity/risk cards

## Horizon 4 — Adaptive and comparative intelligence

1. Simulation Mode
2. World Model expansion
3. Multi-Strategy Collaboration
4. offline Self-Evaluation and routing optimization

## Build-order rule

Do not build Horizon 4 as a platform project. Each capability advances only when a smaller user journey proves the underlying contracts and produces measurable value.

# Measures of success

Kitty is taking a real step forward when:

- the user can resume meaningful work without searching;
- important status claims have evidence;
- simple tasks remain fast and inexpensive;
- difficult tasks receive deeper, bounded treatment;
- memory use is visible and correctable;
- Builder and background work are understandable;
- major decisions can be revisited with their assumptions and outcomes;
- proactive alerts are rare, relevant, and actionable;
- the product feels calmer as its capability grows, not busier.
