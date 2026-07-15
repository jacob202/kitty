---
type: record
title: "Audit Migration Table"
status: canonical
owner: jacob
primary_purpose: Disposition for every document that existed before the Repository Governance Foundation restructuring
derives_from:
  - docs/GOVERNANCE.md
review_cycle: as needed
---

# Audit Migration Table

Disposition for every document that existed before the Repository Governance Foundation restructuring (2026-07-14).

## Disposition Key

| Code | Meaning |
|---|---|
| KEEP | Retained in current location |
| MERGE | Consolidated into another document |
| ARCHIVE | Moved to docs/archive/ for reference |
| SUPERSEDE | Replaced by a new document in a new location |
| RENAME | Moved to a new subdirectory |

## Documents

| Original Path | New Path | Disposition | Notes |
|---|---|---|---|
| `docs/VISION.md` | `docs/VISION.md` | KEEP | Foundational |
| `docs/CONSTITUTION.md` | `docs/CONSTITUTION.md` | KEEP | Foundational |
| `docs/ROADMAP.md` | `docs/ROADMAP.md` | KEEP | Foundational |
| `docs/GOVERNANCE.md` | `docs/GOVERNANCE.md` | KEEP | Foundational |
| `docs/DECISIONS.md` | `docs/DECISIONS.md` | KEEP | Foundational |
| `docs/README.md` | `docs/README.md` | KEEP | Rebuilt |
| `docs/INDEX.md` | `docs/INDEX.md` | KEEP | New |
| `docs/CANONICAL_SOURCES.md` | `docs/CANONICAL_SOURCES.md` | KEEP | New |
| `docs/KNOWLEDGE_MODEL.md` | `docs/knowledge/KNOWLEDGE_MODEL.md` | SUPERSEDE | Moved, merged with reference architecture |
| `docs/NORTH_STAR.md` | `docs/VISION.md` | MERGE | Superseded by VISION.md |
| `docs/KITTY_HUB.md` | `docs/archive/KITTY_HUB.md` | ARCHIVE | No longer active |
| `docs/OPERATOR_STRATEGY.md` | `docs/archive/OPERATOR_STRATEGY.md` | ARCHIVE | Superseded |
| `docs/ARCHITECTURE.md` | `docs/engineering/ARCHITECTURE.md` | RENAME | Engineering section |
| `docs/AGENT_HANDOFF.md` | `docs/operations/AGENT_HANDOFF.md` | RENAME | Operations section |
| `docs/AGENT_RUNTIME.md` | `docs/operations/AGENT_RUNTIME.md` | RENAME | Operations section |
| `docs/LEARNINGS.md` | `docs/operations/LEARNINGS.md` | RENAME | Operations section |
| `docs/PROJECT_STATUS.md` | `docs/operations/PROJECT_STATUS.md` | RENAME | Operations section |
| `docs/WORKFLOW.md` | `docs/operations/WORKFLOW.md` | RENAME | Operations section |
| `docs/BLUEPRINT.md` | `docs/product/BLUEPRINT.md` | RENAME | Product section |
| `docs/KITTY_PRODUCT_ARCHITECTURE.md` | `docs/product/KITTY_PRODUCT_ARCHITECTURE.md` | RENAME | Product section |
| `docs/QUICK_CAPTURE.md` | `docs/product/QUICK_CAPTURE.md` | RENAME | Product section |
| `docs/SIRI_SHORTCUT.md` | `docs/product/SIRI_SHORTCUT.md` | RENAME | Product section |
| `docs/USER_PREFS.md` | `docs/product/USER_PREFS.md` | RENAME | Product section |
| `docs/council-routing-design.md` | `docs/research/council-routing-design.md` | RENAME | Research section |
| `docs/tutor-design.md` | `docs/research/tutor-design.md` | RENAME | Research section |
| `docs/KITTYBUILDER_ORCA_SETUP.md` | `docs/engineering/KITTYBUILDER_ORCA_SETUP.md` | RENAME | Engineering section |
| `docs/KITTYBUILDER_ORCHESTRATOR_PHASE1A.md` | `docs/engineering/KITTYBUILDER_ORCHESTRATOR_PHASE1A.md` | RENAME | Engineering section |
| `docs/KITTYBUILDER_QUICKSTART.md` | `docs/engineering/KITTYBUILDER_QUICKSTART.md` | RENAME | Engineering section |
| `docs/KITTYBUILDER_SELF_BUILDING_MVP.md` | `docs/engineering/KITTYBUILDER_SELF_BUILDING_MVP.md` | RENAME | Engineering section |

## New Documents (Governance Foundation Era)

| Path | Type | Purpose |
|---|---|---|
| `docs/architecture/REFERENCE_ARCHITECTURE.md` | architecture | Target architecture |
| `docs/architecture/ORGANIZATIONAL_MODEL.md` | model | Offices and governance |
| `docs/architecture/SYSTEM_INTERACTIONS.md` | architecture | Subsystem contracts |
| `docs/architecture/CAPABILITY_MODEL.md` | architecture | Capability maturity |
| `docs/knowledge/KNOWLEDGE_MODEL.md` | model | Canonical vocabulary |
| `docs/knowledge/HISTORICAL_KNOWLEDGE_RECOVERY.md` | methodology | Recovery methodology |
| `docs/builder/BUILDER_OPERATING_MODEL.md` | model | Builder operating model |
| `docs/repository/REPOSITORY_EVOLUTION.md` | methodology | Evolution framework |
| `docs/adr/0017-kitty-is-engineering-operating-system.md` | adr | Organizational decision |
| `docs/adr/0018-documentation-as-architecture.md` | adr | Governance decision |
| `docs/adr/0019-knowledge-model-prerequisite.md` | adr | Knowledge decision |
