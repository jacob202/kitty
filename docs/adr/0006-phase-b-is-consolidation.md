# ADR-0006: Phase B Is Consolidation

**Status:** Accepted
**Date:** 2026-07-02

## Context

Phase B came after a long stretch of feature work, agent sprawl, and
storage fragmentation. The risk in this phase is to mistake "the
product feels exciting" for a reason to add a new substrate, a new
mobile app, or a new sync layer.

## Decision

Phase B is one storage story and one operating story. No mobile app,
cloud sync, push notifications, full agent dashboard, TELOS
expansion, or new memory substrate.

## Consequences

- New state-spine stores land in `kitty.db` with their own
  migrations; no new SQLite files, no new vector stores, no new
  memory substrates.
- "Phase C" and later can revisit this, but only after Phase B
  closes with measured, working state consolidation.
- Exciting-but-unrelated work is captured in `docs/packets/` for
  later, not built in Phase B.
