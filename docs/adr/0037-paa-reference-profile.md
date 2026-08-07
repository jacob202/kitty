# ADR 0037: Adopt PAA as Kitty's Reference Architecture and Portability Profile

**Status:** Accepted  
**Date:** 2026-08-03  
**Decision authority:** Jacob explicitly directed the project to adopt the
Personal AI Architecture approach after reviewing BrainDrive and PAA.  
**Numbering note:** originally filed as ADR 0028; renumbered 2026-08-07 because
0028 was independently reused by "Commodity Software Precedence" and this file
was never added to the ADR index, so the number collided silently. No decision
content changed.

## Context

Kitty and BrainDrive independently converged on a similar product direction:
a local-first personal AI that owns durable user context, works across
replaceable models and clients, and helps turn goals into plans and continued
follow-through.

BrainDrive is built on the open, MIT-licensed Personal AI Architecture (PAA).
PAA provides something Kitty lacks as one coherent artifact: explicit
component responsibilities, owner-memory guarantees, adapter boundaries,
schemas, swap tests, deployment invariants, and a lock-in checklist.

Kitty already implements much of the substance:

- local owner-controlled deployment;
- a Gateway API serving multiple clients;
- a unified memory read boundary;
- interchangeable local and cloud model routes;
- tool, connector, MCP, and worker adapters;
- durable KittyBuilder execution, evidence, and recovery;
- life-first product behavior and project continuity.

A replacement or migration to BrainDrive would discard Kitty's strongest and
most distinctive systems. Blindly declaring Kitty PAA-conformant would be
false. PAA requires a content-agnostic Gateway and generic Agent Loop, while
accepted ADR 0003 deliberately makes Kitty's Gateway the product and places
context assembly, personal behavior, domain policy, and model routing behind
it.

The project therefore needs a precise adoption decision: use PAA to strengthen
portability and boundaries without erasing Kitty's product layer or creating a
new framework migration.

## Decision

Kitty adopts the Personal AI Architecture as its **external reference
architecture and executable portability/lock-in profile**, subject to the
following rules.

### 1. PAA is a reference profile, not a replacement codebase

Kitty will not be rebuilt on BrainDrive or the PAA TypeScript template merely
to resemble the reference implementation. PAA documents the guarantees Kitty
chooses to meet; Kitty remains the implementation.

New framework, runtime, or language dependencies require their own evidence and
ADR. Architectural resemblance is not proof of conformance.

### 2. Kitty adopts these PAA guarantees

Kitty will make the following claims executable:

- owner memory is portable in open, inspectable formats;
- canonical owner data is distinguishable from derived indexes, caches,
  secrets, and execution evidence;
- full export/import works on a fresh installation and reports omissions;
- clients remain replaceable through versioned Gateway contracts;
- model/provider choices remain adapter/configuration decisions;
- tools can be added or removed without changing core architecture;
- local single-machine operation remains supported;
- localhost is the default network posture;
- offline operation is testable when local models/tools are configured;
- outbound network behavior is explicit rather than silent;
- boundary payloads are versioned and schema-tested;
- client-facing streamed errors use a safe fixed taxonomy;
- storage/auth changes preserve tested backup, restore, and migration safety;
- PRs affecting these guarantees pass an applicable lock-in review.

### 3. Kitty defines a Principal/Application layer

PAA's strict Gateway and Agent Loop responsibilities do not describe Kitty's
accepted product architecture. Kitty therefore defines a logical
**Principal/Application layer** that owns:

- user intent interpretation;
- selective context assembly;
- personal identity, preferences, and life-first policy;
- domain and strategy selection;
- model/provider policy;
- permission and approval requests;
- project/resume-loop behavior;
- Mission authoring for KittyBuilder;
- presentation and teach-back of results.

The external Gateway contract routes clients into this layer. A replaceable,
generic Agent Loop may execute model/tool turns behind it. These layers may
remain physically colocated in the Python Gateway package initially, but their
responsibility boundary must become explicit and testable before Kitty claims
that the Agent Loop is swappable.

This decision **amends the interpretation of ADR 0003 without superseding it**:
the Gateway service remains Kitty's product backend and deployment boundary,
but not every responsibility inside that process is classified as PAA Gateway
behavior.

### 4. Deliberate deviations are first-class evidence

Kitty will maintain a pinned alignment matrix using these statuses:
`PASS`, `PARTIAL`, `FAIL`, `DELIBERATE DEVIATION`, and `UNKNOWN`.

A PAA requirement that Kitty intentionally declines must be recorded with its
reason, consequence, and replacement guarantee. It must not be hidden through
renaming or called conformant.

The initial matrix is `docs/audit/PAA_ALIGNMENT_2026-08.md`.

### 5. Owner Memory becomes an explicit product boundary

Kitty will define one machine-readable owner-data manifest covering all
canonical personal state, including conversations, memory, journal, projects,
preferences, todos, captures, signals, imported knowledge sources, and artifact
metadata.

Every store will be classified as one of:

- canonical owner memory;
- derived/rebuildable data;
- secret;
- cache;
- operational/execution evidence.

Existing `memory_graph`, `storage_sync`, and PR #388's backup/restore substrate
will be extended rather than replaced by a competing memory or backup system.

### 6. Open WebUI and every other client remain replaceable

ADR 0027 authorizes Open WebUI only as a shell. No canonical Kitty authority,
provider policy, personal memory, project state, Tutor behavior, tool policy,
or Builder execution state may become trapped in that shell.

Client-replaceability evidence must include stopping/removing Open WebUI while
Kitty Gateway, owner memory, projects, tools, and another supported client
remain functional.

### 7. KittyBuilder remains a Kitty extension outside PAA's foundation

PAA's four-component foundation does not replace KittyBuilder. KittyBuilder
continues to own durable engineering execution state: Missions, initiatives,
packets, tasks, attempts, leases, workers, worktrees, validation, reviews,
publication, budgets, recovery, and evidence.

The only product control boundary remains:

```text
Kitty Principal/Application
  -> versioned approved Mission
  -> KittyBuilder
  -> structured Result/Evidence
  -> Kitty Principal/Application
```

PAA work may improve contracts and portability but must not create a second
Builder state machine or move execution authority into an agent framework.

### 8. Conformance is profile-specific and evidence-gated

Kitty may claim only **Kitty PAA profile** results until every strict PAA
requirement is met without deviation.

The executable profile will include provider/model/tool/client swaps, complete
owner-memory export/import, schema validation, safe errors, localhost defaults,
o-silent-outbound checks, offline operation, and Open WebUI removal.

A document, interface resemblance, unit test with mocks, or reference
implementation result is not sufficient evidence by itself.

### 9. BrainDrive is a harvest source

BrainDrive will be evaluated for demonstrated improvements in:

- interview -> structured spec -> action plan -> continued partnership;
- life-area and project onboarding;
- backup/restore settings and owner-data explanations;
- one-command install/update/backup/restore/support bundles;
- recovery and diagnostics UX.

Each item receives an `ADOPT`, `ADAPT`, `DEFER`, or `REJECT` disposition with
Kitty-specific evidence. BrainDrive remains neither authority nor replacement.

## Consequences

### Easier

- Kitty gains one coherent portability and anti-lock-in target.
- Open WebUI and future clients have a clear non-authority boundary.
- Provider, tool, memory, and client refactors can be judged through swap tests
  rather than architecture prose.
- Backup/restore work gains a complete owner-data definition and semantic parity
  finish line.
- Deliberate product differences can be preserved honestly.

### Harder

- Existing mixed responsibilities must be documented and gradually separated
  behind real contracts.
- Complete export/import is broader than archiving `data/` or selected SQLite
  tables.
- Auth cannot remain an implicit collection of route/tool checks forever.
- Offline and no-silent-outbound claims require real runtime tests.
- Every new provider/client/tool shortcut must preserve swappability evidence.

### Off-limits

- claiming strict PAA conformance from architectural similarity;
- replacing Kitty with BrainDrive or the PAA template without a separate,
  evidence-backed decision;
- moving canonical Kitty state or policy into Open WebUI;
- creating a parallel memory platform beside `memory_graph` and current stores;
- creating a second execution control plane beside KittyBuilder;
- adding ignorable lock-in CI checks while branch protection still allows red
  checks to be merged;
- treating derived vector indexes, caches, secrets, and owner memory as one
  undifferentiated backup blob.

## Evidence and follow-up

- Baseline matrix: `docs/audit/PAA_ALIGNMENT_2026-08.md`
- Work breakdown and acceptance: issue #389
- Task-level agent-pattern harvest: issue #390
- Open WebUI shell boundary: ADR 0027 on PR #384
- Backup/restore substrate: PR #388
