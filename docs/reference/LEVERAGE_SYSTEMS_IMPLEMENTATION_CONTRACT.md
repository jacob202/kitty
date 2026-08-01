# Leverage Systems — Implementation Contract

**Status:** Ratified design input with executable packaging
**Owner:** Jacob
**Sources:** issue #354 formal red-team review; issue #346 Chat trust reset; issue #353 Product Studio
**Architecture:** ADR 0017, ADR 0023, and ADR 0024
**Queue package:** `docs/initiatives/ktl-001-leverage-and-learning-v1.json`
**Operator entrypoint:** `.agents/skills/next/SKILL.md`

## Purpose

Turn the useful parts of issue #354 into bounded work that completes existing
Kitty and KittyBuilder responsibilities instead of creating new authorities.

The original ideas reduce to eight workstreams. The eighth is the connective
workflow that was previously missing: a deterministic `next` operation, a
complete session-end closeout, and a conservative learning loop that promotes
repeated evidence into the existing queue rather than creating another backlog.

This document is the consolidated implementation contract. `docs/ROADMAP.md`
remains the only active product roadmap; Builder remains the only execution
queue. This contract defines boundaries, proving slices, evidence, reuse rules,
and stop conditions. Its packetization lives in the queue manifest named above.

## Current parallel work — do not duplicate

At the time this contract was packaged:

- two independent workers were already verifying the real KittyBuilder path;
- one worker was already implementing the reuse-first Chat trust slice on
  `spike/chat-reuse-trust-slice`;
- PR #355 owned the mobile shell/fail-closed Slice 1 files;
- PR #356 owned the acceptance-policy follow-up.

These workers are evidence producers and dependencies. They are not permission
to start another Builder map, another Chat implementation, or another mobile
shell edit. Packets that consume their output must block with an exact missing
artifact reason rather than silently recreating it.

## Non-negotiable rules

1. **No new control plane.** Do not add a second Mission owner, queue, attempt
   store, event authority, budget ledger, approval path, merge path, workflow
   runtime, roadmap, or recommendation database.
2. **Continue before starting.** A valid current checkpoint or owned in-flight
   packet is completed/recovered before a new packet is selected.
3. **Finish ingress and projection before adding orchestration.** Existing
   authority must become usable before another coordinator is proposed.
4. **Runtime evidence outranks documents.** A design claim is not product truth
   until a deterministic test or real task proves it.
5. **One adapter boundary per imported platform.** Third-party UI, capture,
   testing, or evaluation code may sit at the edge; it may not own Kitty state.
6. **Every dependency declares what it replaces.** “Useful” is insufficient.
   The imported dependency must delete, avoid, or materially shrink named Kitty
   work.
7. **Every proving slice is removable.** A failed spike leaves fixtures and
   findings, not a permanent half-adopted platform.
8. **No activity theatre.** Outputs report usable outcomes, regressions,
   spend/waste, decisions, evidence gaps, and one next move—not commit counts or
   agent narration.
9. **Learning requires evidence and repetition.** A single annoyance is
   observed, not promoted. Integrity, security, data-loss, fabricated-success,
   queue-corruption, and paid-waste incidents may promote immediately.
10. **One bounded continuation per `next`.** Resolve, execute, verify, run
    session-end, and stop. Never roll directly into a second packet.

## Authority and storage boundary

| Concern | Existing authority | This program may do | This program must not do |
|---|---|---|---|
| Product direction | `docs/ROADMAP.md`, approved Mission/ADRs | package approved work as packets | create a second roadmap |
| Execution | Builder initiative/packet/task/attempt/event/review records | apply one versioned manifest and execute packets | invent another queue or edit SQLite |
| Session continuity | `.claude/STATE.md`, `.claude/HANDOFF.md` | leave one valid next action and parallel-work inventory | use free-form future notes |
| Cross-tool learning | `~/kb` | record durable knowledge, corrections, and workflow signals | copy project execution state into a new DB |
| Code and publication | Git, GitHub checks/reviews, Builder publication rails | preserve SHA-bound evidence and authorized low-risk publication | fabricate green state or bypass human boundaries |
| Product evidence | existing browser/runtime/test artifacts | capture, redact, replay, and cite evidence | treat screenshots or model consensus as acceptance |

## Dependency kill-switch record

Every proposed external dependency must record:

```text
dependency
  name, repository, license, pinned_version_or_sha, disposition
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

A dependency without a named replacement, boundary, proof, kill condition, and
exit path is rejected. “It has more features” is not evidence.

---

## 0. Continuous Execution and Learning Loop

### Problem

The repository has a queue, initiatives, worker briefs, evidence, session
checkpoints, and a knowledge base, but they are not connected tightly enough for
a coding tool to receive `next`, resolve the correct work, finish it, close the
session, and improve the process without Jacob repeatedly rebuilding context.

### Binding design

The repo-owned entrypoint is `.agents/skills/next/SKILL.md`. All supported tools
route a bare continuation instruction to the same workflow:

```text
cold-start receipt
  -> field survey
  -> continue owned in-flight work
  -> materialize approved initiative idempotently
  -> select highest-priority eligible non-colliding packet
  -> governed Builder execution
  -> deterministic evidence and independent review
  -> honest terminal/waiting state
  -> full session-end
  -> one valid next action
  -> stop
```

The approved executable package is:

```text
docs/initiatives/ktl-001-leverage-and-learning-v1.json
```

It is applied through Builder's existing idempotent initiative command. The
manifest is immutable after application: a hash conflict stops and requires a
new initiative revision.

### Selection rules

Continue before starting. Selection order is:

1. valid non-terminal work owned by the current session/tool;
2. a Builder packet already leased by the same worker identity;
3. an authorized recovery/review/publication action;
4. the highest-priority eligible queued packet with no live path collision;
5. one promoted workflow improvement only when no existing roadmap, initiative,
   queue task, PR, or issue owns it;
6. explicit no-op.

A different worker's lease is never stolen. Unrelated parallel work does not
block a packet. Path, state-authority, or required-artifact overlap does.

### Session learning

Session-end records no more than three structured signals through
`scripts/session_learning.py`:

```json
{
  "stable_key": "duplicate-chat-foundation-work",
  "category": "duplicate_work",
  "severity": "medium",
  "summary": "...",
  "evidence": "...",
  "impact": "...",
  "suggested_change": "...",
  "source_session": "...",
  "verified_by": "..."
}
```

Signals live under `~/kb/workflow-signals/`; when the separate KB is unavailable,
the documented fallback is `docs/session-notes/workflow-signals/`. The script
owns validation, stable identity, repeat counting, promotion status, and a
machine-readable summary. It does not mutate Builder or create issues.

Promotion rules:

- immediate: critical severity or an integrity/security/data-loss/
  fabricated-success/queue-integrity/paid-waste category;
- repeated: the same stable key appears in at least two sessions within 30 days;
- observe: one non-critical occurrence;
- suppress: an existing authority already owns the same problem.

A later bounded adapter may promote one deduplicated signal into Builder. It
must dry-run first, record the signal fingerprint, and create at most one task
per stable key. No background daemon and no GitHub issue flood.

### Acceptance

- A bare `next` resolves the same authorized continuation across OpenCode,
  Claude Code, and Codex.
- Existing owned work is continued; overlapping work is rejected; unrelated
  work may proceed in parallel.
- A byte-identical manifest apply creates no duplicate tasks.
- One instruction executes one packet cycle and invokes session-end once.
- The first ordinary signal is observed; its second occurrence promotes.
- Integrity incidents promote immediately.
- Corrupt learning records fail loudly.
- A second tool session resolves the post-session continuation rather than the
  packet already completed.

### Stop rule

Stop if this workflow needs its own queue, automatically executes arbitrary
checkpoint commands, creates unbounded recommendations, promotes single
annoyances, bypasses Builder fencing/review, or starts multiple packets from one
`next` instruction.

---

## 1. Mission Intake and Authority Projection

### Problem

Kitty and KittyBuilder already have the correct ownership boundary, but an
ordinary request does not reliably become one validated Mission followed by one
truthful explanation of current authority.

### Existing authority

- Kitty owns intent clarification, planning judgment, Mission authorship, and
  user communication.
- KittyBuilder owns Mission validation, durable execution state, eligibility,
  attempts, evidence, and recovery.
- `docs/ROADMAP.md`, `docs/mission/execution.md`, Builder records, git/PR state,
  and versioned decisions remain their current authorities.

### Smallest proving slice

Given one real request that conflicts with current work, produce a read-only
projection:

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

Then author the smallest valid Mission revision or reject the request with a
specific reason. Do not execute it in this slice.

### Acceptance

- Detects a duplicate branch/PR, unmet dependency, stale base, conflicting
  current priority, and unauthorized paid/destructive action.
- Same source state yields the same projection.
- Every statement cites its owning source and freshness.
- Missing data remains explicit; no “probably active” inference.
- Output contains exactly one allowed-next recommendation or an explicit no-op.
- A real conflicting request is rejected rather than converted into a polished
  prompt.

### Reuse

Adapt Spec Kit's clarification, specification, cross-artifact analysis, and
checklist patterns into Kitty's ISA and Mission contracts. Do not add `.specify/`
or another specification store.

### Stop rule

Stop if the slice needs its own mutable database, duplicates Builder eligibility,
or cannot outperform a direct read of canonical sources on seeded conflicts.

---

## 2. Independent KittyBuilder Operator Cockpit and Run Timeline

### Problem

Builder's durable execution truth exists, but it is not projected through one
independent, understandable repair surface.

### Binding architecture

ADR 0024. Same monorepo and Builder backend; separate frontend package/build/
process/URL; CLI remains the repair floor; normal Kitty shows only compact
decisions/status and a deep link.

### Ordered foundation

1. B1 reconstructs the live Builder path and classifies all `builder_*` modules.
2. One versioned runtime snapshot derives from existing authorities.
3. One normalized replayable event stream supplies a canonical timeline.
4. One generated typed client consumes the Builder API.
5. Decision Inbox becomes the home surface.
6. Initiative tree, worker pane, evidence inspector, and timeline follow.
7. Operator controls call canonical commands with actor, reason, expected
   version, and audited result.

The two active Builder-verification workers own step 1. No cockpit packet may
presume or duplicate their result. Missing or incomplete `builder-map.md` is a
block condition.

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

Compare embed, thin fork, and native approaches using a recorded Builder
snapshot/event fixture. Pin the tested version/SHA. Agent Canvas must render
with no OpenHands backend running. Measure adapter size, patched files,
bundle/build cost, memory, accessibility, responsive behavior, upgrade effort,
and replaced Kitty work.

### Acceptance

- Works while `kitty-chat` is deliberately stopped or broken.
- CLI, API, and UI agree on active, blocked, allowed-next, and prohibited state.
- Decision Inbox explains failed checks, merge conflict, exhausted budget, and
  required approval in plain language.
- Timeline distinguishes retained events, event gaps, raw fallback evidence,
  and inferred display-only grouping.
- One bounded action is requested and resolved through canonical Builder
  commands without optimistic local success.
- Mobile supports status, decisions, approvals, and evidence; it is not a
  compressed desktop IDE.

### Stop rule

Reject any approach that transfers authority to Agent Server, requires direct
SQLite reads, creates UI-owned state, or keeps a heavily patched fork whose
maintenance exceeds the avoided native work.

---

## 3. Product Evidence and Resilience Lab

### Problem

Jacob must currently reconstruct failures manually, while screenshots and prose
regressions can become stale and non-executable.

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

A bounded rolling interaction buffer may use rrweb, but recording is opt-in,
local, visibly active, aggressively redacted, and retained only long enough to
attach to a triage item. No automatic issue creation.

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

Start API-state injection with MSW. Add Toxiproxy only when transport-level
latency, reset, bandwidth, or connection loss cannot be represented truthfully
with fixtures.

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
- Secrets, tokens, prompt/private text selectors, file contents, and configured
  sensitive fields are redacted before persistence.
- At least three real failures are replayable and fail before their fix/pass
  after it.
- Pass means truthful, understandable, fail-closed, and recoverable—not merely
  “did not crash.”
- Captures expire or can be deleted with one command/action.

### Stop rule

Stop or reduce scope if capture creates privacy risk, unreliable reproduction,
high runtime overhead, or issue noise greater than the manual effort removed.

---

## 4. Capability Registry and Controlled Rollout

### Problem

Backend existence and visible UI have repeatedly been mistaken for shipped,
usable capability.

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

- `proven`: current acceptance evidence exists for the declared journey and
  viewport.
- `preview`: usable with disclosed limitations and a recovery path.
- `developer-only`: intentionally available only in engineering surfaces.
- `blocked`: requirements are unmet; visible only with a truthful reason and
  recovery where useful.
- `hidden`: should not be discoverable as a normal action.

The registry evaluates capability; it does not replace service health,
authorization, or Builder state. A capability can be structurally present and
still blocked or hidden.

### Smallest proving slice

Register three demonstrated problem surfaces, including image generation with
engines offline. Derive UI actionability from the evaluated registry rather than
component-local optimism.

### Acceptance

- Unproven actions cannot appear as normal shipped actions.
- A required service outage changes evaluated state without editing prose.
- Evidence expiration or revision mismatch downgrades the capability.
- Every blocked/preview state has a user-facing reason and, where possible, one
  recovery action.
- Manual overrides record actor, reason, expiry, and cannot promote directly to
  `proven` without evidence.

### Reuse

Borrow OpenFeature's provider-neutral evaluation shape, not a remote flag
service. Kitty retains richer maturity, evidence, viewport, and recovery
semantics.

### Stop rule

Stop if the registry becomes a second health system or generic feature-flag
platform. It remains a small projection over real health, policy, and evidence.

---

## 5. Kitty Model Evaluation Bench

### Problem

Model/provider choices are based too heavily on reputation, isolated anecdotes,
or price rather than Kitty-specific outcomes.

### Smallest proving slice

Create 10–20 golden tasks from actual failures and work classes:

- planning/contradiction detection;
- bounded packet authoring;
- code change with scoped tests;
- debugging from logs and runtime evidence;
- independent review;
- UX task-completion critique;
- research with primary-source evidence;
- browser operation;
- refusal/stop behavior under missing authority;
- provider failure and resume classification.

Use Inspect AI where multi-turn tools and agent behavior matter; use Promptfoo
for fast prompt/model matrices and red-team cases. Both must pass the reuse gate.
Store task fixtures, scorer version, model/provider/version, settings, raw
receipts, latency, cost, retries, variance, and catastrophic failures.

### Scoring

Correctness and evidence integrity dominate. Style is secondary:

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
- A cheaper model may be recommended only when it clears the task-class
  threshold.
- The compute governor remains routing authority; the bench supplies evidence,
  not live dispatch.
- No automatic routing change until shadow results show no unacceptable
  regression.

### Stop rule

Stop expansion if tasks are synthetic, scorers reward verbosity, provider
versions are not recorded, or benchmark maintenance exceeds routing savings.

---

## 6. Builder Live-Path and Change-Impact Mapping

### Problem

The repository contains many Builder modules and broad tests, but the live
invocation path and journey impact of changes are not trustworthy enough to
drive deletion or targeted testing.

### B1 contract

Produce `docs/mission/builder-map.md` covering every current
`gateway/builder_*` module:

- classification: live, test-only, dormant/feature-gated, duplicate, dead
  candidate, or unknown;
- concrete importer/call site;
- entrypoint and runtime path;
- owning state/store/API;
- tests that exercise it;
- confidence and unresolved dynamic-registration risk.

Trace at least one real `./kitty builder` invocation from CLI parsing to eligible
packet selection, worker dispatch, attempt/event persistence,
validation/review, and terminal reporting. Static tools may identify
candidates; runtime tracing is final authority.

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

Changed paths select relevant journeys and dependency-off states. A periodic
full suite remains the backstop. Evaluate `pytest-testmon` in shadow and compare
misses/false positives before it can skip required tests.

### Acceptance

- All Builder modules classified with evidence; unknown remains explicit.
- One live trace proves the actual path rather than presumed architecture.
- Deletion candidates require static and runtime evidence plus full-suite proof.
- Impact selection never suppresses required full-suite/periodic checks.
- Reliability is measured by seeded changes that must select known affected
  tests/journeys.

### Stop rule

Do not build a graph database, migrate build systems, or auto-delete code. Stop
affected-test automation if it misses any seeded critical journey.

---

## 7. Product Studio and Reuse-First Chat

Issue #353 owns taste memory, design exploration, synthetic specialist review,
and real-user validation.

### Product Studio boundaries

- accepted/rejected designs store the artifact and reason, not a guessed
  preference profile;
- synthetic reviewers generate hypotheses, never acceptance evidence;
- every important exploratory finding becomes a deterministic journey or a
  real-user test;
- Product Studio consumes friction captures, failure specimens, capability
  state, and Builder evidence rather than duplicating them;
- Playwright remains journey authority;
- axe-core may verify measurable accessibility properties but cannot certify
  overall accessibility;
- Lighthouse CI supplies regression evidence, not comprehension judgment;
- Storybook is adopted only when it replaces named component-state/test work;
- exploratory browser agents discover; deterministic tests prove.

### Reuse-first Chat lane

Kitty already uses `@assistant-ui/react`; PR #286 proved that LibreChat and
AnythingLLM could boot against a Kitty-compatible gateway but did not establish
product fit. Bootability is not adoption evidence.

The active Chat worker owns the first real reuse trust slice. Its required
workflow is:

```text
send
  -> incremental real stream
  -> one durable user turn and one assistant turn
  -> browser reload
  -> Kitty process restart
  -> identical conversation resume
  -> truthful provider/stream failure
  -> safe retry without duplicate user turn or fabricated success
```

A landing-review packet consumes that worker's branch/PR and reuse ledger. It
must not implement another Chat path. Accepted reused work records exact source,
license, pin, symbols inspected, Kitty code deleted/avoided, adapter boundary,
maintenance, and kill conditions. Any candidate that creates competing
conversation, memory, routing, agent, or permission authority is rejected.

---

## Executable packet map

`ktl-001-leverage-and-learning-v1` packages this contract as:

| Packet | Proves |
|---|---|
| KTL-001 | one deterministic cross-tool `next` resolution |
| KTL-002 | evidence-based session-end learning |
| KTL-003 | deduplicated promoted-signal → Builder adapter |
| KTL-004 | replace-or-avoid dependency gate |
| KTL-005 | independent landing review of the active Chat reuse worker |
| KTL-006 | private redacted friction capture and one executable specimen |
| KTL-007 | three fail-closed capabilities from runtime evidence |
| KTL-008 | Product Studio over shared real evidence |
| KTL-009 | Agent Canvas embed/fork/native decision after verified B1 |
| KTL-010 | Kitty-specific model bench |
| KTL-011 | read-only Mission authority projection |
| KTL-012 | one complete `next` → packet → session-end → next cycle |

Packets KTL-005 and KTL-009 are consumer gates for the active Chat and Builder
workers. They block on missing artifacts rather than duplicate them.

## Cross-workstream promotion order

Current active roadmap work remains first. Within this program:

1. Verify the `next` protocol.
2. Verify session-end learning and deduplicated promotion.
3. Enforce the reuse-first dependency gate.
4. Consume and independently verify the active Chat worker.
5. Capture private friction and executable failures.
6. Prove the capability registry.
7. Prove Product Studio on shared evidence.
8. Consume verified Builder B1 and run the Agent Canvas decision spike.
9. Build the model bench from real failures.
10. Build Mission authority projection after its sources are deterministic.
11. Prove the complete cross-tool continuation cycle.

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

A document, mock UI, screenshot, model claim, passing unit test without the user
journey, boot-only external application, or new database containing copied truth
is not completion.
