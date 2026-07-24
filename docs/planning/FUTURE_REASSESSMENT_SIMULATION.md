# Simulated Future Reassessment — Six to Nine Months After Shipping

**Status:** product simulation, not observed usage data \
**Date:** 2026-07-14 \
**Purpose:** stress-test Kitty's future roadmap before implementation hardens into product debt

## Scenario

Assume Kitty has shipped meaningful versions of:

- the Reasoning Policy Engine;
- quiet execution receipts;
- Capability Manifest and Truth Layer;
- Continuations and a redesigned Home;
- connected product objects and an Operational Timeline;
- memory transparency;
- a first-class KittyBuilder tab;
- Decision Journal, Reasoning Profiles, Simulation Mode, and proactive cards;
- partial World Model and Personal Automation support;
- the major model-harness improvements described in `UNFAIR_ADVANTAGE_AND_HARNESS.md`.

This document simulates the reassessment six to nine months later. It asks:

1. What became indispensable?
2. What needs tuning?
3. What should merge into a simpler concept?
4. What should be removed?
5. What important capability was missing from the original plan?

The expected answer is not that every planned feature succeeds. A healthy product should become simpler as evidence accumulates.

---

# Executive conclusion

The strongest version of Kitty probably converges around five user-facing ideas:

1. **Continue** — resume the right work without reconstructing context.
2. **Ask** — collaborate with Kitty through chat and direct manipulation.
3. **Build** — delegate durable work through KittyBuilder.
4. **History** — understand what changed, what happened, and why.
5. **Proof** — inspect sources, memory, actions, receipts, and uncertainty when needed.

Most planned capabilities should become infrastructure beneath those ideas rather than separate modes, screens, or brands.

The probable winners are:

- Continuations;
- first-class KittyBuilder;
- context and packet compilation;
- evidence-backed completion;
- Capability Manifest;
- connected objects;
- memory correction;
- a calm, adaptive Home;
- model routing and budget allocation that mostly stays invisible.

The probable overbuild risks are:

- too many user-facing reasoning controls;
- receipts shown too often;
- a separate World Model product surface;
- visible agent-role choreography;
- confidence percentages;
- an advanced automation studio before simple reusable routines are proven;
- a timeline that behaves like a log dump;
- proactive alerts tuned for recall instead of precision.

---

# Simulated product experience after six months

A typical successful day looks like this:

1. Kitty opens to one dominant continuation: `Continue PR #214 — reviewer requested one change`.
2. A small Needs You card shows one approval and one stale deadline, not twelve system notifications.
3. The user asks a question. Kitty silently chooses Balanced, retrieves relevant context, and answers.
4. The answer offers one useful continuation: `Compare options`, `Save decision`, or `Build this`.
5. The user starts a build. KittyBuilder shows the plan, current task, next dependency, and what would require approval.
6. The work runs without babysitting. A failure becomes a clear recovery choice rather than a terminal archaeology session.
7. The result appears with concise proof: tests passed, review passed, PR ready.
8. Technical details remain one tap away.

A typical unsuccessful day looks like this:

1. Home displays too many cards with equal visual weight.
2. Every response shows mode, provider, tokens, cost, memories, sources, and confidence.
3. Kitty asks the user to choose among Fast, Balanced, Deep, reasoning effort, provider, local/cloud, and strategy.
4. The Operational Timeline fills with low-level events.
5. Proactive cards repeatedly surface weakly relevant possibilities.
6. KittyBuilder exposes packets and worktrees before explaining the user outcome.
7. The user spends more time managing the assistant than benefiting from it.

The reassessment should aggressively optimize toward the first experience.

---

# Feature-by-feature reassessment

## 1. Reasoning Policy Engine

### Simulated outcome

The engine is valuable, but users rarely want to manage several reasoning dimensions. **Auto becomes the real default**, while manual control is used only for exceptional requests.

### Fine-tuning required

- Reduce the normal control to `Auto`, `Quick`, and `Thorough`, or keep Fast/Balanced/Deep inside an expandable menu.
- Keep model-native reasoning effort entirely in advanced diagnostics.
- Tune classification around observed failures: unnecessary research, under-verification, expensive escalation, and slow treatment of trivial prompts.
- Add per-domain policies for coding, personal decisions, medical/legal/financial research, creative work, and private/local tasks.
- Add clear temporary overrides such as `be quick`, `verify this`, and `keep this local`.

### Product decision

**Keep the engine; simplify the visible control.** Do not make users understand the policy graph.

---

## 2. Execution Receipts

### Simulated outcome

Receipts are essential for trust but irritating when displayed after every routine answer. Most users inspect them after failures, high-stakes claims, paid actions, or surprising results.

### Fine-tuning required

- Show no receipt row for trivial conversation unless an action, source, memory, cost, or warning matters.
- Show a compact proof row for research, tools, builds, and consequential decisions.
- Auto-expand only for failures, degraded capability, paid escalation, uncertainty, or irreversible effects.
- Present evidence first; provider IDs, hashes, token counts, and policy revisions remain advanced.
- Group multiple tool receipts into one understandable operation receipt.

### Product decision

**Merge receipts into a broader Proof concept.** Proof includes sources, actions, memories, validation, and uncertainty.

---

## 3. Home as an Operating Surface

### Simulated outcome

Home is either the product's strongest surface or its largest source of clutter. Static bento cards age badly; an adaptive hierarchy performs better.

### Fine-tuning required

- Always make one primary continuation dominant.
- Limit Needs You to genuinely blocking or time-sensitive items.
- Hide empty sections completely.
- Collapse low-value change history into one digest.
- Learn which cards the user repeatedly ignores, but require explicit control over permanent layout changes.
- Add Focus states: `Today`, `Project`, and `Recovery/Resume` rather than dozens of card types.
- Let the user act directly from cards without opening several screens.

### Product decision

**Keep Home, but treat it as a dynamic decision surface—not a configurable widget dashboard.**

---

## 4. Truth Layer

### Simulated outcome

The truth metadata is extremely valuable internally. Showing seven truth labels directly in the interface is too much.

### Fine-tuning required

- Collapse visible states into understandable language: `verified`, `from you`, `inferred`, `may be outdated`, and `could not verify`.
- Show truth labels only where ambiguity changes the decision.
- Integrate truth state into citations, memory cards, receipts, and warnings.
- Apply stronger truth requirements to actions and high-stakes recommendations than to brainstorming.

### Product decision

**Keep as infrastructure; merge the UI into Proof.** Do not create a separate Truth screen.

---

## 5. Capability Manifest

### Simulated outcome

The manifest quietly prevents fake success and model confusion. Users do not want to browse the full manifest frequently.

### Fine-tuning required

- Show only material capability changes in normal UI.
- Expose a simple connection/health sheet for troubleshooting.
- Keep the full manifest in advanced diagnostics and receipts.
- Improve freshness and ownership rules; stale health data will become a major source of false confidence.
- Add capability dependency explanations: `Image editing unavailable because Draw Things is offline`.

### Product decision

**Keep completely, but mostly invisible.** This is foundational infrastructure, not a destination.

---

## 6. Continuations

### Simulated outcome

Continuations become one of Kitty's defining advantages. The biggest failures are wrong continuation selection, stale next steps, and too many competing resumptions.

### Fine-tuning required

- Rank by user intent, recency, importance, blocked state, and available next action—not recency alone.
- Distinguish `resume`, `review`, `decide`, and `waiting` continuations.
- Allow pin, snooze, archive, and `not this` feedback.
- Require evidence for claimed completion and next step.
- Generate project-level and global continuations from the same underlying state.
- Preserve the user's exact stopping point, not just a generated summary.

### Product decision

**Double down. Continue should become a primary product verb.**

---

## 7. Connected Objects

### Simulated outcome

Typed relationships power the product, but users rarely want to navigate a literal graph. The value appears through better search, context, continuation, and provenance.

### Fine-tuning required

- Keep the graph implicit in normal use.
- Add relationship views only where useful: `related work`, `used by`, `created from`, `depends on`.
- Improve duplicate detection and object merging.
- Add strong source and deletion semantics.
- Prevent inferred relationships from silently becoming permanent facts.

### Product decision

**Keep as architecture. Do not ship “Everything is an Object” as a user-facing concept.**

---

## 8. Operational Timeline

### Simulated outcome

The timeline is useful during recovery, review, and accountability, but becomes unreadable if it records every internal transition.

### Fine-tuning required

- Rename the normal surface **History**.
- Show meaningful outcomes and state changes, not worker noise.
- Group related events into episodes: one build, one research task, one decision.
- Offer `What changed since I last looked?` as the primary view.
- Preserve a raw event stream only in advanced diagnostics.
- Add strong filters for project, person, build, decision, and failure.

### Product decision

**Merge Operational Timeline, activity feed, receipt history, and change digest into one History system with several projections.**

---

## 9. Memory Transparency and Control

### Simulated outcome

Users value correction and deletion more than seeing every memory used. Constant memory disclosure feels invasive and distracting.

### Fine-tuning required

- Show memory use only when it materially changes the answer or the user asks.
- Prioritize `Why did you remember this?`, `Correct`, and `Forget`.
- Add source, date, project scope, sensitivity, and confidence.
- Add temporary/session memory and durable memory as distinct choices.
- Detect contradictions and ask for resolution instead of stacking conflicting facts.
- Create a periodic memory review rather than persistent memory clutter.

### Product decision

**Keep memory controls; reduce automatic display.** Merge memory evidence into Proof.

---

## 10. KittyBuilder tab

### Simulated outcome

KittyBuilder becomes a major differentiator if it remains outcome-first. It fails if it becomes a prettier terminal dashboard.

### Fine-tuning required

- Make the build objective, current outcome, blocker, and next action more prominent than packet internals.
- Replace misleading percentage progress with phases and completed evidence unless progress is genuinely measurable.
- Add one-click recovery recommendations.
- Let the user amend the plan or add an instruction without restarting safe completed work.
- Add `show me what changed`, `show me the risky parts`, and `compare to objective`.
- Surface cost and model only when they matter or on expansion.
- Separate active work from historical initiatives.
- Add a universal approval inbox shared with other Kitty actions.

### Product decision

**Double down. KittyBuilder should remain a named primary tab.**

---

## 11. Reasoning Profiles

### Simulated outcome

A separate profile editor becomes confusing and underused. The underlying preferences are useful.

### Fine-tuning required

- Store explicit preferences as policy rules, not personality profiles.
- Let Kitty propose a rule after repeated explicit overrides: `Always verify medical questions?`
- Provide a small Preferences and Policies view with examples and undo.
- Keep domain-specific behavior separate from tone/personality.

### Product decision

**Remove Reasoning Profiles as a separate product feature. Merge into Preferences + Policy.**

---

## 12. Decision Journal

### Simulated outcome

The journal is highly valuable for major decisions but too heavy for routine choices. Its value appears months later when outcomes can be compared.

### Fine-tuning required

- Add `Save as decision` rather than requiring a special mode.
- Automatically capture alternatives, assumptions, evidence, and review trigger from the conversation, then let the user edit.
- Prompt for outcome review only when a meaningful trigger or date arrives.
- Link decisions to resulting builds, calendar changes, purchases, or projects.
- Add `what did we learn?` and `which assumption failed?` summaries.

### Product decision

**Keep, but make it an object/action—not a standalone daily destination.**

---

## 13. World Model

### Simulated outcome

A broad “World Model” becomes risky, vague, and difficult to govern. The useful parts are typed relationships, constraints, commitments, and sourced context.

### Fine-tuning required

- Narrow scope to explicit user-relevant entities and relationships.
- Require provenance and confidence for every inferred relationship.
- Separate observed facts, user claims, and model inferences.
- Add expiration and review for time-sensitive relationships.
- Avoid durable psychological interpretation unless explicitly supplied and useful.

### Product decision

**Drop World Model as a user-facing name and standalone initiative. Fold valid pieces into Connected Context.**

---

## 14. Simulation Mode

### Simulated outcome

Simulation is useful for consequential choices but awkward as a global chat mode. Users usually ask to compare options rather than “simulate.”

### Fine-tuning required

- Offer contextual actions: `Compare strategies`, `Stress-test this plan`, `Show best/worst case`, and `Find the most reversible path`.
- Use shared assumptions and explicit uncertainty.
- Avoid numerical forecasts without real data.
- Link the selected strategy into the Decision Journal.

### Product decision

**Remove Simulation as a persistent mode. Merge into Compare and Decision tools.**

---

## 15. Self-Evaluation and Routing Improvement

### Simulated outcome

This is valuable backend machinery but dangerous if optimized against weak proxy metrics or allowed to drift continuously.

### Fine-tuning required

- Separate correctness, usefulness, latency, and cost metrics.
- Prevent optimization for user agreement or superficial acceptance.
- Use frozen benchmark sets plus recent canaries.
- Require reviewed, versioned policy promotions.
- Detect benchmark overfitting and provider/model drift.
- Preserve rollback and side-by-side comparisons.

### Product decision

**Keep entirely as governed infrastructure. No standalone user feature.**

---

## 16. Proactive Opportunity and Risk Detection

### Simulated outcome

This becomes either magical or unbearable. The decisive metric is precision, not number of surfaced opportunities.

### Fine-tuning required

- Default to fewer, higher-confidence cards.
- Require actionability, freshness, materiality, and a clear reason.
- Learn from dismissals by category, not from one-off emotional reactions.
- Separate urgent, useful, and merely interesting.
- Bundle low-priority observations into a digest.
- Add quiet modes and project-specific notification policies.
- Never frame speculative concern as fact.

### Product decision

**Keep, but aggressively tune for silence.** One excellent alert is worth more than twenty plausible ones.

---

## 17. Multi-Strategy Collaboration

### Simulated outcome

Different reasoning roles improve difficult work, but exposing a cast of agents adds theatre and cognitive load.

### Fine-tuning required

- Keep role activation internal.
- Show only a concise statement such as `researched and independently checked` when relevant.
- Measure whether extra roles materially improve the result.
- Collapse roles for routine work to reduce latency and cost.
- Preserve disagreement only when it changes the final recommendation.

### Product decision

**Keep as harness behavior; remove visible agent-swarm presentation.**

---

## 18. Personal Automation Studio

### Simulated outcome

A full visual automation builder arrives too early and feels like programming. Users value saving proven routines, not designing workflows from scratch.

### Fine-tuning required

- Start with `Do this again`, `Save as routine`, and editable templates.
- Generate automations from successful receipts and repeated work.
- Keep triggers, approval boundaries, stop conditions, and outputs understandable.
- Add a simple test-run and preview.
- Expose advanced step editing only after the user needs it.

### Product decision

**Delay or remove the full Automation Studio. Replace V1 with Routines.**

---

# Harness reassessment after six to nine months

## Context compiler

### Likely problem

The compiler retrieves too much code, trusts stale docs, or omits one decisive dependency.

### Tuning

- measure which context items were cited, opened, or used in edits;
- penalize repeated irrelevant retrieval;
- add freshness and authority scoring;
- compare retrieval bundles for successful and failed packets;
- let workers request targeted expansion;
- create subsystem-specific context recipes.

**Keep and invest heavily.** This is one of the largest quality multipliers.

## Packet compiler and linter

### Likely problem

It creates formally complete but overly verbose packets, or splits work so finely that integration becomes expensive.

### Tuning

- optimize for independently verifiable outcomes, not smallest possible diff;
- detect cross-packet integration tax;
- learn common packet templates by task class;
- test whether acceptance criteria predict successful review;
- allow bounded ambiguity where exploration is genuinely necessary.

**Keep; simplify generated packets and improve split decisions.**

## Model capability registry

### Likely problem

Benchmarks become stale as providers update models, and performance varies by repository and prompt shape.

### Tuning

- rolling canaries;
- repository- and task-specific scores;
- confidence intervals rather than a single rank;
- decay old results;
- separate provider outages from model quality;
- evaluate total workflow success, not one response.

**Keep; make it empirical and continuously recalibrated.**

## Adaptive budgets

### Likely problem

Auto either over-escalates and becomes expensive or under-escalates and produces weak results.

### Tuning

- correlate budget increases with accepted quality improvement;
- identify task classes where more reasoning does not help;
- add hard ceilings and one-step escalation;
- distinguish model failure from missing context/tool failure;
- allow user-level cost and latency preferences.

**Keep; expect ongoing calibration forever.**

## Stage-specialized roles

### Likely problem

Too many handoffs increase latency, prompt cost, and inconsistency.

### Tuning

- activate roles only above measured complexity/risk thresholds;
- reuse shared structured state instead of repeating prose;
- collapse planner and implementer for narrow tasks;
- require a separate reviewer only when the consequence justifies it;
- compare one-agent versus staged outcomes on the same packets.

**Keep the roles, reduce default orchestration.**

## Tool harness

### Likely problem

Tool output is inconsistent, verbose, and occasionally more confusing than the underlying command.

### Tuning

- typed schemas and stable error classes;
- concise summaries plus durable full artifacts;
- tool reliability scoring;
- better transient/permanent/partial-effect classification;
- stage-specific tool exposure;
- usage telemetry to remove low-value tools.

**Keep; tool quality may matter more than adding more tools.**

## Change-aware validation

### Likely problem

Targeted tests are fast but occasionally miss distant regressions.

### Tuning

- retain the full publication gate;
- learn dependency and historical failure relationships;
- run broader tests for shared contracts, migrations, routing, and state;
- quarantine known flakes without treating them as passes;
- measure false-negative rates of affected-test selection.

**Keep; never let speed replace final assurance.**

## Independent review

### Likely problem

Reviewers generate plausible but low-value findings, causing unnecessary repair loops.

### Tuning

- severity calibration;
- acceptance-criterion-specific verdicts;
- reviewer precision tracking;
- require evidence and a concrete failure scenario;
- separate must-fix defects from suggestions;
- use a second reviewer only for high-risk disagreement.

**Keep; tune aggressively against false-positive review theatre.**

## Failure memory

### Likely problem

Old lessons become stale rules that block valid new approaches.

### Tuning

- expiration, version scope, and applicability conditions;
- evidence-backed lessons only;
- detect when the original cause has been fixed;
- allow contradiction and supersession;
- retrieve a few high-relevance lessons, not every historical incident.

**Keep; treat lessons as versioned evidence, not commandments.**

## Parallelism scheduler

### Likely problem

Parallel work creates hidden shared-state conflicts or overwhelms the M1 machine.

### Tuning

- path, symbol, migration, and configuration conflict prediction;
- actual CPU/RAM/disk pressure feedback;
- provider rate-limit awareness;
- dynamic concurrency reduction;
- merge-order simulation before launch.

**Keep, but default conservative.**

## Browser verification

### Likely problem

Pixel-level tests become brittle and expensive.

### Tuning

- prioritize user journeys, semantic DOM, accessibility, and important visual regions;
- use screenshot comparison only with tolerant, intentional baselines;
- distinguish content drift from layout regression;
- run mobile and error-state checks selectively by affected surface.

**Keep; avoid turning screenshots into a flaky second product.**

## Governed self-improvement

### Likely problem

The system optimizes metrics rather than outcomes or creates complexity faster than value.

### Tuning

- require a measurable problem before proposing a harness change;
- compare against a simple baseline;
- limit simultaneous policy experiments;
- require human review and rollback;
- periodically delete rules and machinery that no longer earn their complexity.

**Keep only after benchmark foundations are trustworthy.**

---

# Features that should merge

## Merge into Continue

- Continuations
- resume projections
- active project state
- interrupted chat recovery
- next-action suggestions
- waiting/blocked state

## Merge into Proof

- Execution Receipts
- Truth Layer presentation
- sources/citations
- memory-used disclosure
- verification and validation evidence
- model/provider/cost details
- uncertainty warnings

## Merge into History

- Operational Timeline
- What Changed
- activity feed
- build/run history
- decision outcomes
- receipt archive

## Merge into Preferences + Policy

- Reasoning Profiles
- privacy/local routing preferences
- cost and latency preferences
- notification thresholds
- domain-specific verification rules
- approval boundaries

## Merge into Compare and Decide

- Simulation Mode
- strategy comparison
- stress testing
- reversible-path analysis
- Decision Journal creation

## Merge into Routines

- Personal Automation Studio V1
- repeated successful workflows
- saved templates
- scheduled or triggered actions
- approval and stop conditions

## Merge into Connected Context

- World Model
- connected objects
- people/projects/commitments graph
- relevant constraints
- sourced relationships

---

# Features that should probably disappear as standalone concepts

1. **Raw reasoning display as a central feature** — provider summaries may remain available, but hidden chain-of-thought is not a product.
2. **A primary off/normal/deep reasoning knob** — keep advanced; normal users need Auto plus simple intent overrides.
3. **Reasoning Profiles as a named feature** — merge into policy preferences.
4. **World Model as a screen or brand** — retain sourced connected context only.
5. **Simulation Mode as a permanent mode** — make comparison contextual.
6. **Visible multi-agent role theatre** — keep collaboration internal.
7. **Full Automation Studio in early versions** — begin with Routines.
8. **Always-visible token/cost/provider telemetry** — show when relevant or expanded.
9. **Numerical confidence scores** — use evidence and specific warnings instead.
10. **A raw all-events Operational Timeline** — retain only advanced diagnostics.

---

# Missing capabilities the original roadmap underestimates

## 1. Universal Capture and Triage

Kitty needs a frictionless inbox for thoughts, screenshots, files, links, voice, emails, and unfinished ideas. It should classify later without forcing organization during capture.

Required behaviors:

- capture in one gesture;
- suggest project/object relationships;
- detect action, reference, idea, decision, and follow-up;
- prevent duplicate forgotten notes;
- surface important untriaged items without nagging.

## 2. Universal Search and Command Palette

Connected objects are not useful without fast retrieval.

Kitty needs one search/command surface across:

- conversations;
- projects;
- people;
- decisions;
- builds;
- artifacts;
- files;
- memories;
- sources;
- actions.

Search should support natural language, exact filtering, recent items, and direct commands.

## 3. Undo, Reversibility, and Change Preview

An unfair advantage includes confidence to act because changes can be understood and reversed.

Add:

- preview before consequential actions;
- explicit reversible versus irreversible labels;
- undo windows where technically valid;
- rollback artifacts and version history;
- `what will change?` before execution;
- `what changed?` after execution.

## 4. Unified Approval Center

Approvals should not be scattered across Home, Chat, Builder, and notifications.

One approval system should show:

- requested action;
- reason;
- risk;
- reversibility;
- cost;
- scope;
- expiration;
- approve once, approve bounded class, reject, or modify.

## 5. Outcome Tracking

Kitty can only improve recommendations if it learns what happened after the decision or action.

Add lightweight outcome capture:

- Did this solve the problem?
- Was the artifact used?
- Did the decision work?
- Was the build reverted?
- Did the user redo the task elsewhere?

Outcome tracking must remain sparse and contextual, not a satisfaction survey after every response.

## 6. Application Layer

Great answers need a direct path into reality.

Common actions:

- save as decision;
- turn into tasks;
- build this;
- schedule next step;
- draft/send through an approved connector;
- compare against an existing plan;
- attach to a project;
- create a routine;
- mark resolved.

The application layer may create more perceived intelligence than another increase in model reasoning.

## 7. Attention and Interruption Policy

Kitty needs rules for when not to interrupt.

Include:

- quiet/focus periods;
- urgency classes;
- channel-specific delivery;
- bundling and digests;
- escalation only when deadlines or risks materially change;
- awareness of whether the user is already handling the item.

## 8. Data Portability, Backup, and Recovery

A local personal operating system needs user confidence that its state is recoverable and exportable.

Add:

- verified backups;
- export of projects, decisions, artifacts, memories, and receipts;
- restore testing;
- retention and deletion controls;
- migration paths if storage models evolve.

## 9. Progressive Onboarding and Explainability

Kitty's power should reveal itself through use.

Add:

- contextual feature discovery;
- examples at the moment of need;
- `why am I seeing this?`;
- `what can I do here?`;
- novice and advanced disclosure without separate products;
- safe sample builds/routines.

## 10. Manual Intervention Without Restart

Long-running work needs steering.

Add:

- append instruction to an active or paused run;
- amend remaining plan while preserving accepted completed stages;
- take over a worktree;
- hand work back to Builder with explicit state;
- create a repair packet from a finding;
- resume from a chosen checkpoint.

## 11. Reliability Objectives

Kitty needs explicit product reliability targets:

- startup and reconnect behavior;
- state reconciliation latency;
- lost-work rate;
- false-success rate;
- stale-capability rate;
- notification precision;
- build recovery success;
- backup restore success.

Without these, the product may add intelligence while remaining operationally fragile.

## 12. Deletion and Complexity Budget

Every quarterly reassessment should ask what can be removed.

Track:

- surfaces rarely used;
- controls overridden by Auto;
- telemetry nobody acts on;
- prompts/rules that no longer improve benchmarks;
- duplicate stores or projections;
- features that add more management than leverage.

The roadmap should reserve capacity for simplification and deletion, not only expansion.

---

# Recommended nine-month product shape

## Primary navigation

1. **Home** — Continue, Needs You, meaningful changes, and direct actions.
2. **Chat** — ask, create, compare, decide, and apply.
3. **KittyBuilder** — builds, plans, progress, recovery, and verified results.
4. **Library** — artifacts, sources, files, images, and saved research.
5. **History** — meaningful activity, decisions, builds, and proof.

Settings contains connections, Preferences + Policy, notifications, privacy, backups, and advanced diagnostics.

Avoid adding separate primary tabs for:

- World Model;
- Decisions;
- Automations;
- Truth;
- Receipts;
- Memory;
- Reasoning;
- agents.

Those remain contextual views and object types within the five primary destinations.

---

# Reassessment scorecard

At the real six- and nine-month reviews, evaluate every feature against:

1. **Leverage:** Did it materially improve the user's outcome?
2. **Comprehension:** Could the user understand and apply it immediately?
3. **Frequency:** Did it solve a recurring problem?
4. **Trust:** Did it reduce false claims, uncertainty, or lost work?
5. **Calmness:** Did it reduce or increase cognitive load?
6. **Cost:** What latency, token, money, maintenance, and failure cost did it add?
7. **Distinctiveness:** Did it make Kitty feel meaningfully different?
8. **Replaceability:** Could a simpler interaction deliver the same value?
9. **Evidence:** Do usage and outcome data support keeping it?
10. **Deletion test:** Would the product become clearer if this disappeared?

Possible outcomes:

- **Double down** — strong leverage and distinctiveness.
- **Tune** — valuable but noisy, costly, or unreliable.
- **Merge** — keep the capability but remove its separate surface.
- **Advanced only** — useful for diagnostics or expert control.
- **Retire** — complexity exceeds proven value.

---

# Predicted final verdict

## Double down

- Continuations / Continue;
- KittyBuilder tab;
- context compiler;
- packet compiler and evidence traceability;
- connected context;
- Capability Manifest;
- visual recovery;
- one-step application of answers;
- universal capture and search.

## Tune continuously

- Home ranking and layout;
- Auto reasoning policy;
- proactive alerts;
- memory retrieval and correction;
- model routing and budgets;
- independent review;
- targeted validation;
- failure memory;
- parallel execution.

## Merge into simpler concepts

- receipts + truth + sources + memory evidence -> Proof;
- activity + timeline + changed digest -> History;
- reasoning profiles + approval/privacy/cost preferences -> Preferences + Policy;
- simulation + decision journal entry -> Compare and Decide;
- automations -> Routines;
- World Model + object graph -> Connected Context.

## Remove or keep advanced only

- raw chain-of-thought presentation;
- visible agent swarms;
- numerical confidence scores;
- always-visible telemetry;
- permanent model-native reasoning controls;
- raw event-stream UI;
- full automation programming UI before proven demand.

## Add because it was missing

- Capture;
- universal search/command palette;
- Undo and reversibility;
- unified approvals;
- outcome tracking;
- application actions;
- interruption policy;
- backup/export/restore;
- progressive onboarding;
- mid-run steering;
- reliability objectives;
- explicit complexity and deletion budgets.

The likely lesson after nine months is that Kitty's unfair advantage does not come from presenting every advanced capability. It comes from compressing those capabilities into a small number of obvious actions while keeping deep power, evidence, and control immediately available when needed.
