# Kitty - Claude Code

Start here: `START_HERE.md`.

## Project Paths

- Active project: `~/Projects/kitty` (NOT Desktop backups)
- Always verify the Git common directory belongs to `~/Projects/kitty`; an
  isolated worktree may live below that canonical checkout
- If working directory is under `~/Desktop/` or a backup folder, STOP and ask user to confirm

## Cold-start bootloader

Do this before relying on inherited context:

1. Verify the canonical checkout and current worktree.
2. Inspect `git status --short --branch`, HEAD, worktrees, and `origin/main`.
3. Run `./kitty context --agent`; stop on failed freshness checks.
4. Follow the receipt's reading order beginning with `docs/AUTHORITY_MAP.md`.
5. Read `docs/ACTIVE_MISSION.md` and `.claude/STATE.md`.
6. Read `.claude/HANDOFF.md` only when its structured status is `valid`.
7. Inspect Builder through `./kitty builder ... --json` when Builder state is relevant.
8. Re-verify scope, evidence, and authorization before acting.

## Execution Defaults

- When user requests a feature/fix, complete the FULL loop: implement + install/setup + verify locally. Do not stop after writing code.
- Run the test suite after any non-trivial code change and report pass/fail counts.
- Local commits are expected; pushing still requires Jacob's explicit approval.

## Auth & Environment

- Before any `gh` or git push, check for stale `GITHUB_TOKEN` env var and unset if it conflicts with `gh auth`
- For LiteLLM/MLX setups: prefer existing local MLX models over pulling new Ollama models; verify API keys are exported in the current shell, not just .env

## Working Contract

Jacob describes outcomes in plain language. You are the engineer: decode intent, protect him from hidden technical mistakes, and leave a trail he can follow. Be direct when an idea has a problem. Do not flatter bad plans into existence.

## Initiative

See `.claude/rules/initiative.md`. Persona and noticing rules live in `config/SOUL.md`.

## Non-Negotiables

1. Fail loud. No silent exception swallowing, fake defaults, or invented data.
2. Verify before claiming. "Done" means a command ran and the output was read — name the command or MCP server used (e.g. `pytest tests/ -q`, `codegraph_explore`, a `claude-in-chrome` screenshot). If a claim can't actually be checked, say so explicitly instead of implying it was.
3. Keep diffs small. Do not reformat or rewrite unrelated code.
4. Do not push, force-push, rewrite history, delete files, touch secrets/auth/env, or add heavy dependencies without explicit confirmation. **Carve-out (ADR 0018, 2026-07-21):** Builder campaign branches merge automatically under `initiative run`'s evidence gate (validation green + reviewer approve + scope clean, auto-revert on post-merge red) — this is Jacob's standing approval for that path only, not a general push/merge exemption.
5. New durable architecture decisions go in `docs/DECISIONS.md`; workflow lessons go in `docs/LEARNINGS.md`.

## Session State

Read `.claude/HANDOFF.md` and `.claude/STATE.md` at the start of every session. Update `.claude/STATE.md` before stopping; write `.claude/HANDOFF.md` at the end of any session that leaves unfinished work.

These are single shared files, not a session-scoped journal — more than one session or autonomous KittyBuilder campaign can be active in the same window (see `docs/LEARNINGS.md` L-CAND-16). Before writing either file: `git fetch` and read the live `origin/main` copy fresh, not a cached read from earlier in this conversation. If the current content is clearly a different active workstream's narrative (different mission, recent `updated_at`, unfamiliar branch/PR references), don't clobber it wholesale — either leave it alone and put your findings in chat or `docs/LEARNINGS.md`, or scope your addition narrowly. This convention is for Jacob's own interactive sessions; isolated KittyBuilder worker attempts must not touch `.claude/` at all (already enforced in their brief).

## Authority

`docs/AUTHORITY_MAP.md` is the only routing map for project truth. This file is
a bootloader and Claude-specific glossary, not a second status or architecture
authority.

## Runtime Shape

Kitty is a local-first single-user companion on Jacob's Mac:

- FastAPI gateway in `gateway/`
- Next.js UI in `gateway/kitty-chat/`
- LiteLLM proxy for model routing
- Runtime data under `data/`
- Logs under `logs/`

All storage reads for prompt/search context should go through `gateway/memory_graph.py`. Direct store imports are acceptable for write paths until Phase B introduces a write-side storage router.

## Commands

```bash
bash scripts/preflight.sh      # run at session start to catch auth/env blockers
./kitty up
./kitty status
./kitty doctor --json
python3.12 -m pytest tests/ -q --tb=short
make ui-test && make ui-build
make agent-wrap
```

If a command fails, report the failure exactly. Do not round up to passing.

## Voice Glossary

- "the gateway" → `gateway/`
- "the chat thing" / "the UI" → `gateway/kitty-chat/`
- "the agent" → `gateway/agent.py`
- "the storage thing" → `gateway/storage_router.py` + `gateway/memory_graph.py`
- "the routing thing" → `gateway/llm_client.py`
- "the journal thing" → `gateway/journal.py` + `gateway/journal_store.py`
- "phase B" → `docs/phases/PHASE_B_PLAN.md` (shipped)
- "phase C" → storage migrations (chats done, journal next)
- "free workers" / "the free train" → `docs/FREE_WORKERS.md` (zero-cost OpenCode execution of packets)
- "mission" → `docs/ACTIVE_MISSION.md` (approved intent and acceptance contract)
- "execution state" → Builder's durable store through supported Builder projections
- "Goose" → external chat tool, not part of kitty runtime
- "Honcho" → `gateway/honcho.py` — weekly pattern mirror, wired to kitty_tools route
