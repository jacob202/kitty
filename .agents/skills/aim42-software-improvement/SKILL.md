---
name: aim42-software-improvement
description: Evidence-first software modernization workflow adapted from aim42. USE WHEN: architecture modernization, legacy system assessment, technical debt audit, migration planning, repository health review, maintenance cost reduction, refactoring strategy. NOT FOR: greenfield design, an isolated bug fix, or executing an already-approved bounded patch.
when_to_use: architecture modernization, legacy system assessment, technical debt audit, migration planning, repository health review, maintenance cost reduction, refactoring strategy
allowed_tools: [read, search, bash, git, github, browser]
---

# AIM42 Software Improvement

Use this skill to improve an existing software system systematically instead of
jumping from a visible symptom to a fashionable rewrite. It adapts the aim42
method into an evidence-driven workflow suitable for AI coding agents and
KittyBuilder.

The core loop is:

> **Analyze → Evaluate → Improve → Verify → repeat**

## Non-negotiable rules

1. **Diagnose before prescribing.** During analysis, record problems, risks,
   symptoms, constraints, and causes. Do not smuggle proposed solutions into the
   issue description.
2. **No orphan improvements.** Every proposed improvement must link to one or
   more evidenced issues. Do not optimize merely because a technique is
   available.
3. **Separate evidence from judgment.** Label important statements as:
   - **VERIFIED** — directly inspected in code, runtime output, Git, CI, data, or
     another authoritative source.
   - **INFERENCE** — a reasoned interpretation of verified evidence.
   - **HYPOTHESIS** — plausible but still requiring a test.
4. **Observe before estimating.** Prefer measured frequency, latency, failure
   rate, change history, support burden, or developer effort. When measurement
   is unavailable, estimate with a lower and upper bound and list every material
   assumption.
5. **Respect existing authority.** Read the repository's current architecture,
   decisions, roadmap, active mission, and runtime evidence before creating a
   plan. Do not create a competing backlog or state machine.
6. **Improve incrementally by default.** Prefer a small reversible slice,
   prototype, adapter, strangler seam, or change-by-abstraction over a big-bang
   rewrite.
7. **Verify after every change.** A clean diff or passing unit test is not enough
   when the issue concerns runtime behavior, data, UX, deployment, cost, or
   operability.
8. **Keep traceability.** Preserve the many-to-many links between issues,
   causes, improvements, acceptance evidence, and remaining risks.

## Phase 0 — Establish the improvement frame

Before broad inspection, write down:

- system and repository in scope;
- user or business outcome being protected;
- current authority sources;
- relevant quality attributes, such as reliability, maintainability, security,
  performance, portability, usability, cost, recoverability, or auditability;
- constraints: budget, deadlines, compatibility, data retention, deployment,
  permissions, and work already in progress;
- excluded areas and forbidden actions;
- the evidence needed to call the assessment complete.

When quality requirements are vague, express them as scenarios:

```text
Context:       Under what operating condition?
Trigger:       What event or change occurs?
Expected:      What must the system do?
Target:        What measurable limit or outcome defines success?
Constraints:   What must remain unchanged or protected?
Evidence:      How will this be demonstrated?
```

Do not continue with a broad modernization plan until the desired outcomes and
constraints are concrete enough to evaluate tradeoffs.

## Phase 1 — Analyze

The goal is to understand the system and identify issues, not to produce a long
list of refactoring ideas.

### 1. Build a view-based understanding

Inspect enough evidence to explain:

- **Context:** users, clients, external systems, trust boundaries, and major
  inputs/outputs.
- **Building blocks:** large modules, responsibilities, dependencies, state
  owners, and interfaces.
- **Runtime:** important request, background-job, failure, and recovery flows.
- **Deployment:** processes, hosts, ports, storage, credentials, queues, and
  operational dependencies.
- **Data:** canonical stores, derived stores, migrations, ownership, backup,
  restore, retention, and portability.
- **Delivery process:** branch/PR/CI/release path, worker behavior, review,
  observability, and rollback.

Use current code and runtime evidence as primary sources. Treat diagrams and
prose as claims until they agree with the implementation.

### 2. Inspect complementary evidence lanes

Select the lanes relevant to the problem rather than reading everything:

- repository structure and dependency direction;
- Git history, churn, ownership concentration, recurring reverts, and hotspots;
- CI failures, test coverage, flaky tests, ignored checks, and release failures;
- runtime logs, traces, metrics, resource use, startup/shutdown, and recovery;
- issue and PR history, support reports, and repeated operator workarounds;
- documentation freshness and contradictory sources of truth;
- data integrity, migration behavior, backup/restore, and hidden state;
- user journeys, accessibility, response time, confusing states, and dead ends;
- development and operational process, including handoffs and knowledge islands.

### 3. Build an issue ledger

Create one record per distinct issue:

```text
Issue ID:
Title:
Observed symptom:
Affected outcome / quality attribute:
Direct evidence:
Frequency or exposure:
Impact interval:
Likely immediate mechanism:
Likely structural/root cause:
Confidence: high | medium | low
Unknowns / disconfirming evidence:
Related issues:
```

Avoid vague labels such as "architecture is messy." Describe an observable
failure, cost, risk, or impediment.

### 4. Separate cause from effect

For high-impact issues, trace at least four levels where evidence permits:

```text
Visible symptom
  → immediate technical mechanism
  → structural design or state-ownership cause
  → process, incentive, or governance condition that allowed recurrence
```

Do not treat correlation, code proximity, or a plausible narrative as root-cause
proof. Record competing hypotheses and the cheapest discriminating test.

### Analyze exit gate

Proceed only when:

- the important system boundaries and state owners are understood;
- the highest-impact issues have direct evidence;
- symptoms and causes are distinguished;
- major unknowns and assumptions are explicit;
- each candidate improvement can be linked to a real issue.

## Phase 2 — Evaluate

The goal is to make issues and remedies comparable without fake precision.

For each important issue, record:

- measured or estimated cost per occurrence or time period;
- frequency/exposure range;
- user, business, operational, and engineering consequences;
- probability and severity if the issue is a risk;
- confidence and assumptions.

For each candidate improvement, record:

```text
Improvement ID:
Linked issue IDs:
Approach:
Expected benefit interval:
Implementation effort interval:
Operational / migration effort interval:
New risks introduced:
Reversibility:
Dependencies and work unblocked:
Learning value:
Confidence and assumptions:
Evidence required before adoption:
Disposition: adopt | spike | defer | reject
```

### Evaluation discipline

- Compare against **doing nothing** and at least one smaller alternative.
- Estimate with intervals, not a single magic number.
- Mark values as **observation**, **calculation**, or **assumption**.
- Prefer categories and deterministic policy over an LLM-generated 1–10 score.
- Give priority to improvements that remove a costly issue, unblock current
  delivery, reduce recurring risk, and can be verified cheaply.
- Penalize solutions that add a framework, database, queue, protocol, state
  machine, or service without removing more complexity than they introduce.
- Keep rejected and deferred options with reasons so they are not repeatedly
  rediscovered.

### Evaluate exit gate

Select one improvement slice only when its expected value, cost range, risks,
dependencies, and evidence plan are explicit enough to make a defensible choice.

## Phase 3 — Improve

Choose the least disruptive approach that can resolve or materially test the
linked issue.

Useful approach families include:

- **Prototype or spike:** test an uncertain assumption at low cost.
- **Boy-scout improvement:** bounded cleanup while already changing the area;
  larger work returns to the authorized backlog.
- **Change by abstraction:** insert a stable boundary, move callers, then replace
  the implementation.
- **Anti-corruption layer:** isolate a legacy or vendor-specific model behind an
  owned adapter.
- **Strangler:** redirect slices of behavior to a replacement while the old path
  remains available.
- **Split or modularize:** separate responsibilities whose coupling causes
  verified change or failure costs.
- **Data-first, data-last, or composite migration:** choose based on data
  ownership, compatibility, rollback, and availability requirements.
- **Rewrite:** exceptional; require evidence that incremental paths cannot meet
  the outcome and a credible migration/rollback plan.

### Define the bounded slice

Before editing, specify:

```text
Linked issue(s):
Hypothesis:
Exact scope:
Out of scope:
Acceptance criteria:
Baseline measurement:
Verification commands / runtime proof:
Data migration and rollback:
Blast radius:
Owner / implementer / independent verifier:
Stop conditions:
```

Then implement the smallest coherent slice. Do not combine unrelated cleanup,
feature work, and architectural migration in one change.

## Phase 4 — Verify and iterate

Compare the result against the same scenario and measurement used at baseline.
Verification may require several layers:

- focused unit and integration tests;
- full regression suite and static checks;
- clean-install, startup, shutdown, restart, and recovery proof;
- browser or device evidence for UI behavior;
- data integrity, migration, export/import, and rollback proof;
- latency, cost, resource, or failure-rate comparison;
- Git/CI/PR/runtime evidence showing that the delivery process works;
- user or operator confirmation for real-world outcomes.

For every linked issue, report one state:

- **resolved** — acceptance evidence proves the issue is removed;
- **partially resolved** — measurable improvement with residual issue stated;
- **not resolved** — change landed but evidence does not show improvement;
- **worse / regressed** — baseline deteriorated; rollback or corrective action is
  required;
- **unknown** — verification could not be completed.

Feed verified results and residual risks back into the existing roadmap, issue
tracker, ADRs, or evidence store. Do not declare completion from implementation
alone.

## Required final output

When this skill is used for an assessment, produce these sections:

1. **Decision summary** — what should happen next and why.
2. **System understanding** — boundaries, state ownership, runtime, data, and
   delivery flow relevant to the problem.
3. **Issue ledger** — prioritized, evidence-backed issues with causes separated
   from symptoms.
4. **Improvement options** — linked remedies, including no-change and smaller
   alternatives.
5. **Evaluation** — cost/benefit ranges, assumptions, risks, dependencies, and
   dispositions.
6. **Next bounded slice** — one actionable improvement with acceptance,
   verification, rollback, owner, and stop conditions.
7. **Unknowns** — unresolved questions and the cheapest tests to answer them.
8. **Verification report** — after execution, before/after evidence and residual
   risks.

## Failure modes to reject

- rewriting before understanding the existing system;
- solution-first audits that manufacture issues to justify a preferred tool;
- calling code smell or age an issue without demonstrated impact;
- treating documentation, a model's summary, or passing tests as runtime proof;
- converting an estimate into a fact;
- one-way migrations without backup and rollback;
- broad "cleanup" PRs with no linked issue or acceptance contract;
- declaring an issue resolved because code was written;
- creating a second roadmap, backlog, architecture authority, or execution state
  machine;
- optimizing infrastructure while the user-facing outcome remains broken.

## Source and attribution

This skill is an original, condensed adaptation of the open aim42 software
architecture improvement method and its Analyze, Evaluate, Improve, and
cross-cutting practices. Reference: https://aim42.github.io/ . Preserve this
attribution when redistributing substantial derivatives.
