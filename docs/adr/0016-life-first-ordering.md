# ADR 0016 — Life-First Ordering: Kitty Serves Jacob's Life Before Its Own Development

**Date:** 2026-07-11
**Status:** Accepted
**Source:** `docs/NORTH_STAR.md` (final Fable session)

## Decision

1. When Kitty ranks or generates next steps, briefs, or resurfaced items,
   **life projects outrank code projects** — including the Kitty/KittyBuilder
   projects themselves. Life projects are those about employment, benefits,
   education, health, money, and relationships (today identifiable by the
   non-`code` project kind; a worker packet may formalize the tag).
2. The daily companion path (chat, briefs, next steps, capture) must remain
   fully functional on the free/cheap model routes (`kitty-default`,
   `kitty-default-or`) — no feature on the daily path may hard-require a
   premium model.
3. Engineering work on Kitty itself is scheduled through the Builder queue
   and must not colonize the What's Next surface: at most one self-
   development suggestion may appear when life-project steps are available.

## Why

Kitty exists to give Jacob the help that money usually gates. The failure
mode observed across sessions is gravitational: sessions default to
improving the machine because the machine is legible to engineers. The
product measure — mornings Jacob wants to open Kitty — is only moved by the
life loop. This ADR makes the ordering a contract instead of a hope.

## Consequences

- `life-first-v1` initiative packets implement the ranking and free-route
  guarantees.
- Reviewers should reject What's Next changes that surface Kitty-development
  tasks above eligible life-project steps.
