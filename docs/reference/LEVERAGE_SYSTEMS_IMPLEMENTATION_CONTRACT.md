# Leverage Systems — Implementation Contract

**Status:** Ratified design input; execution remains governed by `docs/ROADMAP.md` and `docs/mission/execution.md`
**Owner:** Jacob
**Source:** issue #354 formal red-team review
**Architecture:** ADR 0017 and ADR 0024

## Purpose

Turn the useful parts of issue #354 into bounded work that completes existing Kitty and KittyBuilder responsibilities instead of creating new authorities.

The 17 original ideas reduce to seven workstreams. A workstream may be promoted only when the canonical roadmap names its dependency, owner, proving slice, evidence, and stop rule. This document is not a parallel roadmap and cannot authorize execution by itself.

## Non-negotiable rules

1. **No new control plane.** Do not add a second Mission owner, queue, attempt store, event authority, budget ledger, approval path, merge path, or workflow runtime.
2. **Finish ingress and projection before adding orchestration.** Existing authority must become usable before another coordinator is proposed.
3. **Runtime evidence outranks documents.** A design claim is not product truth until a deterministic test or real task proves it.
4. **One adapter boundary per imported platform.** Third-party UI, capture, testing, or evaluation code may sit at the edge; it may not own Kitty state.
5. **Every dependency declares what it replaces.** “Useful” is insufficient. The imported dependency must delete, avoid, or materially shrink named Kitty work.
6. **Every proving slice is removable.** A failed spike leaves fixtures and findings, not a permanent half-adopted platform.
7. **No activity theatre.** Outputs report usable outcomes, regressions, spend/waste, decisions, evidence gaps, and one next move—not commit counts or agent narration.

## Dependency kill-switch record

Every proposed external dependency must record:

```text
dependency
  name, repository, license, pinned_version_or_sha
purpose
  exact Kitty problem and owning workstream
replacement
  Kitty files/components/work that will be deleted or no longer built
boundary
  allowed inputs/outputs and forbidden authority
proof
  fixture or real task, measurements, acceptance evidence
maintenance
  expected upgrade cadence, patch count, generated code, notices
kill_conditions
  measurable reasons to reject or remove it
exit
  how Kitty returns to the prior implementation without losing durable state
```

A dependency without a named replacement and kill condition is rejected.

---

## 1. Mission Intake and Authority Projection

### Problem

Kitty and KittyBuilder already have the correct ownership boundary, but an ordinary request does not reliably become one validated Mission followed by one truthful explanation of current authority.

### Existing authority

- Kitty owns intent clarification, planning judgment, Mission authorship, and user communication.
- KittyBuilder owns Mission validation, durable execution state, eligibility, attempts, evidence, and recovery.
- `docs/ROADMAP.md`, `docs/mission/execution.md`, Builder records, git/PR state, and versioned decisions remain their current authorities.

### Smallest proving slice

Given one real request that conflicts with current work, produce a read-only projection:

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "authoritative_sources": [],
  "active": [],
  "blocked": [{"item": "...", "reason": "...", "recovery": "..."}],
  "allowed_next": [],
  "prohibited": [{"item": "...", "authority": "...", "reason": "..."}],
  "contradictions": [],
  "stale_decisions": [],
  "required_human_decisions": [],
  "evidence_gaps": []
}
```

Then author the smallest valid Mission revision or reject the request with a specific reason. Do not execute it in this slice.

### Acceptance

- Detects a duplicate branch/PR, unmet dependency, stale base, conflicting current priority, and unauthorized paid/destructive action.
- Same source state yields the same projection.
- Every statement cites its owning source and freshness.
- Missing data remains explicit; no “probably active” inference.
- Output contains exactly one allowed-next recommendation or an explicit no-op.
- A real conflicting request is rejected rather than converted into a polished prompt.

### Reuse

Adapt Spec Kit's clarification, specification, cross-artifact analysis, and checklist patterns into Kitty's ISA and Mission contracts. Do not add `.specify/` or another specification store.

### Stop rule

Stop if the slice needs its own mutable database, duplicates Builder eligibility, or cannot outperform a direct read of the canonical sources on the seeded conflict cases.

---

## 2. Independent KittyBuilder Operator Cockpit and Run Timeline

### Problem

Builder's durable execution truth exists, but it is not projected through one independent, understandable repair surface.

### Binding architecture

ADR 0024. Same monorepo and Builder backend; separate frontend package/build/process/URL; CLI remains the repair floor; normal Kitty shows only compact decisions/status and a deep link.

### Ordered foundation

1. B1 reconstructs the live Builder path and classifies all `builder_*` modules.
2. One versioned runtime snapshot derives from existing authorities.
3. One normalized replayable event stream supplies a canonical timeline.
4. One generated typed client consumes the Builder API.
5. Decision Inbox becomes the home surface.
6. Initiative tree, worker pane, evidence inspector, and timeline follow.
7. Operator controls call canonical commands with actor, reason, expected version, and audited result.

### Standard run evidence bundle

```text
identity
  mission revision, initiative, packet, attempt, session
source
  repository, base SHA, branch, worktree, HEAD, dirty state
execution
  worker/backend/model, commands/tools, normalized events, raw-log links
gates
  scope, validation, review, PR/checks, merge/publish state
resources
  estimates, actual provider usage, GPU/runtime/cleanup cost, bypass actor/reason
artifacts
  diffs, commits, screenshots, reports, hashes
attention
  blocker, failed checks, conflict, exhausted budget, required decision
integrity
  generated_at, source versions, missing/stale sources, explicit event gaps
```

### Agent Canvas spike

Compare embed, thin fork, and native approaches using a recorded Builder snapshot/event fixture. Pin the tested version/SHA. Agent Canvas must render with no OpenHands backend running. Measure adapter size, patched files, bundle/build cost, memory, accessibility, responsive behavior, upgrade effort, and replaced Kitty work.

### Acceptance

- Works while `kitty-chat` is deliberately stopped or broken.
- CLI, API, and UI agree on active, blocked, allowed-next, and prohibited state.
- Decision Inbox explains failed checks, merge conflict, exhausted budget, and required approval in plain language.
- Timeline distinguishes retained events, event gaps, raw fallback evidence, and inferred display-only grouping.
- One bounded action is requested and resolved through canonical Builder commands without optimistic local success.
- Mobile supports status, decisions, approvals, and evidence; it is not a compressed desktop IDE.

### Stop rule

Reject any approach that transfers authority to Agent Server, requires direct SQLite reads, creates UI-owned state, or keeps a heavily patched fork whose maintenance exceeds the avoided native work.

---

## 3. Product Evidence and Resilience Lab

### Problem

Jacob must currently reconstruct failures manually, while screenshots and prose regressions can become stale and non-executable.

### Smallest proving slice: private friction capture

A deliberate dogfood control captures a redacted local bundle:

```text
capture.json
  capture id/time, route, viewport, source/build/runtime ids
note.txt or note audio reference
screenshot.png
recent-actions.json
console.json
network.json
runtime-manifest.json
redaction-report.json
```

A bounded rolling interaction buffer may use rrweb, but recording is opt-in, local, visibly active, aggressively redacted, and retained only long enough to attach to a triage item. No automatic issue creation.

### Executable failure specimen

Each real failure becomes:

```text
specimen
  id, original evidence, affected journey, dependency state
fixture
  minimal deterministic service/browser setup
expectation
  honest user-visible result and recovery action
test
  Playwright assertion and produced evidence
```

Start API-state injection with MSW. Add Toxiproxy only when transport-level latency, reset, bandwidth, or connection loss cannot be represented truthfully with fixtures.

### First seeded failures

- mobile header/control clipping;
- raw internal-server-error text;
- visible action that cannot succeed because its service is offline;
- duplicate/stale launcher serving a different checkout;
- RunPod worker readiness timeout;
- lost or fabricated success receipt;
- failed check or merge conflict not surfaced as a recovery action.

### Acceptance

- One tap plus an optional short note produces a ready-to-triage bundle.
- Secrets, tokens, prompt/private text selectors, file contents, and configured sensitive fields are redacted before persistence.
- At least three real failures are replayable and fail before their fix/pass after it.
- Pass means truthful, understandable, fail-closed, and recoverable—not merely “did not crash.”
- Captures expire or can be deleted with one command/action.

### Stop rule

Stop or reduce scope if capture creates privacy risk, unreliable reproduction, high runtime overhead, or issue noise greater than the manual effort it removes.

---

## 4. Capability Registry and Controlled Rollout

### Problem

Backend existence and visible UI have repeatedly been mistaken for shipped, usable capability.

### Canonical entry

```json
{
  "id": "image.generate",
  "schema_version": 1,
  "maturity": "proven | preview | developer-only | blocked | hidden",
  "required_services": [],
  "supported_viewports": [],
  "evidence": [],
  "last_proven_revision": null,
  "last_proven_at": null,
  "current_blocker": null,
  "recovery_action": null,
  "owner": "...",
  "evaluation_source": "runtime | policy | manual-override",
  "expires_at": null
}
```

### Semantics

- `proven`: current acceptance evidence exists for the declared journey and viewport.
- `preview`: usable with disclosed limitations and a recovery path.
- `developer-only`: intentionally available only in engineering surfaces.
- `blocked`: requirements are unmet; visible only with a truthful reason/recovery where useful.
- `hidden`: should not be discoverable as a normal action.

The registry evaluates capability; it does not replace service health, authorization, or Builder state. A capability can be structurally present and still blocked or hidden.

### Smallest proving slice

Register three demonstrated problem surfaces, including image generation with engines offline. Derive UI actionability from the evaluated registry rather than component-local optimism.

### Acceptance

- Unproven actions cannot appear as normal shipped actions.
- A required service outage changes the evaluated state without editing prose.
- Evidence expiration or revision mismatch downgrades the capability.
- Every blocked/preview state has a user-facing reason and, where possible, one recovery action.
- Manual overrides record actor, reason, expiry, and cannot promote directly to `proven` without evidence.

### Reuse

Borrow OpenFeature's provider-neutral evaluation shape, not a remote flag service. Kitty retains richer maturity, evidence, viewport, and recovery semantics.

### Stop rule

Stop if the registry becomes a second health system or a generic feature-flag platform. It must remain a small projection over real health, policy, and evidence.

---

## 5. Kitty Model Evaluation Bench

### Problem

Model/provider choices are based too heavily on reputation, isolated anecdotes, or price rather than Kitty-specific outcomes.

### Smallest proving slice

Create 10–20 golden tasks from actual failures and work classes:

- planning/contradiction detection;
- bounded packet authoring;
- code change with scoped tests;
- debugging from logs and runtime evidence;
- independent review;
- UX task completion critique;
- research with primary-source evidence;
- browser operation;
- refusal/stop behavior under missing authority;
- provider failure and resume classification.

Use Inspect AI where multi-turn tools and agent behavior matter; use Promptfoo for fast prompt/model matrices and red-team cases. Store task fixtures, scorer version, model/provider/version, settings, raw receipts, latency, cost, retries, and catastrophic failures.

### Scoring

Correctness and evidence integrity dominate. Style is secondary. Minimum dimensions:

- task completion;
- factual/evidence grounding;
- scope discipline;
- authority compliance;
- recovery quality;
- runtime and cost;
- retry rate;
- catastrophic/fabricated-success rate.

### Acceptance

- Blinded scoring where feasible.
- Repeated runs expose variance.
- A cheaper model may be recommended only when it clears the task-class threshold.
- The compute governor remains routing authority; the bench supplies evidence, not live dispatch.
- No automatic routing change until shadow results show no unacceptable regression.

### Stop rule

Stop expansion if tasks are synthetic, scorers reward verbosity, provider versions are not pinned/recorded, or benchmark maintenance exceeds routing savings.

---

## 6. Builder Live-Path and Change-Impact Mapping

### Problem

The repository contains many Builder modules and broad tests, but the live invocation path and journey impact of changes are not trustworthy enough to drive deletion or targeted testing.

### B1 contract

Produce `docs/mission/builder-map.md` covering every `gateway/builder_*` module:

- classification: live, test-only, dormant/feature-gated, duplicate, dead candidate, or unknown;
- concrete importer/call site;
- entrypoint and runtime path;
- owning state/store/API;
- tests that exercise it;
- confidence and unresolved dynamic-registration risk.

Trace at least one real `./kitty builder` invocation from CLI parsing to eligible packet selection, worker dispatch, attempt/event persistence, validation/review, and terminal reporting. Static tools may identify candidates; runtime tracing is final authority.

### Change-impact slice after B1

Introduce an explicit manifest:

```text
journey
  id, user goal, viewports, dependency states
implementation
  routes, components, services, schemas, commands
verification
  unit/integration/browser tests, evidence requirements
```

Changed paths select relevant journeys and dependency-off states. A periodic full suite remains the backstop. Evaluate `pytest-testmon` in shadow and compare misses/false positives before it can skip required tests.

### Acceptance

- All Builder modules classified with evidence; unknown remains allowed but explicit.
- One live trace proves the actual path rather than a presumed architecture.
- Deletion candidates require both static and runtime evidence plus full-suite verification.
- Impact selection never suppresses required full-suite/periodic checks.
- Reliability is measured by seeded changes that must select known affected tests/journeys.

### Stop rule

Do not build a graph database, migrate build systems, or auto-delete code. Stop affected-test automation if it misses any seeded critical journey until the mapping is corrected.

---

## 7. Product Studio

Issue #353 owns taste memory, design exploration, synthetic specialist review, and real-user validation.

This contract adds only boundaries:

- accepted/rejected designs store the artifact and the reason, not a guessed preference profile;
- synthetic reviewers generate hypotheses, never acceptance evidence;
- every important exploratory finding becomes a deterministic journey or a real-user test;
- Product Studio consumes friction captures, failure specimens, capability state, and Builder evidence rather than duplicating them.

---

## Cross-workstream promotion order

Current active roadmap work remains first. When dependencies permit:

1. Builder B1 live-path reconstruction.
2. Product acceptance enforcement (#349).
3. Private friction capture and first executable failure specimens.
4. Capability registry proving slice.
5. Agent Canvas foundation spike under ADR 0024.
6. Builder B2–B10, then the independent cockpit and conversational B11.
7. Model evaluation bench from real Kitty failures.
8. Change-impact selection only after the journey and runtime maps are trustworthy.
9. Mission intake/authority projection after the sources it must project are deterministic enough to trust.

## Definition of done for any promoted slice

A slice is complete only when it records:

- recurring problem and measured baseline cost/harm;
- exact existing authority it extends;
- smallest real failure/task used as proof;
- code and dependency boundary;
- deterministic validation and required runtime evidence;
- privacy/security/cost implications;
- false positives, false negatives, runtime, maintenance, and time saved;
- one consequential Jacob choice or fewer;
- removal/rollback path;
- explicit limitations and next dependency.

A document, mock UI, screenshot, model claim, passing unit test without the user journey, or new database containing copied truth is not completion.
