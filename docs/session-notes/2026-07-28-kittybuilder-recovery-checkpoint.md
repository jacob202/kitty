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

## Reconciled review outcomes

- The live Builder surface retains unusually good underlying evidence but makes
  91 controls reachable in one short viewport and duplicates the full packet
  list in a modal. Its `Read-only execution status` claim conflicts with
  resume/cleanup controls that can mutate Builder state while the fact is
  partial. The next design must make Work the calm cross-domain now page, Build
  a read-only decision radar by default, and move any mutation into an explicit
  management flow that is disabled on degraded, stale, or unknown evidence.
- The running browser was serving canonical commit `1c6487d`, not this
  worktree's `514b17d`. Future browser proof must launch the reviewed worktree
  or display the served build SHA; do not attribute the current UI to this
  branch.
- High-value UI/API truth gaps: repair buttons can return `ok:false` while the
  UI looks successful; provider readiness confuses configured with health-probed;
  Settings confuses LiteLLM model discovery with Gateway health; the command
  palette trigger is inert; Studio turns failed fetches into an empty inventory;
  and Builder glance can call an unavailable fact an empty queue.

## Active read-only review lanes

| Task | Dispatch | Scope | State at checkpoint |
| --- | --- | --- | --- |
| `task_23fbbecd370f` | `ctx_1f4fbe008591` | Builder recovery/root-cause review | completed — result received |
| `task_eff4dfd1daae` | `ctx_0ec018f773ab` | Eight-lens Work/Builder UX swarm | completed — result received |
| `task_9ce58b27bacb` | `ctx_06f44c7780bf` | Frontend/Gateway contract alignment | completed — result received |
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

## Low-cost worker continuation contract

The next worker must not re-discover this state or wait for a packet to fail
when its preconditions are already false.

1. Start with `git status --short --branch`, `git log -3 --oneline`, this file,
   and `.slim/deepwork/kittybuilder-reliability-and-brain.md` if it exists.
   The checkpoint commits are `40b04ee` and `96de6e6`; re-derive the current SHA
   before using any attempt result.
2. Re-run `./kitty context --agent` and inspect the live Builder only through a
   supported projection. In this session the live product evidence was
   `http://127.0.0.1:4000/proxy/runtime/manifest`; it served canonical commit
   `1c6487d`, so it is not proof for this worktree unless this worktree is
   launched explicitly.
3. Do **not** mutate the canonical queue, retry `KB-BRAIN-00-source-harvest`, or
   re-run cancelled KTF packets based only on their queue state. The Brain
   harvest is already present; several KTF packets have invalidated anchor
   guards or superseded targets.
4. Direct specialist work owns difficult recovery and judgment: distinguish
   cancellation from exhaustion, add liveness-proof before stale-attempt
   reconciliation, preserve cancellation provenance, and reconcile raw versus
   derived initiative state. It needs bounded implementation plus independent
   review before any queue repair.
5. Builder may receive only a packet that is current and `free-exec`: narrow
   allowed paths, no unresolved design/authority/environment decision, explicit
   stopping rule, runnable deterministic gate, and verified unmodified-tree
   failure. Everything else stays with the direct specialist lane.
6. The next implementation checkpoint must include exact files and symbols,
   command outputs, task/attempt IDs, live build identity, known hazards,
   prohibited mutations, and one executable next action. Tests have not been
   run in this session; code-level findings are candidates until the agreed
   focused validation runs.
