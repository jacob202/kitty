# Handoff — 2026-07-09

## What's working
- Gateway on 8000, UI on 4000, both responsive
- Frontend proxy works (`/proxy/health` → gateway health)
- 7 real projects in DB (IDs 1-3, 504-507), no more swarm clutter
- `project_store` delete fixed (wrong table name)
- `data/kitty.db` stale copy deleted — only `data/kitty/kitty.db` exists now
- 103/103 frontend tests pass, production build compiles
- Home cockpit now uses the dark cosmic visual direction and existing Kitty mascot assets.
- Home `select space` lists the real existing projects from `/proxy/projects` (7 projects: IDs 1-3, 504-507) instead of pushing Jacob to create fake projects.
- Mobile visual QA no longer has the fixed cat overlapping project rows; Brain card filenames ellipsize instead of overflowing.
- The brief timeout banner was fixed on the frontend side: `/proxy/brief` now gets a 5000ms abort budget, and a regression test covers a 2.1s successful cold-cache/fallback response.
- Dev `4000` now renders the cockpit in Chrome with HMR connected; the stale blank-shell symptom was cleared by restarting the dev server with the current Next dev-origin config.
- `/magic` no longer blocks the FastAPI event loop; the route runs Magic Kitty's synchronous LLM workflow in a worker thread.
- Magic Kitty caches valid empty insight results, but LLM/resume failures now raise loudly instead of being stored as fake empty success.
- Home first-paint proxy pressure is lower: project next-step queries are shared inside `HomeState`, and loops/insights/prompts wait until the Tools view is open.

## What needs attention
1. **PR #119**: open, but the local branch has unpushed follow-up commits. Do not assume PR #119 contains these follow-ups until Jacob approves a push. Current notable local commits include:
   - `a1728e9 fix(home): reduce startup request blocking`
   - `70018c8 fix(magic): fail loud on discovery errors`
   - `bb8cdf6 feat(imagen): add init_image support to generate_until and verify pipelines`
2. **Service pidfiles**: Gateway/LiteLLM are healthy via attached Codex sessions, but `./kitty status` says `not running` from pidfiles while health checks are green. Re-run/repair `./kitty up` backgrounding if the next session needs detached services.
3. **UI**: dark cockpit first slice is implemented and live on 4000. Jacob may still want more polish/density to get closer to the Stitch mockup.
4. **Unmerged**: `feat/port-kittybuilder` still on its worktree branch, never merged to main.
5. **Gateway port**: `.env` `GATEWAY_PORT` field keeps reverting to 8000. Something resets it. Gateway reads from env but the frontend proxy hardcodes `http://127.0.0.1:8000` at `proxy/[...path]/route.ts:13` as fallback.
6. **Unrelated dirty files**: `.agents/skills/engineering/improve-codebase-architecture/INTERFACE-DESIGN.md` and `.agents/skills/engineering/improve-codebase-architecture/SKILL.md` remain uncommitted.
7. **Commit attribution wrinkle**: `mcp/imagen/engines/drawthings.py` landed inside `70018c8` while imagen work was moving concurrently; `bb8cdf6` then added the matching `generate_until`/`verify` plumbing. Do not revert Draw Things img2img support casually because the imagen lane now appears to depend on it.

## Latest verification
- `./kitty status` → pidfiles say not running, but health checks are green for Gateway 8000 and LiteLLM 8001 because services are attached to Codex sessions.
- Live Chrome verification on `http://127.0.0.1:4000` → cockpit renders, HMR connected, no `Brief unavailable`, `changes unavailable`, or `gateway offline` text.
- Temporary 4001 production preview was stopped after 4000 dev was fixed; use `http://127.0.0.1:4000`.
- `python3.12 -m pytest tests/test_magic_route.py tests/test_brief.py tests/test_brief_deadlines.py -q --tb=short` → 32 passed in 7.19s.
- `python3.12 -m pytest tests/test_magic_kitty.py tests/test_magic_route.py tests/test_brief.py tests/test_brief_deadlines.py -q --tb=short` → 37 passed.
- `cd gateway/kitty-chat && npm test` → 16 files / 103 tests passed.
- `cd gateway/kitty-chat && npm run build` → pass; Next build completed TypeScript/static generation successfully.
- `/Users/jacobbrizinski/Projects/kitty/venv/bin/pre-commit run --files gateway/routes/magic.py tests/test_magic_route.py gateway/kitty-chat/src/app/page.tsx gateway/kitty-chat/src/components/HomeState.tsx gateway/kitty-chat/src/lib/queries.ts` → pass.
- `git commit -m "fix(home): reduce startup request blocking"` → `a1728e9`.
- `/Users/jacobbrizinski/Projects/kitty/venv/bin/ruff check gateway/magic_kitty.py tests/test_magic_kitty.py` → pass.
- `/Users/jacobbrizinski/Projects/kitty/venv/bin/ruff format --check gateway/magic_kitty.py tests/test_magic_kitty.py` initially wanted formatting; after `ruff format`, tests passed again.
- `/Users/jacobbrizinski/Projects/kitty/venv/bin/pre-commit run --files gateway/magic_kitty.py tests/test_magic_kitty.py` → pass.
- `git commit -m "fix(magic): fail loud on discovery errors"` → `70018c8`.
- Concurrent/new local commit observed after that: `bb8cdf6 feat(imagen): add init_image support to generate_until and verify pipelines`.
- Playwright screenshots via system Chrome channel:
  - `/tmp/kitty-cockpit-desktop-final2.png`
  - `/tmp/kitty-cockpit-mobile-warm-final.png`
  - `/tmp/kitty-cockpit-mobile-bottom-final.png`
  - `/tmp/kitty-home-brief-check-4001.png`
  - `/tmp/kitty-dev-4000-request-burst-reduced.png`

## Env notes
- `DT_URL=http://127.0.0.1:7859`, `VISION_MODEL=moondream`, `DT_MODEL=Juggernaut XL Ragnarok`
- GATEWAY_PORT=8000 (keeps reverting despite edits)
- `GITHUB_TOKEN` env var has working `ghp_` PAT; `gh auth status` shows `gho_` OAuth from keychain

## Packet status
- 001-015 shipped
- 016 blocked — Jacob needs to judge Bs for registered projects
- 017 PR #112 open (move-in blocker)
- 018 PR #119 open; local follow-up commits are not pushed
- 020 claimed by Antigravity
- 022 partial code in 018 batch
- 023 spec exists
- 024 spec exists, phase 1 built
- 025 committed
