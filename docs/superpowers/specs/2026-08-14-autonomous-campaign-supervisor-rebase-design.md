# Design: Autonomous Campaign Supervisor (rebased)

## Decision

Add a source-controlled, stateless Builder supervisor and strict Claude Pro adapter. KittyBuilder remains the only durable authority; the supervisor is only a bounded launcher and read projection.

## Rebase review

This revision is bound to `main@8bd732f3ef948af2316eadf89ffeaff94849f3e6`. The delta from the prior base `6e49a4e1` is PR #495 only: Discord command request-size validation and its tests. It has no changed paths in `gateway/builder_*`, `scripts/kittybuilder_*`, desktop launchd, or Builder documentation, so the design remains valid without a code-scope adjustment.

## Boundaries

- Existing Builder APIs exclusively select, claim, run, recover, validate, review, and publish work.
- The supervisor takes an OS lock and invokes at most two canonical initiative runs per tick; it owns no task state and never resumes paused work.
- The launcher has a fixed command and safe environment. It schedules, but never installs itself as part of worker verification.
- The Claude adapter mirrors the existing strict adapter contract: Sonnet worker, Opus independent reviewer, no fallback, fake-CLI tests only.
- Discord remains a typed read/control projection with no shell, approval, publication, or merge authority.

## Acceptance evidence

A low-risk manual-publication Mission can advance through normal Builder review after a scheduled tick; duplicate ticks create no duplicate work; provider failure becomes durable Builder truth; a real Claude request is not needed to test the adapter contract.
