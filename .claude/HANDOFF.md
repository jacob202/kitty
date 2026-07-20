# Handoff — Chat Recovery Delivered; Next: Push Decision + IMG-02+

<!-- kitty-handoff
{
  "schema_version": 1,
  "updated_at": "2026-07-20T12:02:00Z",
  "head_sha": "cf6a95c",
  "branch": "feat/image-packets-current",
  "worktree": ".worktrees/image-packets-current",
  "status": "valid",
  "completed_items": [
    "all 7 chat-recovery packets delivered (CR-06/07 directly on main: 78143f6, 9bd57af)",
    "imagen IMG-01 v2 store merged + durable gallery history (b9a8a5d)",
    "tutor DTH-03/04 wired through routes and a TutorPanel, verified live (033cea0)",
    "audit refactor committed and green (c83eb91..33ee509)",
    "branch_leases migration fix for live builder DB (8a434cc)",
    "19 branches + 11 worktrees cleaned; chat-recovery initiatives paused with evidence"
  ],
  "blockers": [],
  "next_action": "Ask Jacob whether to merge this isolated image-packet branch; COMFY_COMMIT pin still needs an operator-selected revision",
  "invalidation_conditions": [
    "HEAD changes beyond da5fc579bdabf20c6d9595c7e25c28becb36868d",
    "branch or registered worktree changes",
    "the active Mission changes"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Resume here

1. Image Lab packets IMG-02..IMG-06 and IMG-G8 are complete on
   `feat/image-packets-current` at `cf6a95c`; backend and frontend checks are
   green. The branch has not been merged or pushed.
2. The ComfyUI workflow is validated against `/object_info`. Set a concrete
   `COMFY_COMMIT` only after Jacob chooses the revision to pin.

1. `main` has 12 unpushed local commits (`221aea6..da5fc57`). Pushing needs
   Jacob's explicit yes — ask before any `git push`.
2. Do NOT rerun chat-recovery packets: `chat-recovery-v1` and
   `chat-recovery-continuation-v1` are paused with evidence notes because
   CR-06/CR-07 (and their b-variants) landed directly on main. Resuming
   those initiatives would rebuild shipped work.
3. The gateway was restarted onto current code and is healthy; the
   kitty-chat dev server may still be running on :4000 (preview session).
4. Next candidates, in rough value order:
   - IMG-02 ComfyUI cancellation + reconciliation (the IMG-01 store it
     needs is now on main), then IMG-03 atomic persistence.
   - Review/land or discard the kept campaign branches (see STATE.md list);
     several reimplement builder governance features and are months of
     drift behind main.
   - reasoning-backend-v1 packets.

## Evidence

- Live verification: tutor quiz answered end-to-end in the browser
  (mastery 51% rendered from a real /tutor/attempt), model-override chip
  armed/cleared, builder home tile healthy after the lease migration.
- `make ui-test && make ui-build` exit 0 (233 UI tests). Python: full suite
  green pre-CR-06 (2537 passed after refactor fixes); every touched area
  re-ran green after (completions 40, tutor 18, imagen 139, builder queue
  13+29 subtests, knowledge 15).
- Worktree drafts discarded during cleanup were all superseded versions of
  the memory-evidence work (confirm-only delete draft, {id,text,index}
  trailer draft); the merged branch + CR-06 implementation covers both.

## Continuity details

- PR descriptions must contain exact `## Summary` and `## Test plan`
  headings. Continue explicit-path staging; never `git add -u` in a mixed
  worktree.
- The preview harness had a stale root binding; `.worktrees/fable-ux-phase`
  is now a symlink to the repo root so `preview_start` works. Harmless, but
  if it confuses anything, delete the symlink.
- Test residue (37 fake image_jobs rows, 2 seeded tutor terms) was wiped
  from the live DBs; current test fixtures are leak-free.
