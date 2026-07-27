# Session State — compute governor and session-end survey open as signed-off drafts

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-07-27T05:25:00Z",
  "head_sha": "16c39cff1da34f620cf75804ca91a3ccc8d7876a",
  "branch": "claude/session-end-recommendations-xsd0ss",
  "worktree": ".",
  "status": "awaiting_review",
  "completed_items": [
    "Hardened .agents/skills/session-end/SKILL.md: survey first, evaluate carried release checks, at most three ranked recommendations, life projects before code",
    "Added scripts/session_end_survey.sh - read-only inventory of worktrees, unmerged branches and the paths they touch, open PRs including drafts, the Builder queue, ~/kb/NOW.md, and carried recommendations",
    "Checkpoint schema_version 2 adds parallel_work and recommendations, enforced by gateway/context_receipt.py",
    "Aligned the AGENTS.md session-end protocol with the skill and named the skill its authority",
    "ADR 0022 accepted, registered as D21, docs/adr/README.md updated",
    "Re-walked SKILL_REGISTRY.md: the heading claimed 7 skills, the table listed 6, the directory held 9",
    "Built gateway/compute_governor.py: per-(task_type, subject_ref, head_sha) receipts, enforced dispatch descriptors, three priced routes, reserve floors, weekly local ledger",
    "Wired the governor into run_packet, run_initiative, and both Builder CLI entry points, on by default at the CLI",
    "Derived the weekly budget from the DeepSeek V4 snapshot prices: CAD 6.00/week",
    "Cleared three failures inherited from origin/main: ruff on insight_loop, mypy on routes/knowledge.py, and the checkpoint JSON blocks this file restores"
  ],
  "blockers": [
    "gh is not installed in this container, so the survey could not verify the open-PR queue; PR state came from the GitHub MCP tools instead",
    "~/kb is not present in this container, so no wiki entry, INDEX line, or NOW.md update was written - this session's durable knowledge is still unextracted",
    "DeepSeek V4 pricing could not be re-verified against the live provider page; outbound web search requires approval in this environment"
  ],
  "next_action": "Merge PR #276, then merge origin/main into PR #278 and resolve the AGENTS.md and gateway/ overlap.",
  "parallel_work": [
    {
      "kind": "pr",
      "ref": "#276",
      "owner": "this session",
      "touches": [".agents", "AGENTS.md", "SKILL_REGISTRY.md", "docs", "gateway", "scripts"],
      "observed_at": "2026-07-27T05:20:00Z"
    },
    {
      "kind": "pr",
      "ref": "#278",
      "owner": "this session",
      "touches": ["AGENTS.md", "config", "docs", "gateway", "kitty", "tests"],
      "observed_at": "2026-07-27T05:20:00Z"
    }
  ],
  "recommendations": [
    {
      "id": "extract-session-kb",
      "what": "On the Mac, write the ~/kb wiki entry for the inherited-red-main lesson and append its INDEX line",
      "why": "This session produced durable knowledge that no checkpoint file carries",
      "class": "code",
      "status": "deferred",
      "blocked_by": "~/kb is a separate repo and is not present in this container",
      "release_check": "test -d ~/kb",
      "deferred_count": 0,
      "first_deferred": "2026-07-27"
    },
    {
      "id": "rebase-278-onto-276",
      "what": "After #276 merges, merge origin/main into #278 and resolve the AGENTS.md and gateway/ overlap",
      "why": "Both branches edit AGENTS.md and gateway/; whichever lands second conflicts",
      "class": "code",
      "status": "deferred",
      "blocked_by": "PR #276 has not merged",
      "release_check": "git fetch -q origin main && git merge-base --is-ancestor origin/claude/session-end-recommendations-xsd0ss origin/main",
      "deferred_count": 0,
      "first_deferred": "2026-07-27"
    },
    {
      "id": "reconcile-receipt-cost",
      "what": "Reconcile a receipt's estimated_usage_cad against the actual token counts in the ledger after a run",
      "why": "estimate_cost_cad prices a dispatch before it runs; nothing checks the estimate afterwards",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    }
  ],
  "invalidation_conditions": [
    "HEAD changes beyond 16c39cff1da34f620cf75804ca91a3ccc8d7876a except the checkpoint commit that records this file",
    "PR #276 or #278 merges, closes, or takes new commits",
    "origin/main advances past 00e005b3c3bf88573b38e4448470d678d4821fce"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint

Branch `claude/session-end-recommendations-xsd0ss` at `16c39cf`, clean, merged
up to `origin/main` at `00e005b`. Two draft PRs are open and signed off by
Jacob: #276 (session-end survey, carry-forward recommendations, ADR 0022) and
#278 (compute governor). Both carry fixes for three failures that originated on
`main`, not in this work.

## Lessons applied

- `origin/main` was red on ruff, on mypy, and on its own cold-start acceptance
  test. A branch that merges main inherits all three, so "my PR is red" needed
  checking against the base before it needed debugging.
- CI runs a PR merged into its base, so a green local branch still fails CI on
  the base's breakage.
- The compute governor's first real find was in its own wiring: an
  override-authorized rerun passed the gate and then failed at settlement.
- A governed CLI pointed at one shared receipts store refuses its own second
  test. Receipt stores must be redirectable per checkout.
- An open-PR inventory without `gh` is unverified, never empty.
