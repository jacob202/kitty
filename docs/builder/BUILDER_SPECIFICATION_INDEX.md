---
type: index
title: "Builder Specification Index"
status: canonical
owner: jacob
primary_purpose: Which Builder specification owns which concepts — a single entry point for all Builder implementation contracts
derives_from:
  - docs/builder/BUILDER_OPERATING_MODEL.md
referenced_by:
  - docs/builder/BUILDER_PACKET_LIFECYCLE.md
  - docs/builder/BUILDER_EXECUTION_PIPELINE.md
  - docs/builder/BUILDER_EVENT_MODEL.md
  - docs/builder/BUILDER_RUNTIME_GAP_ANALYSIS.md
review_cycle: quarterly
---

# Builder Specification Index

The Builder subsystem has five documents. Each owns a specific concept domain. No concept should be defined in more than one document.

## Document Map

```
BUILDER_OPERATING_MODEL.md   ← Philosophy: how Builder thinks
         │
         ├── BUILDER_PACKET_LIFECYCLE.md    ← States: what states exist,
         │                                       what transitions are legal
         │
         ├── BUILDER_EXECUTION_PIPELINE.md   ← Stages: what happens in order,
         │                                       entry/exit criteria per stage
         │
         ├── BUILDER_EVENT_MODEL.md          ← Events: what events fire,
         │                                       who produces/consumes them
         │
         └── BUILDER_RUNTIME_GAP_ANALYSIS.md ← Gaps: what's missing vs model
```

## Concept Ownership

| Concept | Canonical Document | Notes |
|---|---|---|
| Builder philosophy, principles, prime directive | `BUILDER_OPERATING_MODEL.md` | The "why" and "how" |
| Builder decision boundary | `BUILDER_OPERATING_MODEL.md` | §4 — Allowed/Not Allowed |
| Builder loop stages (names) | `BUILDER_OPERATING_MODEL.md` | §5 — Pipeline overview |
| Task states and legal transitions | `BUILDER_PACKET_LIFECYCLE.md` | §Task State Machine |
| Run states and legal transitions | `BUILDER_PACKET_LIFECYCLE.md` | §Run Lifecycle |
| Attempt states and verdict | `BUILDER_PACKET_LIFECYCLE.md` | §Attempt Lifecycle |
| Recovery paths | `BUILDER_PACKET_LIFECYCLE.md` | §Recovery Paths |
| Escalation contract | `BUILDER_PACKET_LIFECYCLE.md` (definition) + `BUILDER_EXECUTION_PIPELINE.md` §2 (trigger stage) | Single definition, pipeline-stage reference |
| Pipeline stages (detailed) | `BUILDER_EXECUTION_PIPELINE.md` | Entry/exit criteria, owner, I/O per stage |
| Shadow mode constraint | `BUILDER_EXECUTION_PIPELINE.md` | §Shadow Mode Constraint |
| Task events (`created`, `claimed`, `released`, `report_attached`, `pr_attached`, `pr_updated`) | `BUILDER_EVENT_MODEL.md` | Producer, consumer, payload, ordering, idempotency |
| Run events (`starting`, `running`, `exited`, `failed`, `timeout`, `cancelled`, `interrupted`, `lease_lost`, `scope_violation`) | `BUILDER_EVENT_MODEL.md` | Producer, consumer, payload |
| Initiative events | `BUILDER_EVENT_MODEL.md` | `initiative_applied`, `initiative_status_changed` |
| Event consumption patterns | `BUILDER_EVENT_MODEL.md` | How events are consumed (CLI, initiative rollup) |
| Runtime gaps vs model | `BUILDER_RUNTIME_GAP_ANALYSIS.md` | Categorized as Required, Implementation Choice, Future Capability, Implemented |
| Contract validation completeness gap | `BUILDER_RUNTIME_GAP_ANALYSIS.md` | §Gap Analysis → Required |
| Escalation implementation gap | `BUILDER_RUNTIME_GAP_ANALYSIS.md` | §Gap Analysis → Required |
| Knowledge Model alignment status | `BUILDER_RUNTIME_GAP_ANALYSIS.md` | Future capabilities dependent on KM |

## Cross-Reference Convention

- Pipeline stages reference Event Model for events produced (`BUILDER_EVENT_MODEL.md §Task Events`)
- Event Model references Pipeline for stage ownership (`Pipeline stage: §N`)
- Lifecycle is referenced by Pipeline and events as authoritative for state/transition legality
- Gap Analysis references all other specs to identify missing coverage

## What Not to Define Here

- Knowledge Model concepts (Evidence, Finding, Knowledge, Pattern, Doctrine, Judgment, Receipt) → `docs/knowledge/KNOWLEDGE_MODEL.md`
- Organizational responsibilities (Planning, Builder, Review, Operations Offices) → `docs/architecture/ORGANIZATIONAL_MODEL.md`
- Subsystem interaction contracts → `docs/architecture/SYSTEM_INTERACTIONS.md`
- Repository code structure → `docs/engineering/ARCHITECTURE.md`
- Initiative manifest schema → `gateway/builder_initiative.py` docstring
- Implementation details (SQLite schema, worktree layout) → gateway source docstrings
