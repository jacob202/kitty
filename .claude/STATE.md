# Session State — 2026-07-09

## Current branch
`claude/packet-018-expert-packs` — PR #119 open; local branch has unpushed follow-up commits.

## Done (this session)
- PR #119 opened: CORS ports, project delete fix, brief timeout fix, LiteLLM db config, dark cosmic cockpit UI, kitty start command
- Fixed `project_store.py` table name bug: `next_steps` → `project_next_steps`
- Deleted 500 swarm-test projects (IDs 4-503) from DB — 7 real projects remain
- Deleted stale `data/kitty.db` (root)
- Fixed LiteLLM `/health` crash: added `database_url: null` to config, installed `prisma` in venv
- Confirmed proxy works, all 102 frontend tests pass, production build succeeds
- Gateway on 8000, UI on 4000, LiteLLM on 8001 — all healthy
- Continued UI reliability cleanup on 2026-07-09:
  - Verified the 4000 blank-shell symptom was a Next dev HMR origin issue; after restarting the dev server, `4000` hydrates and HMR connects.
  - Moved `/magic` route's blocking cross-project LLM work into `asyncio.to_thread` so Magic Kitty no longer blocks unrelated home dashboard requests.
  - Reduced home first-paint proxy pressure by sharing project next-step queries inside `HomeState` and only loading loops/insights/prompts when the Tools view is open.
  - Made Magic Kitty cache valid empty insight results without caching LLM/resume failures as fake empty success.
  - Verified the live `4000` cockpit in Chrome: no false `Brief unavailable`, `changes unavailable`, or `gateway offline` text after the request-burst fix.
  - Committed local follow-up: `a1728e9 fix(home): reduce startup request blocking`.
  - Fresh verification: `python3.12 -m pytest tests/test_magic_route.py tests/test_brief.py tests/test_brief_deadlines.py -q --tb=short` → 32 passed; `npm test` → 103 passed; `npm run build` → pass; targeted pre-commit hooks → pass.
  - Follow-up verification: `python3.12 -m pytest tests/test_magic_kitty.py tests/test_magic_route.py tests/test_brief.py tests/test_brief_deadlines.py -q --tb=short` → 37 passed.
  - Committed Magic Kitty fail-loud follow-up: `70018c8 fix(magic): fail loud on discovery errors`.
  - Fresh Magic Kitty verification: `python3.12 -m pytest tests/test_magic_kitty.py tests/test_magic_route.py -q --tb=short` → 6 passed; `ruff check` → pass; `ruff format` applied to `gateway/magic_kitty.py`; targeted pre-commit hooks → pass.
  - Observed concurrent/new imagen commit on the same branch: `bb8cdf6 feat(imagen): add init_image support to generate_until and verify pipelines`.

## In-flight / Blocked
- **PR #119** — awaiting review/merge, but local follow-up commits are not on the remote PR branch until Jacob approves push.
- **LiteLLM** — healthy now, but some models still fail (Claude Sonnet needs ANTHROPIC_API_KEY, Gemini 2.0 Flash endpoint expired, AgentRouter needs API key)
- **Service pidfiles** — Gateway/LiteLLM are currently healthy via attached Codex sessions, but `./kitty status` reports `not running` for pidfiles while health checks are green. If the next session needs long-lived services outside Codex, re-run/repair `./kitty up` backgrounding.
- **Unrelated dirty files** — `.agents/skills/engineering/improve-codebase-architecture/INTERFACE-DESIGN.md` and `.agents/skills/engineering/improve-codebase-architecture/SKILL.md` were left uncommitted.
- **Commit attribution wrinkle** — `mcp/imagen/engines/drawthings.py` landed in `70018c8` while imagen work was moving concurrently; `bb8cdf6` adds the matching imagen pipeline calls, so do not revert Draw Things img2img support casually.
- **Kitty Builder**: `feat/port-kittybuilder` still unmerged

## Next actions
1. If Jacob approves, push `claude/packet-018-expert-packs` so PR #119 includes the local follow-up commits.
2. After push, confirm CI check runs are green before merging PR #119.
3. Merge Kitty Builder branch if still wanted.
4. Packet 016: Jacob judges Bs for registered projects.
