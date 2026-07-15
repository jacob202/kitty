---
type: adr
title: "Borrow Patterns, Not Random Complexity"
status: accepted
owner: jacob
primary_purpose: Code sniping is encouraged; importing a repo's entire worldview is not
derives_from:
  - docs/CONSTITUTION.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR-0007: Borrow Patterns, Not Random Complexity

**Status:** Accepted
**Date:** 2026-07-02

## Context

AI agents (and humans) reading other repos for inspiration can import
patterns that fit, or import a whole worldview that doesn't. The
"import the worldview" path produces a codebase that has multiple
operating stories.

## Decision

Code sniping is encouraged when it maps to Kitty's current loop.
Borrow proven UX and architecture patterns; do not import a repo's
worldview wholesale.

## Consequences

- A borrowed pattern needs a "why this fits Kitty" note before it
  lands.
- If a borrowed pattern requires a substrate Kitty doesn't have,
  it's not borrowed — it's a project.
- This applies to agents too: a clean "borrow this one trick" is
  fine, a "let me adopt their whole folder layout" is not.
