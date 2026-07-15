---
type: index
title: "Kitty Documentation"
status: canonical
owner: jacob
primary_purpose: Entry point and map for the entire documentation hierarchy
derives_from:
  - docs/VISION.md
  - docs/CONSTITUTION.md
implements: []
referenced_by:
  - START_HERE.md
  - AGENTS.md
  - README.md
  - docs/knowledge/KNOWLEDGE_MODEL.md
review_cycle: quarterly
---

# Kitty Documentation

This is the entry point for all documentation in the Kitty repository. Documents are organized into a layered hierarchy where each layer derives from the one above it.

## Hierarchy

```
VISION.md              ← Why Kitty exists (permanent missions)
  └── CONSTITUTION.md  ← Engineering doctrine (immutable principles)
       └── architecture/   ← Target architecture, organizational model
            └── builder/    ← Builder operating model
            └── knowledge/  ← Knowledge model, historical recovery
            └── ADRs    ← Specific decisions
            └── engineering/  ← Builder, operational guides
            └── product/      ← Product architecture, feature docs
            └── operations/   ← Status, learnings, workflows
            └── research/     ← Design specs, explorations
```

## Foundational Documents

| Document | Purpose |
|---|---|
| [`VISION.md`](VISION.md) | Why Kitty exists, permanent missions |
| [`CONSTITUTION.md`](CONSTITUTION.md) | Immutable engineering principles |
| [`ROADMAP.md`](ROADMAP.md) | Strategic direction and phased plan |
| [`INDEX.md`](INDEX.md) | Single entry point — machine-readable documentation index |
| [`CANONICAL_SOURCES.md`](CANONICAL_SOURCES.md) | Every concept mapped to its one canonical home |
| [`DECISIONS.md`](DECISIONS.md) | ADR index — all settled decisions |
| [`audit-migration-table.md`](audit-migration-table.md) | Migration decisions from the governance restructure |

## Architecture

Target architecture, reference models, and permanent subsystem definitions.

| Document | Purpose |
|---|---|
| [`architecture/REFERENCE_ARCHITECTURE.md`](architecture/REFERENCE_ARCHITECTURE.md) | Target architecture independent of current implementation |
| [`architecture/ORGANIZATIONAL_MODEL.md`](architecture/ORGANIZATIONAL_MODEL.md) | Permanent offices, authority boundaries, and governance |
| [`architecture/SYSTEM_INTERACTIONS.md`](architecture/SYSTEM_INTERACTIONS.md) | Subsystem interfaces, ownership boundaries, and interaction contracts |
| [`architecture/CAPABILITY_MODEL.md`](architecture/CAPABILITY_MODEL.md) | Permanent capabilities, maturity levels, and dependency graph |
| [`architecture/SYSTEM_DESIGN_PRINCIPLES.md`](architecture/SYSTEM_DESIGN_PRINCIPLES.md) | Engineering principles for subsystem design |

## Builder

Builder operating model, contracts, and execution standards.

| Document | Purpose |
|---|---|
| [`builder/BUILDER_OPERATING_MODEL.md`](builder/BUILDER_OPERATING_MODEL.md) | How Builder operates as an engineering organization |
| [`builder/BUILDER_PACKET_LIFECYCLE.md`](builder/BUILDER_PACKET_LIFECYCLE.md) | Task/run/attempt state machines |
| [`builder/BUILDER_EXECUTION_PIPELINE.md`](builder/BUILDER_EXECUTION_PIPELINE.md) | Canonical execution pipeline |
| [`builder/BUILDER_EVENT_MODEL.md`](builder/BUILDER_EVENT_MODEL.md) | Event model — producers, consumers, payloads |
| [`builder/BUILDER_RUNTIME_GAP_ANALYSIS.md`](builder/BUILDER_RUNTIME_GAP_ANALYSIS.md) | Runtime vs model gap analysis |

## Knowledge

Semantic models, historical recovery, and organizational learning.

| Document | Purpose |
|---|---|
| [`knowledge/KNOWLEDGE_MODEL.md`](knowledge/KNOWLEDGE_MODEL.md) | Canonical vocabulary for organizational knowledge |
| [`knowledge/HISTORICAL_KNOWLEDGE_RECOVERY.md`](knowledge/HISTORICAL_KNOWLEDGE_RECOVERY.md) | Methodology for mining historical artifacts into durable knowledge |

## Repository

Repository lifecycle, evolution, and governance.

| Document | Purpose |
|---|---|
| [`repository/REPOSITORY_EVOLUTION.md`](repository/REPOSITORY_EVOLUTION.md) | How the repository evolves while preserving architectural integrity |

## Engineering

Runtime architecture, Builder documentation, and operational guides.

| Document | Purpose |
|---|---|
| [`engineering/ARCHITECTURE.md`](engineering/ARCHITECTURE.md) | Canonical runtime architecture |
| [`engineering/KITTYBUILDER_QUICKSTART.md`](engineering/KITTYBUILDER_QUICKSTART.md) | Builder queue operations |
| [`engineering/KITTYBUILDER_ORCA_SETUP.md`](engineering/KITTYBUILDER_ORCA_SETUP.md) | Orca worktree setup |
| [`engineering/KITTYBUILDER_ORCHESTRATOR_PHASE1A.md`](engineering/KITTYBUILDER_ORCHESTRATOR_PHASE1A.md) | Builder orchestrator architecture |
| [`engineering/KITTYBUILDER_SELF_BUILDING_MVP.md`](engineering/KITTYBUILDER_SELF_BUILDING_MVP.md) | Self-building roadmap |

## Product

Product architecture, feature documentation, and user-facing guides.

| Document | Purpose |
|---|---|
| [`product/KITTY_PRODUCT_ARCHITECTURE.md`](product/KITTY_PRODUCT_ARCHITECTURE.md) | Definitive product architecture |
| [`product/BLUEPRINT.md`](product/BLUEPRINT.md) | Product direction and execution plan |
| [`product/QUICK_CAPTURE.md`](product/QUICK_CAPTURE.md) | Quick capture how-to |
| [`product/SIRI_SHORTCUT.md`](product/SIRI_SHORTCUT.md) | Siri shortcut setup |
| [`product/USER_PREFS.md`](product/USER_PREFS.md) | User preferences |

## Operations

Living status, learnings, workflows, and agent protocols.

| Document | Purpose |
|---|---|
| [`operations/PROJECT_STATUS.md`](operations/PROJECT_STATUS.md) | Current branch, shipped work, test state |
| [`operations/LEARNINGS.md`](operations/LEARNINGS.md) | Hard lessons and guardrails |
| [`operations/AGENT_RUNTIME.md`](operations/AGENT_RUNTIME.md) | Agent entry/exit protocol |
| [`operations/WORKFLOW.md`](operations/WORKFLOW.md) | PR review workflow |

## Research

Design specs, explorations, and candidate architectures.

| Document | Purpose |
|---|---|
| [`research/council-routing-design.md`](research/council-routing-design.md) | Council routing spec |
| [`research/tutor-design.md`](research/tutor-design.md) | Tutor RAG spec |

## Architecture Decision Records

One decision per file in [`adr/`](adr/). See [`DECISIONS.md`](DECISIONS.md) for the index.

## Generated Artifacts

| Artifact | Purpose |
|---|---|
| [`SYSTEM_MAP.md`](SYSTEM_MAP.md) | Auto-generated document relationship map |
| [`codemap/`](codemap/) | Auto-generated code maps |

## Archives

| Directory | Purpose |
|---|---|
| [`archive/`](archive/) | Superseded documents preserved for reference |
| [`retired/`](retired/) | Historical documents no longer active |

## Governance

Documentation governance rules are defined in [`GOVERNANCE.md`](GOVERNANCE.md).

Every foundational document uses YAML frontmatter with: `type`, `title`, `status`, `owner`, `primary_purpose`, `derives_from`, `implements`, `referenced_by`, and `review_cycle`.

The [`SYSTEM_MAP.md`](SYSTEM_MAP.md) is auto-generated from frontmatter and validated by `kitty docs lint`.
