# Leverage Systems — Implementation Contract

**Status:** Ratified design input with corrected executable packaging  
**Owner:** Jacob  
**Sources:** issue #354 formal red-team review; issue #346 Chat trust reset; issue #353 Product Studio  
**Architecture:** ADR 0017, ADR 0023, ADR 0024, ADR 0025, ADR 0026  
**Corrective proving package:** `docs/initiatives/ktl-002-measured-learning-boundary-v1.json`  
**Broader work package:** `docs/initiatives/ktl-001-leverage-and-learning-v1.json` subject to `docs/initiatives/README.md`

## Purpose

Turn the useful parts of issue #354 into bounded work that completes existing
Kitty and KittyBuilder responsibilities instead of creating new authorities.

`docs/ROADMAP.md` remains the only active product roadmap. KittyBuilder remains
the only execution queue. `.claude/STATE.md` and `.claude/HANDOFF.md` remain
interactive continuity. `~/kb` remains cross-tool knowledge and evidence.

This contract defines boundaries, proving slices, reuse rules, evidence, and
stop conditions. It does not itself authorize execution or prove that a tracked
initiative was applied to the local Builder queue.

## Workflow correction

A manually opened Claude Code, OpenCode, Codex, or other repo-aware tool is an
interactive engineering workspace. A bare `next` continues that tool's current
assignment from a valid checkpoint. It may inspect Builder to avoid collision,
but it does not apply initiatives, select/claim/run packets, or drain Builder.

KittyBuilder is a separate autonomous build train. It selects approved eligible
packets under its own scheduler, launches replaceable workers, manages leases
and worktrees, validates, obtains independent review, preserves evidence,
recovers, and continues unrelated work after failure.

Builder may use Claude Code, OpenCode, Codex, or shell adapters as workers. Such
a process is Builder-owned only when a valid task/packet bundle or explicit
durable transfer and matching live lease prove it.

Every implementation has exactly one execution owner:

```text
interactive | builder
```

Reviewing work does not transfer implementation ownership.

The following are distinct intents:

```text
next            continue the current interactive assignment
builder status  inspect Builder without taking work
builder next    explicitly enter Builder's governed selection/execution path
review builder  independently review output without taking implementation ownership
session end     preserve evidence, measure KB use, update continuity, then stop
```

The first three workflow packets in
`ktl-001-leverage-and-learning-v1.json` were authored before this correction and
must not be applied as the current boundary. The corrective proving package is
`ktl-002-measured-learning-boundary-v1.json`. The remaining independent reuse,
evidence, capability, Product Studio, Agent Canvas, model-bench, and
Mission-projection concepts remain inputs and must have their dependencies
reconciled before application.

## Current parallel work — do not duplicate

At packaging time:

- independent workers were verifying the real KittyBuilder path;
- another worker was implementing the reuse-first Chat trust slice;
- PR #355 owned mobile shell/fail-closed Slice 1 files;
- PR #356 owned acceptance-policy follow-up;
- PR #358 later identified and fixed a live-loop dirty-worktree retry defect in
  Builder core.

These lanes are evidence producers and dependencies, not permission to start a
second implementation. A consuming packet blocks with an exact missing-artifact
reason rather than recreating active work.

## Non-negotiable rules

1. **No new control plane.** No second Mission owner, queue, attempt/event store,
   budget ledger, approval path, merge path, scheduler, roadmap, or recommendation
   database.
2. **One execution owner.** Interactive and Builder may work in parallel, but
   never implement the same task simultaneously.
3. **Continue before starting within a lane.** Resume valid owned work before
   beginning another assignment or packet.
4. **Builder remains proactive.** Approved Builder work must not depend on Jacob
   typing `next` in a separate coding tool.
5. **Runtime evidence outranks prose.** A design, worker claim, screenshot, or
   model consensus is not product truth.
6. **One adapter boundary per imported platform.** Third-party code may render,
   capture, test, or evaluate; it may not own Kitty or Builder truth.
7. **Every dependency declares what it replaces.** Added capability without
   named avoided/deleted Kitty work is insufficient.
8. **Every proving slice is removable.** Failed spikes leave evidence and
   fixtures, not a permanent half-platform.
9. **No activity theatre.** Report outcomes, regressions, cost/waste, decisions,
   evidence gaps, and one next move—not commit counts or narration.
10. **Learning requires measurement.** Writing a wiki page or signal does not
    prove lower token use, faster work, or better code.
11. **Unknown stays unknown.** Missing tokens, time, cost, review, or regression
    evidence is `null`, not zero.
12. **No hidden promotion.** Workflow signals and effectiveness receipts never
    schedule Builder. Promotion requires a governed explicit operator action.

## Authority and storage boundary

| Concern | Existing authority | This program may do | This program must not do |
|---|---|---|---|
| Product direction | `docs/ROADMAP.md`, approved Mission/ADRs | package approved work as packets | create a second roadmap |
| Builder execution | initiative/packet/task/attempt/event/review records | execute explicitly approved manifests | infer queue truth from interactive state or edit SQLite |
| Interactive continuity | `.claude/STATE.md`, `.claude/HANDOFF.md` | preserve one interactive next action and parallel inventory | act as a Builder scheduler |
| Cross-tool knowledge | `~/kb` | store verified knowledge/corrections | copy execution state into another DB |
| Workflow signals | `~/kb/workflow-signals/` | record repeated evidence | auto-create work |
| KB effectiveness | `~/kb/metrics/kb-effectiveness.jsonl` | measure retrieval and outcomes | claim causation or mutate priorities |
| Code/publication | Git, GitHub checks/reviews, Builder publication rails | preserve SHA-bound evidence and authorized publication | fabricate green state or bypass gates |
| Product evidence | browser/runtime/test artifacts | capture, redact, replay, cite | treat images or reviewer consensus as acceptance |

## Dependency kill-switch record

Every proposed external dependency records:

```text
dependency
  name, repository, license, pinned_version_or_sha, disposition
purpose
  exact Kitty problem and owning workstream
replacement
  named Kitty files/components/work deleted or no longer built
boundary
  allowed inputs/outputs and forbidden authority
proof
  fixture or real task, measurements, acceptance evidence
maintenance
  upgrade cadence, patch count, generated code, notices
kill_conditions
  measurable reasons to reject or remove it
exit
  return path without loss of durable state
```

A dependency without replacement, boundary, proof, kill conditions, and exit is
rejected. “It has more features” is not evidence.

---

## 0. Separate execution lanes and measured learning

### Problem

Builder autonomy, interactive continuity, workflow signals, and the KB existed,
but their boundaries and effectiveness were not proven. The first implementation
incorrectly made bare interactive `next` select Builder packets. The KB also had
no causal/evidentiary bridge between entries read and resulting token/cost/code
quality outcomes.

### Binding design

Interactive continuation:

```text
bare next
  -> cold-start receipt
  -> validate current interactive checkpoint
  -> survey branches/worktrees/PRs and Builder read-only state for collision
  -> continue the current interactive assignment
  -> verify result or explicit no-op
  -> session-end when closing
  -> stop
```

Builder execution:

```text
approved initiative/packet
  -> Builder scheduler selects eligible packet
  -> isolated worker and lease
  -> implementation
  -> deterministic validation
  -> independent review
  -> evidence/publication/recovery
  -> continue unrelated eligible work
```

No step in interactive bare `next` applies or drains Builder.

### KB effectiveness receipt

Session-end writes one append-only receipt through:

```bash
python3 scripts/kb_effectiveness.py record --payload-json '<json>'
```

Normal storage:

```text
~/kb/metrics/kb-effectiveness.jsonl
```

The receipt records:

- stable session or Builder attempt identity;
- `execution_owner` and tool;
- task class and independently supported outcome;
- KB entries consulted, used, and stale/wrong;
- knowledge promoted to canonical tests/skills/ADRs/docs;
- known KB tokens, total tokens, cost, elapsed time, attempts, repair commits,
  regressions, first-pass independent approval;
- concrete duplicate work or correction prevented;
- branch/HEAD/task/initiative/packet/result references.

Unknown fields remain null. Identical receipts are idempotent; conflicting
session content, unknown keys, corrupt history, invalid subsets, and receipt-ID
mismatch fail loudly.

Rolling report:

```bash
python3 scripts/kb_effectiveness.py summary --window-days 30 --report
```

The report covers retrieval usefulness/staleness, evidence coverage, known
cost/tokens, attempts/repairs, first-pass approval, regressions, avoided
repetition, canonical promotion, and KB-used versus no-KB cohorts.

Cohort differences are observational and do not prove causation. The primary
optimization target is lower total cost and time per independently accepted
outcome without increased regressions—not raw token reduction.

### Workflow learning

Session-end may record up to three structured signals through
`scripts/session_learning.py`. Ordinary first occurrences remain observed;
repeated signals may promote; integrity/security/data-loss/fabricated-success/
queue-integrity/paid-waste incidents may promote immediately.

Promotion is evidence that a problem deserves ownership, not implementation
authority. Existing roadmap, Mission, initiative, queue, branch, PR, and issue
owners suppress duplication. A later explicit adapter may create at most one
Builder task per stable key. It never runs from bare `next` or automatically at
session-end.

### Corrective proving packets

`ktl-002-measured-learning-boundary-v1.json` contains:

1. interactive/Builder boundary fixtures;
2. KB-effectiveness receipt/report validation;
3. an end-to-end proof that Builder autonomy and interactive continuity operate
   in parallel without ownership duplication.

---

## 1. Mission Intake and Authority Projection

### Goal

Given a real request, produce a deterministic read-only projection of:

- authoritative sources and freshness;
- active work and collisions;
- blockers and recovery;
- allowed next and prohibited work;
- contradictions and stale decisions;
- required human decisions;
- evidence gaps.

The same source state produces the same semantic output and exactly one allowed
next or explicit no-op. It may draft a Mission revision but cannot execute it or
mutate Builder.

### Stop conditions

Stop if the projection creates another authority store, guesses missing
Builder state, chooses multiple next actions, or turns a conflict into a polished
execution prompt.

---

## 2. Independent Builder Operator Application

### Goal

Provide a separate process/URL/app over canonical Builder APIs and events. It
visualizes queue, attempts, evidence, budgets, blockers, recovery, and
publication, while the CLI remains the repair floor.

A reused Agent Canvas or other platform may render the fixture. It cannot own
queue, attempts, events, budgets, approvals, or publication.

### Proving slice

Require a verified `docs/mission/builder-map.md`, then compare embed, thin fork,
and native approaches against the same recorded Builder fixture with no external
backend. Measure adapter size, patched files, bundle/runtime cost,
accessibility, responsiveness, upgrade burden, exact work replaced, and kill
conditions.

### Stop conditions

Stop if the map is absent, the candidate requires another backend authority,
state is copied into frontend persistence, or the dependency avoids no named
Kitty work.

---

## 3. Product Evidence and Resilience Lab

### Goal

Capture one explicit local dogfood failure as a bounded redacted evidence bundle
and convert it into a deterministic failing-then-passing journey.

### Required bundle

- route, viewport, source/build/runtime identity;
- explicit recording indicator and optional note;
- recent bounded actions;
- console/network/runtime failures;
- screenshot when safe;
- redaction report;
- retention and one-action deletion;
- replay fixture and acceptance evidence.

No always-on recording, cloud upload, automatic issue/task, second browser
harness, or private prompt/file content in persisted artifacts.

---

## 4. Capability Registry Projection

### Goal

Project whether visible actions are `proven`, `preview`, `developer_only`,
`blocked`, or `hidden` from existing health, policy, viewport, and acceptance
evidence.

Evidence expiry or revision mismatch downgrades state. Overrides record actor,
reason, and expiry and cannot manufacture `proven`.

The registry is a projection, not a service-health database or general feature
flag system.

---

## 5. Kitty-Specific Model Evaluation Bench

### Goal

Evaluate models on 10–20 cited real Kitty failures/tasks: contradiction
detection, packet authoring, scoped coding, log debugging, independent review,
UX critique, primary-source research, browser operation, authority refusal, and
provider failure/resume.

Score task completion, evidence integrity, scope discipline, authority
compliance, recovery, cost, retries, variance, and fabricated-success rate.
Pin model/provider/version/settings and scorer versions. No benchmark result
changes live routing automatically; the compute governor remains authority.

Stop if synthetic trivia, verbosity-biased scoring, or maintenance cost dominates.

---

## 6. Product Studio

### Goal

Run independent specialist reviews over the same real journey evidence, then
produce a concise synthesis and convert useful exploratory findings into
deterministic tests or real-user validation plans.

Reuse axe-core, Lighthouse CI, Storybook, or exploratory agents only when the
reuse record names exact avoided work. Synthetic consensus is not acceptance.
High-severity findings require runtime evidence.

The first foundation requires at least three journeys, five independent role
reports, preserved disagreement, no more than ten synthesized recommendations,
and rediscovery of known defects plus at least one useful new finding.

---

## 7. Reuse-First Chat Landing Review

### Goal

Consume, not duplicate, the active Chat reuse worker. If its artifact is absent,
block. If present, independently verify:

```text
send
  -> incremental stream
  -> durable persistence
  -> browser reload
  -> Kitty restart
  -> identical conversation resume
```

Also verify interrupted-stream retry without duplicate turns or fabricated
success on the phone viewport.

Record source, license, pin, exported primitives, exact Kitty work replaced, and
remaining custom adapter. Reject any second conversation, memory, routing, or
permission authority.

---

## 8. Reuse Governance

### Goal

Maintain a small validated registry of adopted, spike-only, rejected, and
pending dependencies. Detect conflicting authority/replacement claims and
require explicit supersession.

The registry cannot install packages, choose product priority, or become a
roadmap.

---

## Verification and reporting

Every packet must provide:

- exact base and result identity;
- allowed paths and observed changed paths;
- runnable acceptance commands and exact results;
- non-vacuous fail-before/pass-after proof when applicable;
- runtime evidence for runtime claims;
- independent review bound to the reviewed SHA;
- provider/model/cost evidence when known;
- explicit unknowns and cleanup state;
- one owner and one recovery/next action.

A packet is not complete because code exists, a UI boots, a model approves, or a
PR URL exists.

## Removal conditions

Remove or revise any slice when it:

- creates another authority;
- duplicates active work;
- increases context/cost without improving independently accepted outcomes;
- repeatedly produces stale or unused KB entries;
- depends on unverifiable/manual-only acceptance;
- cannot fail closed;
- cannot be upgraded or removed without losing durable state;
- requires paid fallback not explicitly authorized; or
- causes interactive and Builder ownership to become ambiguous.
