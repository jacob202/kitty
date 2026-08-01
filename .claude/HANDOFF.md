# Handoff — open-session audit, three PRs merged, new writing rule

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-01T22:06:59Z",
  "head_sha": "b35a7abf9714858655f1a84fa62476751ce26689",
  "branch": "claude/review-open-sessions-3h65cy",
  "worktree": "kitty",
  "status": "valid",
  "pull_request": "https://github.com/jacob202/kitty/pull/360",
  "completed_items": [
    "Audited all 20 claude/* session branches plus every other agent branch against main. 18 of 20 are fully landed (8 tips are ancestors of main, 9 squash-merged with content verified present, 1 closed-unmerged but superseded via #339).",
    "Found the shallow-clone measurement trap: the session container clones with 16 grafted roots, so git merge-base returns empty and merged branches read as 1000+ commits unlanded. Redone after --unshallow (main is 1656 commits, not 264); landing decided on file content, not commit identity.",
    "Two Claude sessions died with unlanded work: claude/pr-review-48h-aptjw0 (8 RunPod hardening commits above merged #326; scripts/runpod_live_james.sh and tests/test_runpod_bootstrap_contract.py absent from main; main's entrypoint-kitty.sh has no BOOTSTRAP_PID) and claude/conversion-plan-xbsbbi (#266 closed as draft; docs/CONVERSION_PLAN.md exists on no other ref).",
    "Larger orphan found outside the Claude sessions: docs/builder-cockpit-boundary, 28 commits and 10 files including ADRs 0024/0025/0026, with no PR ever opened. It has since been opened as draft #359. contract-first (#298 closed) still holds the OpenAPI->TS pipeline behind response models on 193 routes.",
    "Reviewed and merged #356 (febbb99d), #355 (dda86249), #358 (037052b6). Verified main green afterward: all 6 Tests jobs passed on 037052b6.",
    "#358 was blocked by its PR body, not its code: no bullet under '## Summary' and a '## Verification' heading where .github/workflows/pr-description-check.yml:41-47 requires the literal '## Test plan'. Body rewritten with content preserved; gate passed; merged.",
    "Added the 'How to write to Jacob' rule to CLAUDE.md (Working Contract) and a one-line mirror in config/PREFERENCES.md: plain language, no narration, every reply is instructions/a report/options, never vague status."
  ],
  "blockers": [],
  "next_action": "Decide the disposition of the orphaned work (rescue or drop) and whether to delete the 18 landed claude/* branches; PR #360 is a green draft awaiting Jacob.",
  "invalidation_conditions": [
    "PR #360 is merged or closed",
    "origin/main advances past 037052b6e58a0c496312cce27a7c913435926566"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "parallel_work": [
    "Draft #359 (docs/builder-cockpit-boundary) — the KB learning + Builder boundary orphan, opened by another session during this one. Not mine; do not claim it.",
    "Draft #361 (claude/builder-52dcp7) — 026/027 delta reconcile. Not mine.",
    "Draft #362 (feat/kittybuilder-reviewer-pro) — reviewer on deepseek-v4-pro. Not mine.",
    "Draft #357 (kittybuilder/kb_msaux1t9_e46f) — disposable paid smoke evidence, marked [do not merge]. Close without merging.",
    "Six Dependabot PRs open (#314-#317, #319, #320), all based on 27deef12 and well behind main; four carry risk/manual-approval."
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
  ]
}
-->

## Completed recommendation

`image-agent-slice-a1`, carried from the previous checkpoint as `ready`, has
shipped and is dropped rather than carried. Verified on `main`:
`gateway/image_sessions.py`, `gateway/migrations/029_image_sessions.sql`, and
`tests/test_image_sessions.py` exist; `92665876` is slice A1 and `bcae5f28` is
A2 (#351).

## Unverified at session end

Three survey sections came back `UNAVAILABLE` and are unknown, not clean:

- **Open PRs** — `gh` is not installed in this container. Checked through the
  GitHub MCP tools instead; the open queue is recorded in `parallel_work` above.
- **Builder queue** — `data/kittybuilder/builder_queue.db` does not exist here,
  so Builder state was not inspected.
- **Cross-tool claims** — `~/kb` is not present in this container, so
  `~/kb/NOW.md` was not read and neither `~/kb/wiki/` nor `~/kb/INDEX.md` was
  written. The durable finding worth carrying there is the shallow-clone trap
  recorded in `docs/research/open-session-audit-2026-08-01.md`.

## Files changed

- `docs/research/open-session-audit-2026-08-01.md` (new) — the full audit.
- `CLAUDE.md` — new "How to write to Jacob" section in the Working Contract.
- `config/PREFERENCES.md` — one-line mirror of that rule.

All committed and pushed to `claude/review-open-sessions-3h65cy`; working tree
clean. PR #360 is a draft, 13/13 checks green, `mergeable_state: clean`.
