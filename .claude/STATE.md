# Session State — PR 229 reconciled, INIT-1 v2 ready for B1

<!-- kitty-state
{
  "schema_version": 1,
  "updated_at": "2026-07-23T03:45:00Z",
  "head_sha": "5533deb376540309e0948cadb7a4d9e7eb815d6c",
  "branch": "main",
  "worktree": ".",
  "status": "in_progress",
  "completed_items": [
    "PR #229 reconciled: it silently collided with main's L-CAND-14/15 lessons under the same slot numbers (git's textual merge auto-resolved it by deleting main's entries) — restored both, renumbered the PR's two lessons to L-CAND-16/17, took main's current .claude/HANDOFF.md/STATE.md over the branch's stale copies. Merged as #229 (squash, 3e352a0) after all 7 checks went green.",
    "B1-dogfood-preflight adjudicated: exhausted at 2/2 attempts on a repo:identity false-positive in builder doctor, root-cause-fixed in main (ebd1a93) after INIT-1 v1 was already applied. Manifests are immutable (InitiativeConflictError) and base_sha is resolved once at apply time, so v1 could never pick up the fix. Paused v1 with a documented reason, applied kitty-endgame-init-1-builder-closeout-v2 (same 5 packets, fresh base_sha) — B1 is eligible again.",
    "val-cli / val-cli-fail duplicate initiatives resolved: both were CLI-validation test fixtures from 2026-07-20 (placeholder objective 'Do the first thing', validation_commands true/false), not real work. Operator-cancelled all 4 tasks across both; they now show state=failed instead of confusing duplicate 'active' Kitty Alpha build entries.",
    "Merge rail fixed (docs/LEARNINGS.md L-CAND-15, both halves): merge_and_verify (gateway/builder_publish.py) now rebases the packet's own branch onto fresh main and force-pushes-with-lease only on a clean rebase, retrying the merge once — a rebase conflict is never force-pushed, the original error still propagates. Documented as ADR 0018 amendment 7. CLAUDE.md's Session State section now tells sessions to re-read STATE.md/HANDOFF.md fresh before writing and not clobber a different active workstream's narrative; clarified the convention is for Jacob's interactive sessions, not isolated Builder workers (whose brief already forbids touching .claude/).",
    "Verified via runtime manifest (curl against /runtime/manifest, the exact endpoint BuilderSurface.tsx consumes): val-cli/val-cli-fail show failed, INIT-1 v1 shows paused with the documented reason, INIT-1 v2 shows active with next_packet=B1-dogfood-preflight. Started the kitty-chat dev server (was dead, PID from a prior note had died) to do this check live, not from code inspection.",
    "All 171 focused tests pass (test_builder_publish.py, test_builder_initiative.py, test_builder_doctor.py). kitty doctor: 36 pass/8 warn/0 fail. builder initiative doctor: 13 pass/1 warn/0 fail (warn = expected paused-initiative list)."
  ],
  "blockers": [],
  "next_action": "Jacob runs B1-dogfood-preflight (and the rest of INIT-1 v2's chain) himself via KittyBuilder's CLI/UI now that the queue is clean and the merge rail is fixed — this was his explicit ask, not something to run unattended on his behalf.",
  "invalidation_conditions": [
    "HEAD changes beyond 5533deb376540309e0948cadb7a4d9e7eb815d6c",
    "origin/main advances beyond 5533deb376540309e0948cadb7a4d9e7eb815d6c"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint

`main` = `origin/main` at `5533deb`, pushed. PR #229 merged. Merge-rail gap
(L-CAND-15) fixed and documented (ADR 0018 amendment 7). `.claude/`
clobbering gap (L-CAND-16) fixed via a CLAUDE.md scoping addition.

## Endgame checkpoint

`kitty-endgame-init-1-builder-closeout-v1` is paused (exhausted B1, immutable
manifest, documented reason in its pause_reason). `-v2` is active with B1
eligible — same 5 packets, fresh base_sha off current main. Nothing else in
the whole queue is eligible right now, so there is no cross-initiative
collision risk to worry about when B1 runs.

## Known follow-up

- The CP-06 tripwire and auto-revert path are still unexercised — no revert
  has occurred in real use yet. A deliberate revert drill (daily-driver plan
  §3.3, negative test 4) is still owed before trusting them unattended.
- `feat/reasoning-engine-current` remains Jacob's separate live WIP,
  untouched by this session.
- The kitty-chat dev server needs to be started manually
  (`cd gateway/kitty-chat && npm run dev`) — it is not managed by launchd
  like gateway/litellm, so it doesn't survive a reboot/logout on its own.
