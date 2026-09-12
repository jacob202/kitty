# Agent Admission and Workspace Lifecycle Implementation Plan

**Goal:** Stop non-viable or duplicate agents before model dispatch, reuse existing authenticated lanes, and retire terminal workspaces safely.

**Architecture:** Extend the existing Builder supervisor preflight, KX mutation preflight, `run_workspace`, and session-end machinery. Do not create another scheduler or registry. Admission is read-only and happens before attempt/run creation whenever the required fact can be known locally.

**Primary evidence from the audit:** provider/tooling failures, stale attempts, worktree identity drift, late KX conflicts, and repeated infrastructure blockers consumed substantial attempts. Current Builder preflight is already read-only and checks packet integrity, freshness, eligibility, and estimated route cost, but live provider/toolchain readiness and repeated-blocker identity are still discovered later.

## Task 1: Remove stale compatibility context from worker startup

**Files:**
- Modify: `scripts/kittybuilder_opencode_worker.sh`
- Modify: `scripts/kittybuilder_dsh_worker.sh`
- Modify: `tests/test_kittybuilder_opencode_adapters.py`
- Modify: `tests/test_kittybuilder_dsh_runtime.py`

**Step 1:** Add regression tests proving worker prompts do not instruct implementations to read `.claude/HANDOFF.md` or `.claude/STATE.md`.

**Step 2:** Keep `AGENTS.md`, the runner-generated bundle/context manifest, exact base/candidate identity, allowed paths, acceptance criteria, and validation commands as the worker's startup authority.

**Step 3:** Run the two adapter/runtime test files and record RED before the prompt change and GREEN after it.

## Task 2: Extend read-only Builder admission before attempt creation

**Files:**
- Modify: `gateway/builder_supervisor.py`
- Modify: `tests/test_builder_preflight.py`
- Modify only as needed for shared helpers: `gateway/builder_runner.py`

**Step 1:** Extend `preflight_packet()` with deterministic checks for validation-tool prerequisites derived from declared validation commands. Missing local executables/dependencies must return `blocked`, not create an attempt.

**Step 2:** Add a provider-route readiness result to preflight using adapter-owned/probeable facts only. Distinguish `unknown` from `unavailable`; do not manufacture network health when no trustworthy probe exists.

**Step 3:** Return a machine-readable admission receipt containing base SHA, route, required tools, ownership/freshness result, and a blocker fingerprint.

**Step 4:** Add tests proving blocked admission leaves task, run, attempt, and lease tables unchanged.

**Step 5:** Ensure paid routes still require the existing compute/spend admission and that this plan does not bypass PR #839's reservation boundary.

## Task 3: Prevent unchanged infrastructure blockers from redispatching

**Files:**
- Modify: `gateway/builder_supervisor.py`
- Modify: `gateway/builder_loop.py`
- Modify: `tests/test_builder_preflight.py`
- Modify: `tests/test_builder_loop.py`

**Step 1:** Define a stable blocker fingerprint from blocker class plus the facts that would have to change: route/provider set, validation-tool identity, base SHA, KX ownership collision, or worktree identity.

**Step 2:** Persist the fingerprint in existing Builder event/decision data rather than adding a second state store.

**Step 3:** If the newest blocker fingerprint is unchanged, preflight returns `blocked` with `retry_requires_state_change=true`. It must not launch a worker simply because the supervisor ticked again.

**Step 4:** Permit retry when the fingerprint changes or an explicit operator override is supplied and recorded.

**Step 5:** Cover provider exhaustion, missing validation tooling, and KX collision with focused tests.

## Task 4: Reuse authenticated workspaces for continuing ownership

**Files:**
- Modify: `gateway/run_workspace.py`
- Modify: `gateway/builder_runner.py`
- Modify: `tests/test_run_workspace.py`
- Modify: `tests/test_builder_runner.py`

**Step 1:** Add a reusable-workspace lookup keyed by durable task/lane plus authenticated repository identity. Reuse only when the worktree remains registered, identity matches, and its base/candidate state is compatible.

**Step 2:** Refuse silent reuse of an unrelated dirty tree. Dirty state may be reused only when it is the explicitly preserved repair/recovery input for the same durable task.

**Step 3:** Read-only review/research paths should use detached/ephemeral checkout facilities and should not register another persistent feature worktree unless publication is required.

**Step 4:** Add tests for valid reuse, stale identity, wrong branch/task, dirty unrelated state, and missing registration.

## Task 5: Give every created workspace a terminal lifecycle

**Files:**
- Modify: `gateway/run_workspace.py`
- Modify: `.agents/skills/session-end/SKILL.md`
- Modify: `tests/test_run_workspace.py`
- Modify session-end tests as required.

**Step 1:** Represent workspace disposition as `active`, `cleanup_eligible`, `quarantined`, or `retired` in the existing run/session receipt path.

**Step 2:** Mark clean merged/superseded or fully captured ephemeral worktrees `cleanup_eligible`. Preserve dirty, unpublished, unmatched, or unverified work as `quarantined` with an explicit reason.

**Step 3:** Add an exact-path retirement helper that verifies no active KX claim, no owned process, no unique uncommitted diff, and a recoverable Git ref before removing a worktree.

**Step 4:** Start with report-only cleanup. Automatic removal is allowed only for states proven safe by tests; unknown state fails closed.

**Step 5:** Run focused lifecycle tests plus `git worktree list --porcelain` before/after a fixture cleanup to prove no unrelated tree is touched.

## Task 6: Report owned process lifecycle before adding a reaper

**Files:**
- Add: `gateway/agent_process_lifecycle.py`
- Add: `tests/test_agent_process_lifecycle.py`
- Integrate read-only output with the workspace/session report path chosen in Task 5.

**Step 1:** Model only processes with positive Kitty provenance: recorded PID/start identity, owner/session/task, command fingerprint, and workspace association. Age or executable name alone is never ownership proof.

**Step 2:** Classify `active`, `idle`, `orphan_candidate`, and `unknown` from liveness, parent/session/task terminal evidence, and a grace period. Land report-only first.

**Step 3:** A later bounded change may terminate only exact proven-owned orphan candidates after immediate re-verification; generic host-managed Claude/OpenCode/Codex processes remain untouched.

**Step 4:** Add fixtures for reused PID, missing parent, still-active task, and unknown provenance.

## Acceptance evidence

- Builder can reject missing validation tooling or a known-unavailable route before creating a run/attempt.
- An unchanged infrastructure blocker does not consume another worker dispatch.
- Worker startup no longer reads legacy `.claude/HANDOFF.md` or `.claude/STATE.md` by default.
- A continuing task reuses the same authenticated workspace when safe.
- A read-only review does not leave a persistent worktree merely as a side effect.
- Terminal workspaces receive a durable lifecycle disposition; ambiguous/dirty work is preserved rather than deleted.
- Existing KX ownership, Builder evidence gates, and paid-spend admission remain fail-closed.

## Non-goals

Do not delete arbitrary old branches/worktrees in the implementation PR. Do not make network reachability guesses authoritative. Do not auto-resolve KX collisions by force. Do not retry a changed implementation from a clean provider failure. Do not merge workspace cleanup with PR cleanup unless the same authoritative evidence proves both are safe.
