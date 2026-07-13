# Handoff — 2026-07-12

## TL;DR
PR #164 (ready for review, CI green) on `claude/kittybuilder-dogfood-preflight-bif2qb` delivers: fail-loud sweep across 11 silent except blocks, doc reconciliation (stale handoff refs fixed), CI coverage threshold bumped 10%→65%, and 128 new HTTP-layer route contract tests for 5 modules.

## Resume
1. PR #164 is CI-green and ready to merge
2. Remaining route test coverage: 11 modules still have zero HTTP tests (artifacts/integrations/runtime/memories/experts now covered)
3. Proxy SSRF (Blocker #1) remains T2 — Jacob's call

## Watch out
- The `.claude/worktrees/` directory is gitignored now — agent worktrees are ephemeral
- Coverage threshold is 65%; actual coverage is ~73%. If new code drops below 65% CI will fail.
- Pre-existing test failures in this container (voice, async tests) are due to missing pytest-asyncio/TTS deps locally — CI has them and passes clean.

## T2 (Jacob/Codex only)
- Card A: UI binds 0.0.0.0; proxy injects gateway secret; SSRF in capture/knowledge
- Card B: agent_runner.py / task_runner.py false-complete states; stop() unreliable
