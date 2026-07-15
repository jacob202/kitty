---
type: adr
title: "Documentation Is Architecture"
status: accepted
owner: jacob
primary_purpose: The repository is an engineered knowledge system with structured layers, traceability, and machine-enforced governance
derives_from:
  - docs/CONSTITUTION.md
  - docs/adr/0017-kitty-is-engineering-operating-system.md
implements:
  - docs/CONSTITUTION.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR-0018: Documentation Is Architecture; Repository Governance Foundation

**Date:** 2026-07-14
**Status:** Accepted

## Context

The repository accumulated Markdown files organically: duplicate philosophy, orphaned specs, stale status, no ownership. The alternative to "docs cleanup" was treating documentation as an engineered system with explicit ownership, traceability, governance, and automated enforcement.

## Decision

1. **Documentation is architecture.** Markdown files are implementation details. The documentation architecture is the actual product.
2. **Layered hierarchy:** VISION → CONSTITUTION → ROADMAP → ARCHITECTURE → ADRs → Implementation.
3. **YAML frontmatter is mandatory** for all foundational documents.
4. **SYSTEM_MAP is auto-generated** from frontmatter. CI fails if stale.
5. **Machine enforcement over policy:** `kitty docs lint` validates frontmatter, traceability, broken references.
6. **Every foundational document has one primary purpose.**
7. **Duplicate philosophy is banned.** Reference the source; do not copy.

## Consequences

All foundational documents carry YAML frontmatter. CI enforces documentation integrity on every push. Orphan documents and stale artifacts are caught mechanically. "Documentation cleanup" as a recurring initiative is eliminated — governance prevents drift.
