---
type: adr
title: "The Resume Loop Is The Product; Builder Is A Separate Control Plane"
status: accepted
owner: jacob
primary_purpose: Kitty's defining experience is the resume loop; KittyBuilder is a separate system
derives_from:
  - docs/CONSTITUTION.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR 0015 — The Resume Loop Is The Product; Builder Is A Separate Control Plane

**Date:** 2026-07-11
**Status:** Accepted
**Source:** `docs/BLUEPRINT.md` (Fable blueprint session)

## Decision

1. Kitty's defining experience is the **resume loop**: open Kitty and within
   five seconds know what happened, what's next, and what needs you — and
   continue any of it in chat with context pre-loaded. Features are judged by
   whether they serve this loop.
2. **Kitty and KittyBuilder are separate systems.** Kitty owns user experience
   and personal data (`data/`); Builder owns engineering truth (queue DB, run
   manifests, worktrees). Neither writes the other's stores. Kitty reads
   Builder state only through Builder's read API, only for the delegated-work
   card. Kitty must remain fully usable with Builder offline.
3. **Orca is an adapter.** Durable delegated-task state lives only in the
   Builder queue; Orca transports and reports. A dead Orca means an expired
   lease, never a lost task.
4. **Failure semantics are a contract.** Failures surface as
   `failed`/`interrupted`, never `completed`; empty states are explicit, never
   swallowed exceptions. Verifier exit codes are authoritative
   (`tests/test_verifier.py`), route ownership is unique
   (`tests/test_route_contracts.py`).
5. **Browser verification is a release gate for UI work.** Code + unit tests
   without a live browser pass is "unverified", and unverified = incomplete.
6. **Visual identity:** cosmic dark theme as default identity; hand-drawn
   line-art doodle cat mascots (per verified references in
   `docs/fable-context/assets/`), used in logo, empty states, and delight
   moments — never rendered/3D, never blocking content.
7. **Route surface is frozen:** no new gateway route module without deleting
   one. Honcho, Telegram, and dream/insights UI stay out until real.

## Why

The audit showed the failure mode of the alternative: dashboards of
unverified tiles, silent fallbacks presenting broken integrations as working,
and orchestration state scattered across tools. Continuity + honest state +
delegation is what distinguishes Kitty from stateless AI tools, so the
architecture must protect exactly those three properties.
