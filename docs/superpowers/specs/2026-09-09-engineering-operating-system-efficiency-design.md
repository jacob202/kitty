# Engineering Operating System Efficiency Design

**Date:** 2026-09-09
**Status:** Approved direction; implementation is plan-by-plan and does not activate Builder or a new Mission.
**Owner:** interactive engineering lane
**Base:** `origin/main@505bdc09901084cc7730d6f7d0c442f04d805b4f`

## Problem

Kitty's engineering workflow has accumulated individually sensible safety mechanisms whose combined cost is now multiplicative. A small change can fan out into multiple agents, context loads, worktrees, coordination claims, test passes, PR updates, reviews, recovery cycles, handoffs, and leftover runtime state.

The system is comparatively strong at recovering from failure and preventing collisions. It is weaker at four earlier/later boundaries: deciding whether another agent should launch, keeping the inner development loop cheap, retiring resources after terminal work, and measuring where time/tokens/retries actually went.

This design treats ChatGPT, Codex, Claude, OpenCode, Builder, Git worktrees, KX, GAR, tests, GitHub PRs, and local processes as one development operating system. It does **not** create another execution authority.

## 2026-09-09 baseline

- 11 registered worktrees and 38 local branches were present during the audit; 30 local branches had no current PR mapping.
- Recent merged PRs had a median lifetime of about 30.3 minutes while the median slowest GitHub check was about 5.8 minutes.
- The documented fast-Python baseline was 108.8 seconds / 4,714 passes; the current exact fast tier ran 5,649 passes plus one failure in 403.10 seconds.
- Since that latency baseline, 253 test files changed, 31,190 test lines were added, and 103 new test files appeared.
- In the most recent 500 GAR messages, 474 were broadcasts; claim acquisition/release/status traffic dominates the stream.
- Local Codex and Claude session logs expose enough parent/child/model/token metadata to reconstruct substantial historical execution cost without asking models to remember it.

## Design principles

1. **One outcome owner.** Every implementation has one lead accountable for the requested outcome. Parallel workers assist that owner; they do not independently enlarge the assignment.
2. **Admission before dispatch.** Provider/tool availability, current base SHA, ownership/collision state, workspace destination, validation prerequisites, retry fingerprint, and any spend authorization are checked before an expensive worker exists.
3. **Parallelism must earn its cost.** Spawn another agent only for genuinely independent parallel work or an independent trust boundary. Default child fan-out is bounded; nested swarms are not the default.
4. **One mutating lane, one reusable workspace.** A continuing task reuses its authenticated worktree. Read-only research/review should not create a persistent worktree merely because it can.
5. **Small active context.** Workers receive the outcome contract, exact candidate/base, relevant files, current blocker, constraints, and verification. Historical chatter and compatibility checkpoints stay out unless specifically required.
6. **Tiny inner loop, strong final gate.** Editing uses the narrowest meaningful tests. Expensive repository-wide evidence runs against a frozen candidate rather than after every intermediate edit or push.
7. **Creation implies retirement.** Worktrees, branches, claims, sessions, and owned child processes get terminal-state handling. Dirty/unpublished work is preserved; demonstrably recoverable clean state is retired.
8. **Control-plane state is not conversation.** KX remains authoritative for claims. GAR remains durable communication, but routine claim/heartbeat telemetry should not dominate agents' conversational context.
9. **Measure before optimizing again.** Elapsed time, retries, candidate SHAs, tests, review cycles, context/token telemetry, coordination waits, and cleanup state are recorded from authoritative sources. Dollar cost remains unknown unless a provider gives an authoritative receipt.
10. **No competing control plane.** Existing KX/GAR, `run_workspace`, Builder state, Git/GitHub evidence, PR Janitor, session learning, and CI metrics are extended or joined read-only; they are not replaced by a new scheduler/database of truth.

## Target execution loop

`request -> lead/outcome contract -> admission -> reuse/create one lane -> bounded implementation -> narrow verification -> frozen candidate -> independent review -> authoritative delivery gate -> terminal outcome -> retirement -> metrics receipt`

A failure before dispatch is `blocked_before_dispatch`, not an implementation attempt. An unchanged infrastructure blocker may not consume another retry merely because time passed.

## Reuse of existing architecture

This program is a convergence layer over mechanisms that already exist:

- `gateway/agent_coordination.py` / KX remain collision and mutation-ownership authority.
- `gateway/run_workspace.py` and `gateway/builder_runner.py` already authenticate/create/reuse worktrees and provide safe primitives to extend.
- `workspace_global` remains the durable handoff/assignment surface; direct inbox and threads remain the preferred assignment locators.
- `gateway/builder_pr_janitor.py` remains PR lifecycle machinery; worktree/process retirement should complement it rather than duplicate PR state.
- `verified-delivery`, outcome-first delivery, and the existing Agent Runtime lifecycle designs remain the acceptance/context foundation.
- Git/GitHub remain publication truth; Builder remains Builder execution truth.
- `scripts/ci_metrics.py`, nightly suite profiling, session learning, KB effectiveness, provider spend records, and local agent session logs become evidence inputs rather than separate authorities.

## Program boundaries

The program does not auto-delete unknown work, force-push, merge without authority, kill arbitrary host processes, weaken GitHub required checks, infer provider dollar cost, or turn every adjacent finding into another task. Cleanup starts report-only and becomes automatic only where ownership and recoverability are provable.

The program also does not require Builder. Interactive ChatGPT/Codex/Claude work must improve even when Builder is never opened.

## Delivery sequence

The work is deliberately split so improvements can land independently:

1. **Fast development loop and PR latency:** remove accidental waits and duplicate local/full validation from the inner loop while preserving a strong ready-candidate gate.
2. **Agent admission and workspace lifecycle:** prevent waste before launch, reuse existing lanes, and make terminal work cleanup-eligible.
3. **Workflow telemetry and historical backfill:** normalize existing evidence into one queryable development ledger and establish truthful baselines.
4. **Coordination-plane simplification:** keep KX safety while removing machine lease chatter from the communication path agents consume.

Each implementation plan must produce its own before/after evidence. No later plan is required for an earlier plan to be useful.

## Initial success measures

These are first-wave engineering targets, not permanent product SLOs:

- Ordinary feature editing never requires the complete repository test matrix after every edit or intermediate push.
- The fast Python tier is reprofiled and brought below 180 seconds locally as the first ratchet, with every >5-second fast test explained or repaired; the historical ~109-second level remains the longer-term comparison.
- A ready code PR still receives all scope-required GitHub checks; draft iteration does not manufacture redundant full validation.
- A second worker is not launched when the task fingerprint, owner, and active lane already identify an equivalent worker.
- Infrastructure/provider/toolchain rejection occurs before worker/model dispatch wherever it can be determined locally.
- Every owned worktree reaches one of `active`, `cleanup_eligible`, `quarantined`, or `retired`; terminal clean/recoverable work does not remain indefinitely without explanation.
- Agents discover assignments through direct/threaded communication without ingesting routine claim acquisition/release broadcasts.
- A local report can explain a task/PR timeline in terms of agent launches, parent/child topology, candidate SHAs, tests, CI, reviews, retries, coordination waits, and cleanup state.
- Token/cache figures retain their source semantics; no cumulative counter is double-counted and no token number is presented as money without provider evidence.

## Decision rationale

Kitty genuinely needs isolation and coordination because multiple engineering tools can be active concurrently and the canonical checkout frequently contains unrelated work. Removing worktrees or KX would trade visible overhead for data-loss and collision risk. The right move is to make isolation reusable and lifecycle-owned, and to move collision/admission checks before expensive execution.

Likewise, Kitty's broad test suite provides real regression protection. The problem is not comprehensive final validation; it is paying comprehensive-validation cost repeatedly inside the editing loop. The correct optimization is therefore a cheap inner loop plus a frozen-candidate delivery gate, not weaker final evidence.

Finally, the repository already contains unusually rich execution evidence. Building the telemetry layer from those existing records is lower-risk and more truthful than adding speculative instrumentation first. Historical backfill also lets later policy changes be evaluated against a real baseline rather than intuition.

## Implementation artifacts

- `../plans/2026-09-09-fast-development-loop-and-pr-latency.md`
- `../plans/2026-09-09-agent-admission-and-workspace-lifecycle.md`
- `../plans/2026-09-09-agent-workflow-telemetry-and-backfill.md`
- `../plans/2026-09-09-coordination-plane-simplification.md`

Recommended execution order is Plan 1 first because it reduces the cost of implementing every later plan. Plan 2 is next because it stops avoidable work before launch and closes the workspace lifecycle. Plan 3 should begin early as read-only backfill if it does not contend with Plan 2; its results set later ratchets. Plan 4 should follow once telemetry can measure whether lower GAR message volume preserves collision safety.
