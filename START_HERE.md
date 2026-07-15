# Kitty — Start Here

This is the front door for agents and future Jacob.

## What Kitty Is

Kitty is Jacob's local-first AI companion. It runs on his Mac for one user. The gateway is the product — all clients stay thin. Near-term goal: daily-use reliability. Kitty starts cleanly, captures thoughts quickly, resurfaces them, and keeps Jacob's data local.

## The Rules

Every enduring idea has exactly one canonical home. Every other document references it. None duplicate it. Do not explain architecture here — point to it.

## Documentation Entry Points

| For | Read |
|---|---|
| The full map | [`docs/INDEX.md`](docs/INDEX.md) |
| Agent instructions | [`AGENTS.md`](AGENTS.md) |
| Current status | [`docs/operations/PROJECT_STATUS.md`](docs/operations/PROJECT_STATUS.md) |
| Architecture | [`docs/architecture/REFERENCE_ARCHITECTURE.md`](docs/architecture/REFERENCE_ARCHITECTURE.md) |
| Runtime | [`docs/engineering/ARCHITECTURE.md`](docs/engineering/ARCHITECTURE.md) |
| Decisions | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| Lessons | [`docs/operations/LEARNINGS.md`](docs/operations/LEARNINGS.md) |
| Handoff | [`.claude/HANDOFF.md`](.claude/HANDOFF.md) |
| Session state | [`.claude/STATE.md`](.claude/STATE.md) |

## Default Commands

```bash
./kitty up
./kitty status
./kitty doctor --json
python3.12 -m pytest tests/ -q --tb=short
cd gateway/kitty-chat && npm test && npm run build
python3 scripts/docs_lint.py
```

## Current Rules

- All context reads go through `gateway/memory_graph.py` — do not bypass.
- Do not push, force-push, rewrite history, delete files, or touch `.env` without explicit confirmation from Jacob.
- Voice/persona lives in `config/SOUL.md`. Do not modify it without Jacob.
