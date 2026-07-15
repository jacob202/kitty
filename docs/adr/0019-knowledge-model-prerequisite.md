---
type: adr
title: "Knowledge Model Is a Foundational Prerequisite"
status: accepted
owner: jacob
primary_purpose: A canonical vocabulary and semantic model must exist before any new subsystem that reasons about knowledge
derives_from:
  - docs/CONSTITUTION.md
  - docs/adr/0017-kitty-is-engineering-operating-system.md
implements:
  - docs/knowledge/KNOWLEDGE_MODEL.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR-0019: Knowledge Model Is a Foundational Prerequisite

**Date:** 2026-07-14
**Status:** Accepted

## Context

Kitty is becoming an organization that converts experience into reusable judgment. But the vocabulary is informal: "knowledge," "insight," "lesson," "pattern," "finding" are used interchangeably. Without canonical definitions, no subsystem can reliably process, store, or reason about what the organization knows.

## Decision

1. **A canonical Knowledge Model must exist** before any subsystem that reads, writes, or reasons about organizational knowledge.
2. **The Knowledge Model defines vocabulary only** — not a database, graph engine, or AI system.
3. **Dependency order is fixed:** Builder Operating Model, Organizational Model, and Historical Knowledge Recovery depend on the Knowledge Model.
4. **Historical Knowledge Recovery is a separate initiative** downstream of the Knowledge Model.

## Consequences

`docs/knowledge/KNOWLEDGE_MODEL.md` is ratified as the canonical vocabulary. No database, graph engine, or AI is required — only the semantic model. Any subsystem that uses knowledge terms must reference the canonical definitions. Historical chat mining becomes evidence processing, not knowledge generation.

A semantic alignment pass (2026-07-14) reconciled existing code terminology: `KNOWLEDGE_DIR` and `Source.KNOWLEDGE` are storage/index categories (Evidence), not Knowledge Model semantics. The journal `reflection` theme is user-facing journaling, not architectural Reflection. Seven model concepts (Doctrine, Pattern, Judgment, Receipt, Outcome, Finding, Observation) have no runtime representation. All clarified via docstrings — no renames, no new systems.
