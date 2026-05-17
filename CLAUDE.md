# Kitty — Claude Code Rules

## Structure

- **Backend:** `gateway/` — FastAPI on `:5001`, uvicorn
- **Frontend:** `gateway/kitty-chat/` — Next.js
- **Tests:** `tests/` — pytest
- **Config:** `config/`, `.env` (never commit)

## Run tests

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
```

Last known passing: 335 passed, 2 skipped.

## Cost discipline

Cheap-first routing. In order: AgentRouter → LiteLLM → OpenRouter → Gemini → NVIDIA.

- Execution work → DeepSeek V4 Flash, Gemini 2.5 Flash
- Architecture/review → Claude Sonnet
- Never use Opus unless Jacob explicitly says so

## Security rules

- Secrets go in `.env` only, never in code
- `.env` is in `.gitignore` — do not commit it
- Auth middleware is in `gateway/auth.py` — don't bypass it

## Key files

| File | Purpose |
|---|---|
| `gateway/app.py` | FastAPI app, all routes |
| `gateway/llm_client.py` | LLM routing |
| `gateway/context_builder.py` | Context assembly |
| `gateway/paths.py` | Path/env constants |
| `.env.example` | What goes in `.env` |
| `docs/STANDUP.md` | Current state |
| `docs/ARCHITECTURE.md` | System overview |
