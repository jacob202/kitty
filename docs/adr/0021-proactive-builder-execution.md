# ADR 0021: Proactive Builder Execution and Model Policy

- **Status:** Accepted
- **Date:** 2026-07-26
- **Decision owner:** Jacob
- **Amends:** ADR 0018's campaign-only scope

## Context

KittyBuilder already has durable queue, initiative, packet, attempt, lease,
worktree, review, publication, and recovery seams. The remaining operating
failure is that progress still depends too often on Jacob starting the next
packet, rescuing every failure, or manually carrying successful work through
GitHub.

Free workers are abundant but unreliable. Paid reasoning is scarce and must be
reserved for work that actually requires judgment. Provider exhaustion and
rate limits are normal availability conditions, not reasons to lose progress or
misclassify a packet.

## Decision

Once work is explicitly approved, KittyBuilder is proactive.

1. It selects the highest-priority eligible approved packet without waiting for
   another human launch instruction.
2. A failed, blocked, or exhausted packet does not stop unrelated eligible
   packets. Builder records the evidence, releases resources safely, and
   continues.
3. For an approved packet Builder may edit, test, commit, push its Builder-owned
   branch, open or update a draft PR, mark the PR ready, and merge only when the
   packet is eligible for evidence-gated low-risk auto-merge.
4. Provider exhaustion, rate limiting, or unavailable models produce a durable,
   resumable pause. Partial work and evidence remain intact; no success or
   implementation failure is fabricated.
5. There is no arbitrary campaign-level packet or runtime ceiling. Per-attempt
   timeouts, bounded repair loops, lease expiry, concurrency controls, provider
   budgets, and tripwires remain mandatory safety mechanisms.
6. Builder reports completed outcomes, failures, diagnostic evidence, and
   decisions needed. Investigation detail lives in durable artifacts rather
   than chat.

## Model classes

Every executable item is classified before dispatch:

- `free-exec`: all judgment is resolved and correctness is decided by runnable,
  falsifiable deterministic gates.
- `free-exec-blocked`: would be `free-exec`, but a required gate or environment
  is unavailable.
- `paid-author`: a strong model must produce patch-level instructions before a
  free worker can execute.
- `paid-exec`: judgment remains necessary during implementation or review.
- `human`: requires accounts, money, secrets, physical action, or an owner
  decision.
- `idea`: preserved but not executable.

There is no accidental paid fallback. A packet uses a paid route only when its
policy permits it and funded credentials are available. Otherwise it pauses or
uses an approved free route.

## Low-risk auto-merge boundary

Evidence-gated auto-merge requires all of ADR 0018's validation, independent
review, scope, post-merge verification, auto-revert, and tripwire protections.
It is disallowed for:

- dependencies or lockfiles;
- CI workflow changes;
- auth, secrets, permissions, or security boundaries;
- destructive operations or data migration;
- schema migrations unless separately classified and approved;
- UX, copy, visual, or product judgment requiring human inspection;
- unresolved cross-initiative path collisions;
- gates that are not runnable and falsifiable;
- any material scope expansion.

Those items may still be committed, pushed, and opened as draft PRs under their
approved packet; they stop before merge for the required decision or review.

## Scheduling consequence

The existing nightly drain is extended rather than replaced. Scheduling is not
enabled until CI is trustworthy, at least one real `free-exec` manifest has
passed its falsifiability checks, and one daylight unattended run has completed
end to end. On macOS the durable scheduler is `launchd`; Builder remains the
owner of execution state.

## Consequences

- Jacob approves work and policy, not every mechanical transition.
- Builder becomes a delivery loop rather than a one-packet launcher.
- Free-model execution and deterministic verification are one engineering
  problem.
- Paid tokens are concentrated on planning, packet authoring, difficult
  execution, and high-risk review.
- Exhaustion and failure become resumable state instead of lost nights.
