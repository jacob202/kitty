# Handoff

<!-- kitty-handoff
{
  "active_mission": "docs/ACTIVE_MISSION.md",
  "blockers": [
    "#874 needs a risk label, an exact-head approval and a review override, all of which only Jacob can originate. Recommendation from this review is to close it and switch to the already-built local reviewer instead.",
    "#870 (R-3) is blocked on 6 unresolved reviewer threads; the end-to-end product journey has still never been driven.",
    "Builder autonomy stays off: ~/Library/LaunchAgents/com.kitty.builder.supervisor.plist still points ProgramArguments[1] and WorkingDirectory at /Users/jacobbrizinnski/Projects/kitty-autonomy-runtime, which does not exist. Editing LaunchAgents was blocked by the sandbox, so this needs Jacob or an explicit permission."
  ],
  "branch": "main",
  "completed_items": [
    "RESTORED the product. Stopped the scratch stack (pids proven to own 8100/8101/4100 before signalling, per the 2026-09-01 kill-by-port correction), fast-forwarded main 505bdc09 -> a98f2fee, rebuilt the UI because the existing .next predated the R-2 source changes, and started gateway + LiteLLM + UI on canonical 8000/8001/4000.",
    "VERIFIED the restore: /health ok with litellm_reachable true, UI HTTP 200, ./kitty status reports build source a98f2fee with freshness checkout-current and gateway-truth PASS, ./kitty doctor 39 PASS / 8 WARN / 0 FAIL (was 2 FAIL).",
    "VERIFIED Jacob's real data is intact and served: data/kitty/kitty.db holds 5 projects, 16 chat conversations, 140 artifacts.",
    "CLEANED the workspace: 26 worktrees -> 5, 87 branches -> 61. Every dirty worktree's uncommitted diff was preserved as a patch under ~/kb/evidence/worktree-cleanup-20260914/ before removal. Only provably-merged branches were deleted with git branch -d; squash-merge candidates were left alone because git cherry cannot distinguish them from genuine unlanded work.",
    "COMMITTED 196f3ae6: four skills (catchup, debug-fix, remember, second-opinion) and three standing preferences that had been untracked for days.",
    "FOUND the identity defect behind the blocked commit: gateway/agent_coordination_cli.py:98 defaults KITTY_AGENT_PARTICIPANT to 'chatgpt', so any agent without that env var commits as chatgpt, and .git/kitty-agent-session held an expired chatgpt session. Worked around by claiming docs:roadmap as claude; the default itself is unfixed."
  ],
  "head_sha": "196f3ae6ea106bee4e3531dfe79f5b135cb362a5",
  "invalidation_conditions": [
    "origin/main advances past a98f2fee.",
    "#874 is merged or closed, or #870's reviewer threads are resolved.",
    "The canonical stack is stopped or restarted, which changes every runtime observation here."
  ],
  "next_action": "ready:switch-reviewers",
  "parallel_work": [
    {
      "kind": "pull_request",
      "observed_at": "2026-09-15T02:15:00Z",
      "owner": "other-lane",
      "ref": "#870",
      "touches": [
        "gateway/mission_runtime.py",
        "gateway/routes/missions.py"
      ]
    },
    {
      "kind": "pull_request",
      "observed_at": "2026-09-15T02:15:00Z",
      "owner": "other-lane",
      "ref": "#874",
      "touches": [
        "scripts/pr_review.py",
        "scripts/pr_review_gate.py"
      ]
    },
    {
      "kind": "branch",
      "observed_at": "2026-09-15T02:15:00Z",
      "owner": "other-lane",
      "ref": "feat/expert-evidence-runtime-20260913",
      "touches": [
        "gateway/expert_evidence.py"
      ]
    }
  ],
  "pull_request": null,
  "recommendations": [
    {
      "blocked_by": null,
      "class": "life",
      "deferred_count": 0,
      "first_deferred": null,
      "id": "switch-reviewers",
      "release_check": null,
      "status": "ready",
      "what": "Close #874, set KITTYBUILDER_LOCAL_REVIEW_SHADOW to enable gateway/local_review.py, and stop investing in scripts/pr_review.py.",
      "why": "The local reviewer is already built, benchmarked across 15 models, and its 4.6GB model is on disk; it is gated behind an env var set in zero files. Meanwhile scripts/pr_review.py took 36 commits since Aug 15 without once improving what it looks for, stalls at 240s on a 40-line diff, and burns paid calls for no verdict. ADR-0041 also establishes the human-approval gate #874 protects is unenforceable while agents act as jacob202."
    },
    {
      "blocked_by": null,
      "class": "code",
      "deferred_count": 0,
      "first_deferred": null,
      "id": "enforce-dont-record",
      "release_check": null,
      "status": "ready",
      "what": "Turn the three repeatedly-relearned lessons into mechanisms: the WIP stop-intake rule into scripts/hooks/pre-push reading kb-effectiveness.jsonl; a promoted signal must name an implementing SHA or path or session_end_survey.sh fails it; and fix gateway/agent_coordination_cli.py:98 so participant identity is never silently 'chatgpt'.",
      "why": "The 2026-09-12 council reached the WIP conclusion independently three times and it was written into ~/kb/PLAYBOOK.md, which agents do not read; the backlog then went to 54 completed_unreviewed against a rule that says stop at 2. A promoted signal with no mechanism recurred three times in four days."
    },
    {
      "blocked_by": null,
      "class": "code",
      "deferred_count": 0,
      "first_deferred": null,
      "id": "close-r3-by-driving-it",
      "release_check": null,
      "status": "ready",
      "what": "Resolve the 6 reviewer threads on #870, merge it, then actually drive chat request -> proposal -> approve -> Work progress -> real result -> Library -> Chat, plus one interruption and reload, at desktop and iPhone-class widths.",
      "why": "R-3 and BUILDER-001 are the same job and it is the only remaining step before the return program's value checkpoint. Merging #870 is not this item; driving the journey is."
    }
  ],
  "schema_version": 2,
  "session_id": "claude-6fb80449814b4824a85ef292910078e5",
  "status": "awaiting_review",
  "updated_at": "2026-09-15T02:15:00Z",
  "worktree": "."
}
-->

## What happened this session

A read-only consolidation review, then two authorised actions: Kitty was restored and the
workspace was cleaned.

**Restored.** The scratch acceptance stack in `/private/tmp` was stopped (PID ownership of
8100/8101/4100 proven first), `main` fast-forwarded `505bdc09` -> `a98f2fee`, the UI rebuilt
because the existing `.next` predated the R-2 source changes, and the canonical stack started on
8000/8001/4000. `kitty doctor` went from 2 FAIL to 0 FAIL. Jacob's real data is served: 5 projects,
16 conversations, 140 artifacts.

**Cleaned.** 26 worktrees -> 5; 87 branches -> 61. Every dirty worktree diff was preserved as a
patch under `~/kb/evidence/worktree-cleanup-20260914/` before removal. Only provably-merged
branches were deleted.

## The finding worth carrying

`gateway/agent_coordination_cli.py:98` defaults `KITTY_AGENT_PARTICIPANT` to `"chatgpt"`. Any agent
that does not set it commits as ChatGPT, and `.git/kitty-agent-session` was pinning an expired
ChatGPT session, which blocked a commit from this session. This is the same class of defect as
ADR-0041's finding that human approvals are unattributable: identity is assumed, never established.

## Next move

Close #874 and switch to the already-built local reviewer (`gateway/local_review.py`, gated behind
`KITTYBUILDER_LOCAL_REVIEW_SHADOW`, set in zero files, model already on disk). Then turn the
repeatedly-relearned lessons into mechanisms rather than notes. Then close R-3 by driving the
journey, not by merging #870.

## DO NOT REDO

The consolidation, the branch/worktree triage, the 93%/4% measurement, the launchd and queue-state
verification, or the month-long log archaeology of GAR and reviewer effectiveness.
