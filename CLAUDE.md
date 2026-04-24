# Kitty — Claude Code Rules

## Storage Targets (look this up before writing any data)
| Data | Store | NEVER use |
|------|-------|-----------|
| KB / knowledge ingestion | LightRAG | JournalDB |
| Journal entries | JournalDB | LightRAG |
| MCP entities/relations | @modelcontextprotocol/server-memory | — |

Violating this routing is the #1 source of data-loss bugs in this project.

## Before Touching Frontend
1. Search for the CSS class, DOM element ID, or JS function name before adding it
2. Previous agents left complete implementations — check first, always
3. Duplicate mic button CSS was introduced twice by not checking; don't do it again

## Model Routing
| Need | Model | Notes |
|------|-------|-------|
| Fast/free/local | MLX Qwen3.5-4B | `enable_thinking=True` for reasoning |
| Cheap remote | deepseek-chat | currently wired for both large + small slots |
| Heavy reasoning | deepseek-reasoner | paid — use sparingly |

Local models are free. Use them first.

## File Organization
- Source code → `src/`
- Tests → `tests/`
- Docs and plans → `docs/`
- Config → `config/`
- Scripts → `scripts/`
- **NEVER save to project root**

## Specialist Framework
- Base class: `src/core/specialist_framework.py`
- Configs: `config/specialists/*.md`
- Python: `src/core/specialists/*.py`
- Specialists are Python classes, not agents (unless explicitly wired as agents)

## Voice Pipeline
`Browser MediaRecorder → POST /api/transcribe → src/api/transcription_service.py → faster-whisper → text`

## Skills
- Consolidated (reasoning/execution/planning): `consolidated-skills/`
- Project-level: `src/tools/superpowers/skills/`

## Validation Loop (REQUIRED after every code change)

After writing or editing any code, run this loop before reporting done:

```
1. Run tests:   /opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
2. If failures: read the error, fix the root cause, go back to 1
3. If passing:  run the full test suite (same command) to check for regressions
4. For eval-gated changes: POST /api/eval/run -d '{"suite":"smoke"}' (expect 200, not 422)
5. Only mark done when: all tests pass + eval smoke returns 200 + no new failures vs baseline
```

Never skip this. The reasoning route bug and ChromaDB regression both slipped through
because code was marked done before the loop ran.

## After Structural Changes
Run evals before marking done. ChromaDB changes once silently dropped eval scores — always verify.

## Test Command
```bash
/opt/homebrew/bin/python3.12 -m pytest -q
```

## Commit Rules
- Never commit `.env`, secrets, or credentials
- Run tests before committing
- Staged files must be exactly what should be committed

## Security
- Validate user input at system boundaries
- Sanitize file paths from user input
- No API keys in source files — ever
