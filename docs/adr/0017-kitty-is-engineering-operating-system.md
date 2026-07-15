---
type: adr
title: "Kitty Is an Engineering Operating System"
status: accepted
owner: jacob
primary_purpose: Kitty is an organization that converts experience into engineering judgment — not a chatbot, not an agent framework
derives_from:
  - docs/CONSTITUTION.md
  - docs/VISION.md
supersedes:
  - docs/adr/0010-kitty-is-personal-operating-layer.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR-0017: Kitty Is an Engineering Operating System

**Date:** 2026-07-14
**Status:** Accepted

## Context

ADR-0010 established Kitty as a "personal operating layer" — a product identity. But the working hypothesis has changed. Implementation is rapidly becoming inexpensive, while architectural judgment remains expensive. Kitty should optimize for preserving, improving, distributing, and reusing judgment.

## Decision

1. **Kitty is an Engineering Operating System.** It is an organization — not a chatbot, coding agent, orchestration framework, memory system, or documentation system. Those are subsystems.
2. **Organizational learning is the product.** Every engineering action should leave the organization more capable than before. Capability compounds. Code decays.
3. **The organizational model** uses persistent offices with stable responsibilities. Workers are replaceable. Offices persist.
4. **Three permanent missions:** Reduce uncertainty. Reduce activation energy. Compound organizational judgment.

## Consequences

This ADR supersedes ADR-0010 in organizational scope but inherits its product-level constraints: Kitty remains single-user, local-first, state-truthful, and Jacob-facing. Every subsystem must support one or more of the three missions. "Is this improving the organization or just generating more code?" is a valid review question.
