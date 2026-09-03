# Decision Review — 2026-07-26

## Purpose

Reconcile Kitty's accepted ADRs with current repository evidence, the
Kitty/KittyBuilder Alignment Map, Jacob's proactive-execution authority, and the
requirement for one canonical roadmap.

This file records the review outcome. The durable decisions themselves live in
`docs/adr/`.

## Disposition

### Kept unchanged

ADRs 0001–0005, 0007–0009, 0011–0012, 0014, 0016, and 0019 remain compatible
with the current architecture.

They preserve local-first single-user operation, the gateway product boundary,
explicit storage seams, durable capture, high-signal lint, the privacy boundary,
read-only Gmail, Magic Kitty, life-first ordering, and the rule that audits do
not auto-implement themselves.

### Fulfilled / historical

ADR 0006 governed Phase B consolidation. That phase is complete. Its anti-sprawl
principle survives through ADR 0007, ADR 0020, and the Alignment Map, but its
phase-specific build restriction no longer controls current sequencing.

### Amended

- **ADR 0010:** retained the personal operating-layer identity; retired its
  fulfilled state-spine packet order.
- **ADR 0013:** retained phone-first delivery and "bring review to Jacob";
  moved exact transport and changing priorities out of permanent architecture.
- **ADR 0015:** clarified one product with separate Kitty/Builder responsibility
  and state ownership; retired the absolute route freeze and styling detail.
- **ADR 0017:** moved planning judgment and packet authoring above Builder;
  Builder validates, selects, executes, verifies, and reports approved work.
- **ADR 0018:** expanded evidence-gated auto-merge from one historical campaign
  plan to any explicitly approved low-risk Builder packet under ADR 0021.

### Added

- **ADR 0020:** one canonical roadmap and explicit planning ownership.
- **ADR 0021:** proactive Builder execution, continuation after unrelated
  failures, resumable provider exhaustion, model classes, and the low-risk
  delivery boundary.

## Concrete decisions

1. `docs/ROADMAP.md` is the only active roadmap.
2. `docs/ACTIVE_MISSION.md` now owns the trust-foundation and first complete
   resume-loop proof.
3. Old plans, packets, audits, and initiative manifests are preserved planning
   inputs, not parallel authority.
4. `kx-01` and `kx-02` should be combined into one dependency-valid initiative
   with internal phases rather than adding cross-initiative dependencies.
5. Packet 007 is not first in the free-execution conversion order. Its current
   Markdown renderer is not an executable-manifest compiler.
6. Existing packet prose is delta-reviewed against current code before any
   re-execution.
7. Builder may proactively carry approved work through edit, test, commit,
   push, draft PR, ready, and evidence-gated low-risk merge.
8. A failed packet does not block unrelated eligible packets.
9. Provider exhaustion is a durable resumable pause, not lost work or a
   fabricated implementation failure.
10. Chat receives outcomes, failures, and decisions needed; detailed work and
    evidence stay in durable files and Builder artifacts.

## Immediate effect

The current phase is not another feature build. It is:

- restore Python and frontend CI;
- close PRs #261/#262/#263 coherently;
- repair planning authority;
- close Builder recovery by evidence;
- create two verified `free-exec` JSON packets;
- prove proactive execution in daylight;
- prove one real life-project resume loop end to end.

Everything else remains visible in the backlog and waits for promotion by the
canonical roadmap.
