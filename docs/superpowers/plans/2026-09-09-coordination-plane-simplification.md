# Coordination Plane Simplification Implementation Plan

**Goal:** Keep KX collision safety while making coordination cheap enough that agents spend context on the task rather than lease chatter, stale handoffs, and broad workspace scans.

**Architecture:** Preserve KX as mutation-ownership authority and `workspace_global` as durable human/agent communication. Stop using GAR broadcasts as a shadow state feed for facts already queryable from KX/Builder/GitHub. Prefer direct/threaded assignments and on-demand state projection.

**Audit evidence:** the recent GAR stream was overwhelmingly broadcast traffic, while active work frequently depended on a small number of direct ownership/assignment facts. Historical sessions repeatedly reacquired context after lease expiry and sometimes discovered coarse resource conflicts only after substantial work.

## Task 1: Separate machine state from communication

**Files:**
- Modify: `gateway/agent_room_cli.py`
- Modify: `gateway/agent_workspace.py`
- Modify: `tests/test_agent_room_cli.py`
- Modify: `tests/test_agent_workspace.py`

**Step 1:** Classify routine claim acquire/renew/release/heartbeat events as machine-state telemetry rather than default workspace conversation.

**Step 2:** Keep conflict, handoff, blocked dependency, review request, acceptance result, and terminal closeout messages visible because they require another actor's attention.

**Step 3:** Add a query/projection path that can show current KX ownership on demand without replaying historical lease chatter into the agent's conversational context.

**Step 4:** Add regression tests proving an agent can reconstruct active ownership after routine lease broadcasts are filtered from its normal catch-up view.

## Task 2: Make assignments direct and resumable

**Files:**
- Modify: `docs/reference/MULTI_AGENT_COORDINATION.md`
- Modify: `START_HERE.md`
- Modify: `.agents/skills/next/SKILL.md`
- Modify: `tests/test_documentation_authority.py`

**Step 1:** Define the default assignment contract as one direct/threaded locator containing outcome, owner, role, base SHA, workspace, bounded scope, stopping condition, and continuation pointer.

**Step 2:** Require continuations to reuse that locator and existing lane when recoverable instead of publishing a fresh root broadcast and recreating context.

**Step 3:** Make stale compatibility checkpoints explicitly non-authoritative for worker startup; current KX/Git/Builder/GitHub evidence wins.

**Step 4:** Update documentation tests so future guidance cannot reintroduce broad-broadcast-first coordination.

## Task 3: Add a concurrency budget before fan-out

**Files:**
- Modify: `.agents/skills/next/SKILL.md`
- Modify: `docs/reference/MULTI_AGENT_COORDINATION.md`
- Modify relevant policy tests in: `tests/test_documentation_authority.py`

**Step 1:** Default to one mutating outcome owner. Additional mutating workers require a documented independent scope with no path/semantic collision and a clear merge/handback point.

**Step 2:** Default child fan-out to at most two concurrent implementation workers unless the plan explicitly justifies more. Nested worker-created swarms are off by default.

**Step 3:** Read-only research/review may run in parallel when it does not acquire mutation ownership or create persistent workspaces.

**Step 4:** If coordination overhead exceeds expected task effort, collapse back to one owner rather than adding a supervisor layer.

## Task 4: Surface collisions before an agent starts working

**Files:**
- Modify: `gateway/agent_coordination.py`
- Modify: `gateway/builder_supervisor.py`
- Modify: `tests/test_agent_coordination_acceptance.py`
- Modify: `tests/test_builder_preflight.py`

**Step 1:** Make preflight report both path and semantic ownership conflicts in a compact machine-readable form before dispatch.

**Step 2:** Where a coarse semantic resource conflicts but concrete paths do not, return the exact conflicting owner/resource and whether a narrower claim would be valid. Do not silently force or widen ownership.

**Step 3:** Ensure missing KX registry coverage is surfaced during admission rather than after the worker has already spent context preparing an edit.

**Step 4:** Add tests showing a blocked collision creates no worker/run/attempt and that a non-overlapping narrow scope can proceed without waiting on an unrelated broad claim.

## Task 5: Measure coordination signal-to-noise

**Files:**
- Extend: `scripts/engineering_efficiency_report.py` from the telemetry plan
- Modify: `tests/test_engineering_efficiency_report.py`

**Step 1:** Report root broadcasts, thread replies, directs, claim-telemetry messages, handoffs, and actionable dependency messages for a selected time window.

**Step 2:** Report median time from assignment to first mutation and time spent blocked on ownership where timestamps allow it.

**Step 3:** Establish a post-change comparison without turning a message-count target into a hard product SLO.

## Acceptance evidence

- Routine claim/heartbeat traffic no longer dominates an agent's normal catch-up context.
- Active ownership remains reconstructable directly from KX.
- New mutating work defaults to one owner and bounded fan-out; nested swarms require explicit justification.
- Collision/missing-registry blockers are visible before worker dispatch.
- Continuations reuse existing direct/threaded assignment locators and recoverable workspaces.
- Coordination metrics can show whether chatter and ownership wait actually decreased.

## Non-goals

Do not remove KX, GAR durability, lease expiry, or collision protection. Do not make direct messages a hidden source of ownership truth. Do not auto-force-release another active owner. Do not encode a permanent numeric concurrency limit in a way that blocks deliberately approved parallel campaigns; the first limit is a default safety/economics policy with explicit override evidence.
