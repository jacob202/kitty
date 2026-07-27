# Handoff — session-end survey and compute governor, both signed off, both draft

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-07-27T05:25:00Z",
  "head_sha": "16c39cff1da34f620cf75804ca91a3ccc8d7876a",
  "branch": "claude/session-end-recommendations-xsd0ss",
  "worktree": ".",
  "status": "valid",
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
  "invalidation_conditions": [
    "HEAD changes beyond 16c39cff1da34f620cf75804ca91a3ccc8d7876a except the checkpoint commit that records this file",
    "PR #276 or #278 merges, closes, or takes new commits",
    "origin/main advances past 00e005b3c3bf88573b38e4448470d678d4821fce"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## What was done

- `.agents/skills/session-end/SKILL.md` — rewritten. Runs `scripts/session_end_survey.sh`
  first, evaluates each carried `release_check`, then produces at most three
  ranked recommendations with life projects ahead of code (ADR 0016).
- `scripts/session_end_survey.sh` — read-only field inventory. Unreachable
  sources print `UNAVAILABLE` with a reason instead of an empty section.
- `gateway/context_receipt.py` — checkpoint `schema_version: 2` with
  `parallel_work` and `recommendations`. A deferred recommendation with no
  `release_check`, or a duplicate id, fails the continuity gate.
- `AGENTS.md` — the session-end protocol matches the skill and names it authority.
- `docs/adr/0022-*.md` — Accepted, registered as D21.
- `SKILL_REGISTRY.md` — re-walked; `expert-swarm` marked UNVERIFIED pending
  Jacob's confirm rather than archived unilaterally.
- `gateway/compute_governor.py` + `_cli.py` — receipts keyed on
  `(task_type, subject_ref, head_sha)`, enforced dispatch descriptors, three
  priced routes (free ladder / V4 Flash / V4 Pro), reserve floors plus an
  affordability check, weekly local ledger. Wired into `run_packet`,
  `run_initiative`, and both Builder CLI commands, on by default at the CLI.

## In-flight / WIP

- PR #276 (this branch) and PR #278 (`claude/compute-governor-receipts`), both
  draft, both signed off by Jacob in a comment (GitHub blocks owner
  self-approval, so there is no formal review approval on either).

## Other work in flight (not mine)

- `origin/main` advanced to `00e005b` mid-session with `gateway/insight_loop.py`
  and a rewritten checkpoint pair from another session. That work is theirs;
  only its CI breakage was touched here.

## Blockers

- `gh` is not installed in this container. The survey's PR section reports
  `UNAVAILABLE`; PR state came from the GitHub MCP tools.
- `~/kb` is absent, so no wiki entry, INDEX line, or NOW.md update was written.
- DeepSeek V4 pricing could not be re-verified against the live page; outbound
  web search needs approval here.

## Next move

Merge PR #276. Then merge `origin/main` into PR #278 and resolve the
`AGENTS.md` and `gateway/` overlap.

## Deferred, and what releases them

- `extract-session-kb` — write the ~/kb wiki entry and INDEX line — blocked by
  `~/kb` being absent here — unblocks when `test -d ~/kb` exits 0.
- `rebase-278-onto-276` — merge main into #278 and resolve the overlap —
  blocked by #276 not merging — unblocks when
  `git merge-base --is-ancestor origin/claude/session-end-recommendations-xsd0ss origin/main`
  exits 0.

## Files changed this session

- `.agents/skills/session-end/SKILL.md`, `scripts/session_end_survey.sh`
- `AGENTS.md`, `SKILL_REGISTRY.md`, `docs/FREE_WORKERS.md`
- `docs/adr/0022-session-end-carry-forward-recommendations.md`, `docs/adr/README.md`, `docs/DECISIONS.md`
- `gateway/context_receipt.py`, `tests/test_context_receipt.py`
- `gateway/compute_governor.py`, `gateway/compute_governor_cli.py`, `tests/test_compute_governor.py`
- `gateway/builder_loop.py`, `gateway/builder_run.py`, `gateway/builder_cli.py`, `tests/test_builder_loop.py`, `tests/conftest.py`
- `gateway/paths.py`, `kitty`, `config/compute_governor.json`
- Inherited-breakage fixes: `gateway/insight_loop.py`, `tests/test_insight_loop.py`, `gateway/routes/knowledge.py`

## Verification

- `pytest tests/ -q` on #278: 3103 passed, 7 failed. Five are the pre-existing
  canonical-path failures (`test_check_continuity_state`, `test_resume_script`),
  which reproduce on the unmodified tree; the sixth and seventh were the
  inherited cold-start acceptance failure this checkpoint pair fixes.
- `pytest tests/test_compute_governor.py tests/test_builder_loop.py -q`: 100 passed.
- `ruff check gateway/ tests/ mcp/`: clean. `mypy gateway/ mcp/`: clean of
  errors in every file this session touched.
- `bash scripts/session_end_survey.sh`: ran end to end; `gh` and `~/kb` correctly
  reported `UNAVAILABLE`.
