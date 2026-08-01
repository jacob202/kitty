# Active Mission — Phase 2 Life-First Home Truth

**Roadmap phase:** Phase 2 ("Life-First Daily Driver") in `docs/ROADMAP.md`
**Mission ID:** KLF-001
**Status:** Running
**Phase linkage:** This mission sits within Phase 2 of the roadmap. Phase 2 was
not defined when KLF-001 was authored; the roadmap now defines it and this
mission is its active execution thread.

<!-- kitty-mission
{
  "schema_version": 1,
  "mission_id": "KLF-001",
  "status": "running",
  "approved_at": "2026-07-31T11:29:42Z",
  "approved_by": "Jacob",
  "base_sha": "da88c21bdd323f2d11a5e344c6fa0129668652a4",
  "authority": "docs/ACTIVE_MISSION.md"
}
-->

## Objective
Finish the recovered August life-first plan by making Home reliably expose one
truthful life-project move, independently from active chat state or transient
startup failures.

## Authorization
Jacob explicitly instructed OpenCode to recover, review, and execute the prior
monthly plan, then approved reapplying the verified Home/Chat separation after
a concurrent worktree reset.

## Scope
1. Keep Home and Chat as separate product surfaces.
2. Recover automatically from a transient Gateway health timeout.
3. Ensure `/repairs` runs blocking checks outside the event loop.
4. Label Builder transition-history defects accurately rather than as leases.
5. Report healthy Kitty-owned listeners as running even when pidfiles are stale.
6. Reconcile mission and checkpoint metadata with live Git state.

## Acceptance Contract
- Home renders the life-first dashboard even when the active chat has messages.
- A transient startup health failure retries and reaches the application.
- Live Repairs reports the healthy Gateway and LiteLLM as healthy.
- Builder rows lacking event history are not described as stale leases.
- `./kitty status` reports healthy Kitty-owned listeners as running.
- Focused frontend and backend tests pass.
- The running app shows the same life-first step at desktop and mobile widths,
  with no horizontal mobile overflow.
- `./kitty context --agent` has no continuity failures.

## Publication Authorization
Jacob explicitly authorized commit, push, PR review, and merge for this mission.
Secrets, auth, `.env`, paid execution, destructive data changes, new
orchestration machinery, and unrelated product expansion remain excluded.
