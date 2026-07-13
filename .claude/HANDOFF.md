# Handoff — 2026-07-13

## TL;DR

PR #164 on `claude/kittybuilder-dogfood-preflight-bif2qb` adds Chat Cutting Edge
waves 1–3: reasoning display, memory visibility, thread-scoped goals, proactive
signal cards, inline memory correction, and per-message model override.
`origin/main` has the workspace cleanup merged (`2b77f6b`); this branch has been
rebased/merged on top of it.

## Resume

1. Continue / finish PR #164:
   - Wave 3b: Goal progress sidebar (`Rail.tsx` or new `SessionSidebar.tsx`)
   - Wave 3e: Reasoning level config (`TopBar.tsx`, `completions.py`)
2. Verify the frontend build (`npm run build`) and frontend tests (`npm test`)
   stay green after wave 3b/3e.
3. Run targeted Python tests for touched route modules.

## Watch out

- The `.claude/worktrees/` directory is gitignored — agent worktrees are ephemeral.
- Coverage threshold is 65%; actual coverage is ~73%. If new code drops below
  65% CI will fail.
- Pre-existing test failures in this container (voice, async tests) are due to
  missing pytest-asyncio/TTS deps locally — CI has them and passes clean.
- Preserve the active builder worktree `.worktrees/kittybuilder/kb_mrh9ilha_f3d9`
  (task `kb_mrh9ilha_f3d9`, modifies `gateway/next_step.py` and
  `tests/test_next_step.py`).

## T2 (Jacob/Codex only)

- Card A: UI binds 0.0.0.0; proxy injects gateway secret; SSRF in
  capture/knowledge routes.
- Card B: `agent_runner.py` / `task_runner.py` false-complete states;
  `stop()` unreliable.
