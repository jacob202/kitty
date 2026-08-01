# Session State — open-session audit; #355/#356/#358 merged; main green

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-08-01T22:06:59Z",
  "head_sha": "b35a7abf9714858655f1a84fa62476751ce26689",
  "branch": "claude/review-open-sessions-3h65cy",
  "worktree": "kitty",
  "status": "complete",
  "completed_items": [
    "Audited every open session branch against main. 18 of 20 claude/* sessions fully landed; 2 died with unlanded work.",
    "Corrected a measurement error worth keeping: the container clones shallow (16 grafted roots), so merge-base returns empty and merged branches read as 1000+ commits unlanded. Re-ran after --unshallow; main is 1656 commits, not 264. Landing decided on file content so squash merges do not read as loss.",
    "Orphans confirmed by content, not just file presence: main's workers/comfy_worker/entrypoint-kitty.sh has no BOOTSTRAP_PID, so claude/pr-review-48h-aptjw0's PID-1 supervision fix is genuinely unlanded. docs/CONVERSION_PLAN.md exists on claude/conversion-plan-xbsbbi and no other ref.",
    "Merged #356 (febbb99d docs/template), #355 (dda86249 mobile shell + fail-closed Studio), #358 (037052b6 builder dirty-worktree retry) after reviewing each diff rather than trusting green checks.",
    "#355 review checked the fetchImageStatus contract change: dropping its catch makes a dead gateway throw instead of reporting available:false, which is intended. All four consumers reach it via useImageStatus; ImageGenPanel — the one component the PR did not touch — reads statusQuery.data?.available ?? null and degrades to unavailable rather than crashing.",
    "Verified main green after the merges: all 6 Tests jobs passed on 037052b6 (pytest, kitty-chat, browser-smoke, lint, typecheck, hygiene).",
    "Added the 'How to write to Jacob' rule to CLAUDE.md and mirrored it as a one-line standing preference in config/PREFERENCES.md."
  ],
  "blockers": [],
  "next_action": "Await Jacob's call on rescuing the orphaned work and deleting the 18 landed claude/* branches; PR #360 is a green draft he has not marked ready.",
  "parallel_work": [
    "Drafts #359, #361, #362 were opened by other sessions while this one ran. #359 is the docs/builder-cockpit-boundary orphan this audit flagged — it now has a PR. Not mine; do not claim them.",
    "Draft #357 is disposable smoke evidence marked [do not merge].",
    "Six Dependabot PRs (#314-#317, #319, #320) remain open, based on 27deef12, four labelled risk/manual-approval. Not merged here — CLAUDE.md non-negotiable 6 forbids auto-merging dependency work."
  ],
  "recommendations": [
    {
      "id": "rescue-orphaned-session-work",
      "what": "Rescue claude/pr-review-48h-aptjw0's 8 RunPod hardening commits and docs/CONVERSION_PLAN.md from claude/conversion-plan-xbsbbi onto fresh branches with PRs",
      "why": "Both are the only copies. The RunPod set includes PID-1 bootstrap supervision and a test locking the startup diagnostic contract, neither of which is on main",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "close-landed-session-branches",
      "what": "Delete the 18 landed claude/* branches and close draft #357, which is marked [do not merge]",
      "why": "50 unmerged refs make the session-end survey truncate at 8 and hide real orphans behind noise",
      "class": "ops",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "red-ci-must-block-merge",
      "what": "Make a red tests.yml actually block a merge, starting with Dependabot PRs",
      "why": "Sharpens the carried dependabot-guardrail recommendation against evidence: tests.yml:36 already runs 'pip install -r requirements.txt', so the resolvability check exists. What failed on #322 was enforcement — the unresolvable bump merged anyway and main stayed red for 8 commits",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    }
  ],
  "invalidation_conditions": [
    "PR #360 is merged or closed",
    "origin/main advances past 037052b6e58a0c496312cce27a7c913435926566"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": "https://github.com/jacob202/kitty/pull/360"
}
-->

## Dropped from the previous checkpoint

`image-agent-slice-a1` was carried as `ready`; it has shipped. `main` holds
`gateway/image_sessions.py`, `gateway/migrations/029_image_sessions.sql`, and
`tests/test_image_sessions.py`; `92665876` is slice A1, `bcae5f28` is A2 (#351).

The previous checkpoint's own invalidation conditions had both fired before this
write — `origin/main` advanced past `b68268b0` and `tests.yml` went green — so
overwriting it clobbered nothing live.

## Unverified

`gh`, `data/kittybuilder/builder_queue.db`, and `~/kb` are all absent from this
container. Open PRs were checked through the GitHub MCP tools; Builder state and
cross-tool claims were not inspected, and no `~/kb` write happened. Those are
unknown, not clean.
