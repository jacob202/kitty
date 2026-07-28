# KittyBuilder recovery checkpoint — 2026-07-28

## Purpose

This checkpoint preserves the live evidence, active review work, and safe next
step for the KittyBuilder reliability and operational-surface effort. It is not
a new Builder authority; queue state remains owned by supported Builder
projections.

## Live evidence

- Worktree: `jacob202/fix-description` at
  `514b17da5bdcaa19bdec82f8fd204c4cf9ee2164`, clean before this checkpoint.
- `./kitty builder initiative doctor --json` in this worktree was healthy but
  inspected an empty *worktree-local* database. Do not use it to make claims
  about the canonical queue.
- The running Kitty app at `http://127.0.0.1:4000` loaded successfully. Its
  supported runtime projection, `GET /proxy/runtime/manifest`, reported Builder
  as `degraded`, with 6 partial packet records out of 75 and queue totals:
  80 total, 11 queued, 2 blocked, 3 awaiting review, 36 done, and 28 cancelled.
- The live Builder screen exposes a large undifferentiated packet list while
  Work overlaps conceptually with Builder. It has visible `resume` and cleanup
  controls; do not trigger them until the queue records are reconciled.

## Confirmed diagnostic findings

1. `kittybuilder-brain-v1` is active in runtime state with eight queued packets,
   but `docs/initiatives/README-kittybuilder-brain-v1.md` says its source harvest
   already exists and downstream packets are not runnable until the active
   roadmap promotes the remaining delta. Do not retry its first packet blindly.
2. Several KTF packets are cancelled after the target state was superseded or
   partially landed. Re-run eligibility requires Git and focused test evidence,
   not attempt status alone.
3. The independent reliability review identified three code candidates that must
   be independently confirmed before repair:
   - cancellation is collapsed into `packet_exhausted` in the initiative runner;
   - stale-attempt reconciliation treats every outcome-null attempt as stale
     without run/PID liveness proof and may leave recovery-only blocked tasks
     unreselectable;
   - the status projection hides cancellation provenance and can expose a raw
     stored initiative state that conflicts with the derived state.
4. Some partial records are historical malformed evidence (publication SHA or
   policy shape), not a current parser failure. Do not rewrite history to make
   the status look healthy.

## Active read-only review lanes

| Task | Dispatch | Scope | State at checkpoint |
| --- | --- | --- | --- |
| `task_23fbbecd370f` | `ctx_1f4fbe008591` | Builder recovery/root-cause review | completed — result received |
| `task_eff4dfd1daae` | `ctx_0ec018f773ab` | Eight-lens Work/Builder UX swarm | running |
| `task_9ce58b27bacb` | `ctx_06f44c7780bf` | Frontend/Gateway contract alignment | running |
| `msg_fcc2df76f79b` | canonical handoff | Read-only Builder CLI evidence | awaiting reply |

## User-requested scope queued after reliability reconciliation

- A conversational KittyBuilder Brain, but only as a bounded view over existing
  Mission/Builder evidence—not a new queue or project-manager authority.
- Frontend/backend feature alignment and quick, verifiable wiring wins.
- Review the Genevolve image-generation repository once its local path is known
  and access is granted; adopt patterns only after compatibility and ownership
  review.
- Consolidate the overlapping Work and Builder surfaces into one usable,
  information-rich operational area. The designer owns the visual and
  interaction decisions.

## Safe next move

Reconcile the two remaining reviews, confirm or refute the three candidates
against current source and focused tests, then prepare one bounded repair that
keeps cancellation, provider exhaustion, stale recovery, and historical data
quality distinct. Before any canonical queue mutation, take a fresh supported
runtime snapshot and prove run identity, PID/lease status, no open attempt, and
the exact recovery-only block reason for each candidate.
