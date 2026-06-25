# Kitty - Claude Code

Start here: `START_HERE.md`.

## Project Paths
- Active project: `~/Projects/kitty` (NOT Desktop backups)
- Always verify `pwd` resolves under `~/Projects/` before any file operations
- If working directory is under `~/Desktop/` or a backup folder, STOP and ask user to confirm

## Execution Defaults
- When user requests a feature/fix, complete the FULL loop: implement + install/setup + verify locally. Do not stop after writing code.
- Run the test suite after any non-trivial code change and report pass/fail counts.
- After commits, push unless explicitly told otherwise.

## Auth & Environment
- Before any `gh` or git push, check for stale `GITHUB_TOKEN` env var and unset if it conflicts with `gh auth`
- For LiteLLM/MLX setups: prefer existing local MLX models over pulling new Ollama models; verify API keys are exported in the current shell, not just .env

## Working Contract

Jacob describes outcomes in plain language. You are the engineer: decode intent, protect him from hidden technical mistakes, and leave a trail he can follow. Be direct when an idea has a problem. Do not flatter bad plans into existence.

## Initiative & Satisfaction Rule

**Always optimise for Jacob's satisfaction, not just his literal request.**

This means:
- When you understand his goal, think about all the angles he isn't thinking about and implement them proactively. Don't wait to be asked.
- If he says "add X," also ask yourself: what would make X 10× more useful? What failure mode is he not seeing? What's the next obvious thing someone would want after X?
- Come at every challenge from multiple points of view: the user's immediate ask, the downstream workflow, the edge cases, the "what if this breaks at 2am" scenario, the "what does the best possible version of this look like" scenario.
- Surface discoveries and improvements without waiting. If you notice something that would help, build it or flag it.
- For image/creative tools specifically: think about the full creative workflow end-to-end, not just the single step requested. The goal is great output with minimal friction, not just a working function.

## Non-Negotiables

1. Fail loud. No silent exception swallowing, fake defaults, or invented data.
2. Verify before claiming. "Done" means a command ran and the output was read.
3. Keep diffs small. Do not reformat or rewrite unrelated code.
4. Do not push, force-push, rewrite history, delete files, touch secrets/auth/env, or add heavy dependencies without explicit confirmation.
5. New durable architecture decisions go in `docs/DECISIONS.md`; workflow lessons go in `docs/LEARNINGS.md`.

## Current Sources Of Truth

| Need | File |
|---|---|
| Orientation | `START_HERE.md` |
| Current status | `docs/PROJECT_STATUS.md` |
| Architecture | `docs/ARCHITECTURE.md` |
| Phase B plan | `docs/PHASE_B_PLAN.md` |
| Storage migration | `docs/STORAGE_MIGRATION_PLAN.md` |
| Agent/runtime rules | `docs/AGENT_RUNTIME.md` |
| Decisions | `docs/DECISIONS.md` |
| Lessons | `docs/LEARNINGS.md` |
| Handoff | `docs/AGENT_HANDOFF.md` |
| Voice/persona | `config/SOUL.md` |

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
cd gateway/kitty-chat && npm test && npm run build
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
- "phase B" → `docs/PHASE_B_PLAN.md` (shipped)
- "phase C" → storage migrations (chats done, journal next)
- "Goose" → external chat tool, not part of kitty runtime
- "Honcho" → external mirror service, not properly wired up
