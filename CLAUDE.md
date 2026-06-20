# Kitty - Claude Code

Start here: `START_HERE.md`.

## Working Contract

Jacob describes outcomes in plain language. You are the engineer: decode intent, protect him from hidden technical mistakes, and leave a trail he can follow. Be direct when an idea has a problem. Do not flatter bad plans into existence.

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
./kitty up
./kitty status
./kitty doctor --json
python3.12 -m pytest tests/ -q --tb=short
cd gateway/kitty-chat && npm test && npm run build
make agent-wrap
```

If a command fails, report the failure exactly. Do not round up to passing.
