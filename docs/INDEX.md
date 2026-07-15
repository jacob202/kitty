---
type: index
title: "Kitty Documentation Index"
status: canonical
owner: jacob
primary_purpose: Single entry point for all documentation — machine-readable, canonical, non-duplicative
derives_from:
  - docs/VISION.md
  - docs/CONSTITUTION.md
referenced_by:
  - AGENTS.md
  - CLAUDE.md
  - docs/README.md
review_cycle: as needed
---

# Kitty Documentation Index

This is the single entry point for all documentation in the Kitty repository. Every enduring idea has exactly one canonical home. Every other document references it. None duplicate it.

## Constitutional Rule

No document may duplicate content that exists in another canonical document. Reference, do not copy. If a concept deserves explanation, it deserves a canonical home. Every document that needs that concept points to it.

## Entry Points

| Role | Entry Point |
|---|---|
| Agent instructions | `AGENTS.md` |
| Claude Code bootstrap | `CLAUDE.md` |
| Human-readable map | `docs/README.md` |

## Canonical Documents

### Foundation

| Document | Purpose | Status |
|---|---|---|
| `VISION.md` | Why Kitty exists, permanent missions | canonical |
| `CONSTITUTION.md` | Immutable engineering principles | canonical |
| `ROADMAP.md` | Strategic direction and phased plan | canonical |
| `GOVERNANCE.md` | Documentation ownership, review, and amendment | canonical |
| `DECISIONS.md` | ADR index | canonical |
| `CANONICAL_SOURCES.md` | Every concept mapped to its one canonical home | canonical |

### Architecture

| Document | Purpose | Status |
|---|---|---|
| `architecture/REFERENCE_ARCHITECTURE.md` | Target architecture | draft |
| `architecture/ORGANIZATIONAL_MODEL.md` | Offices, authority boundaries, governance | draft |
| `architecture/SYSTEM_INTERACTIONS.md` | Subsystem interfaces and interaction contracts | draft |
| `architecture/CAPABILITY_MODEL.md` | Capabilities, maturity levels, dependency graph | draft |
| `architecture/SYSTEM_DESIGN_PRINCIPLES.md` | Engineering principles for subsystem design | draft |

### Knowledge

| Document | Purpose | Status |
|---|---|---|
| `knowledge/KNOWLEDGE_MODEL.md` | Canonical vocabulary | draft |
| `knowledge/HISTORICAL_KNOWLEDGE_RECOVERY.md` | Mining historical artifacts into knowledge | draft |

### Builder

| Document | Purpose | Status |
|---|---|---|
| `builder/BUILDER_OPERATING_MODEL.md` | Builder as engineering organization | draft |

### Repository

| Document | Purpose | Status |
|---|---|---|
| `repository/REPOSITORY_EVOLUTION.md` | Repository lifecycle and evolution | draft |

### Runtime

| Document | Purpose | Status |
|---|---|---|
| `engineering/ARCHITECTURE.md` | Canonical runtime architecture | canonical |

### Operations

| Document | Purpose | Status |
|---|---|---|
| `operations/PROJECT_STATUS.md` | Current branch, shipped work, test state | canonical |
| `operations/LEARNINGS.md` | Hard lessons and guardrails | canonical |

### ADRs

| Resource | Purpose |
|---|---|
| `adr/README.md` | Full ADR index |
| `adr/0000-template.md` | Template for new ADRs |

### Generated

| Artifact | Purpose | Generator |
|---|---|---|
| `SYSTEM_MAP.md` | Auto-generated document relationship map | `python3 scripts/docs_system_map.py` |

## What Not to Duplicate

Architecture explanations → `docs/architecture/`. Knowledge Model definitions → `docs/knowledge/KNOWLEDGE_MODEL.md`. Constitutional principles → `docs/CONSTITUTION.md`. Vision and missions → `docs/VISION.md`. Organizational structure → `docs/architecture/ORGANIZATIONAL_MODEL.md`. Builder rules → `docs/builder/BUILDER_OPERATING_MODEL.md`. Historical recovery methodology → `docs/knowledge/HISTORICAL_KNOWLEDGE_RECOVERY.md`.
