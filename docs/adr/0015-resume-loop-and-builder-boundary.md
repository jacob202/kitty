# ADR 0015 — The Resume Loop Is The Product; Builder Has Separate State Ownership

**Date:** 2026-07-11
**Status:** Accepted; amended 2026-07-26
**Source:** `docs/BLUEPRINT.md` (Fable blueprint session)

## Decision

1. Kitty's defining experience is the **resume loop**: open Kitty and within
   five seconds know what happened, what's next, and what needs you — and
   continue any of it in chat with context pre-loaded. Features are judged by
   whether they serve this loop.
2. **Kitty and KittyBuilder are one product with separate responsibilities and
   state ownership.** Kitty owns user experience, intent, and personal data.
   Builder owns engineering execution truth: missions, queue state, attempts,
   leases, worktrees, evidence, review, and publication. They communicate only
   through supported versioned command and projection interfaces; direct
   cross-store writes remain forbidden. Kitty remains useful when Builder is
   offline.
3. **Orca is an adapter.** Durable delegated-task state lives only in the
   Builder queue; Orca transports and reports. A dead Orca means an expired
   lease, never a lost task.
4. **Failure semantics are a contract.** Failures surface as failed,
   interrupted, blocked, or unknown — never completed. Empty states are
   explicit, never swallowed exceptions. Verifier evidence is authoritative.
5. **Browser verification is a release gate for UI work.** Code and unit tests
   without a live browser pass remain unverified and incomplete.
6. Visual identity belongs to the canonical design system and product plan. It
   is not an execution-boundary decision.
7. Route growth is governed by evidence, ownership, and duplication analysis.
   The former absolute "no new route module without deleting one" rule is
   retired; a new route still requires a demonstrated owner and must not create
   a parallel subsystem.

## Amendment — 2026-07-26

The original wording called Kitty and KittyBuilder "separate systems." That was
useful for protecting storage boundaries but misleading at the product level.
The corrected rule is: **one product, separate responsibility and state
ownership.** ADR 0017 defines the Mission boundary, ADR 0020 defines planning
ownership, and ADR 0021 defines proactive execution.

## Why

The alternative repeatedly produced unverified dashboards, silent fallbacks,
and orchestration truth scattered across tools. Continuity, honest state, and
bounded delegation distinguish Kitty from a stateless chat tool. The boundary
protects those properties without turning Builder into a competing product.
