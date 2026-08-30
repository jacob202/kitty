# ADR 0038: Builder Crash-Recovery Durability Contract

**Date:** 2026-08-05
**Status:** Accepted

## Context

KittyBuilder's execution control plane (initiatives, packets, task queue,
leases, attempts, worker runs, validation, review, budgets, operator overrides)
has been proven operational under induced failure. The phase1-1 builder recovery
proof and core runtime audit (both 2026-08-01) demonstrated:

- Worker self-crash → lease expires, packet is retryable by a fresh worker.
- Supervisor crash → stale leases are detected and recovered.
- Budget exhaustion → packet transitions to a blocked state with a durable
  reason; operator grant unblocks it.
- Cancellation → explicit cancellation terminates the attempt and transitions
  the packet cleanly.
- Worktree removal → dirty worktrees refuse deletion; clean ones are removed.
- State projection — `./kitty builder status` and `./kitty builder doctor --json`
  reflect the correct state after every recovery operation.

The implementation exists in `gateway/builder_*.py` (per ADR 0036)
backed by `data/kittybuilder/builder_queue.db`. However, no ADR formally defines
the durability contract that the proofs verify. ADR 0021 covers proactive
execution and model policy; ADR 0036 covers module organization and extraction
readiness. Neither documents the crash-recovery semantics.

## Decision

Builder's crash-recovery durability contract is as follows:

1. **Every packet state transition is atomic.** A packet moves from one state to
   another through a single write transaction. No intermediate state is
   observable.

2. **Leases are time-bounded and self-expiring.** A worker holds a lease for a
   bounded interval. If the worker crashes or the supervisor dies, the lease
   expires and the packet returns to the eligible pool. A fresh worker may claim
   it on the next selection cycle.

3. **Failed attempts are preserved, not overwritten.** Each attempt is a durable
   record with its own branch, base SHA, changed files, test results, verdict,
   and evidence. A retry creates a new attempt; it never mutates or hides the
   failed one.

4. **Budget exhaustion produces a durable blocked state with a reason.** A
   packet that exhausts its attempt budget transitions to a state that can only
   be unblocked by an explicit operator grant. The blocking reason is durable
   and survives restart.

5. **Cancellation is explicit and complete.** A cancelled packet records the
   cancellation as a terminal state transition. No orphaned worktrees, leases,
   or partial attempts remain.

6. **Dirty worktrees are preserved.** A worktree with uncommitted changes
   refuses deletion. Only clean, completed worktrees are removed during cleanup.

7. **Provider exhaustion is not implementation failure.** When all eligible
   providers are exhausted, Builder pauses durably and does not fabricate a
   `failed` outcome for packets it never attempted.

8. **Recovery is deterministic.** Given the same queue state, Builder selects
   the same next eligible packet. Recovery does not depend on in-memory state or
   a specific process surviving.

## Consequences

- The durability contract is verifiable by the existing `scripts/builder_recovery_proof.py`
  harness (phase1-1). Every scenario runs against the real Builder queue with
  deterministic local worker fixtures; no model provider is contacted.
- Any change to Builder's state machine must preserve all eight recovery
  properties. The recovery proof must be re-run and pass.
- The contract is independent of worker type (shell, OpenCode, Claude Code,
  Codex). It governs the queue layer, not the worker adapter.
- This ADR does not change any implementation. It formalizes the contract the
  existing proofs already verify.