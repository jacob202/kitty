# Kitty — Agent Rules

Applies to all agents (Claude Code, Gemini, Codex, Goose, etc.).

## Structure

- Backend: `gateway/` (FastAPI + uvicorn, port 8000)
- Frontend: `gateway/kitty-chat/` (Next.js)
- Tests: `tests/`

## Orientation

1. Read `docs/STANDUP.md` — current state
2. Read `docs/ARCHITECTURE.md` — system overview
3. Read `CLAUDE.md` — Claude-specific rules

## Rules

1. **No secrets in code.** All keys go in `.env`. Use `os.environ.get(...)`.
2. **Run tests before claiming done.** `/opt/homebrew/bin/python3.12 -m pytest tests/ -q`
3. **Cheap models for execution.** Reserve Sonnet for review/synthesis.
4. **Don't delete without asking.** Moves are fine; destructive deletes need confirmation.
5. **One concern per commit.** Don't bundle unrelated changes.
6. **Don't touch `.env`.** Read `.env.example` instead.

## What's forbidden

- MCP expansion beyond current scope
- QLoRA / fine-tuning
- Removing raw chat logs
- Committing `.env` or any file with real API keys
