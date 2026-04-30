# Kitty Repo AGENTS

Purpose: keep Codex and delegated workers aligned with the active control system in this repository.

## First Read Order

1. `CURRENT_FOCUS.md`
2. `TASKS.md`
3. `SESSION_SUMMARY.md`
4. `docs/DECISIONS.md`
5. `docs/FILE_GOVERNANCE.md`
6. `docs/PARKED_FEATURES.md`

If these conflict with older notes, these files win.

## Execution Contract

- Convert request -> one spec -> one build -> one validation -> one completion report.
- No raw idea goes directly to implementation.
- Dry-run defaults for intake/builder tools; require explicit write flags.
- Every meaningful change must include:
  - files changed
  - commands run
  - tests run
  - outcome and remaining risks

## Scope Guards

- Respect `CURRENT_FOCUS.md` forbidden work list.
- Do not expand MCP, QLoRA, proactive nudging, or unrelated UI polish unless a new approved spec explicitly allows it.
- Do not delete raw chat logs.
- Do not delete or rename `/Users/jacobbrizinski/Projects/kitty` while copy-first migration is active.

## Validation Minimum

For runtime/API work:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
./kitty status
curl -sS http://localhost:5001/api/brief
curl -sS -X POST http://localhost:5001/api/command -H "Content-Type: application/json" -d '{"command":"/stuck"}'
```

For control-layer/build-tooling work:

```bash
bash scripts/run_gates.sh
```

## OpenAI/Codex Docs Rule

When answering OpenAI API/Codex usage questions:

- Use official OpenAI developer documentation first.
- Prefer MCP docs server when available: `https://developers.openai.com/mcp`.
- If MCP is unavailable, fall back to official domains only:
  - `developers.openai.com`
  - `platform.openai.com`
  - `openai.com`
  - `help.openai.com`

## Delegation Rule

- Delegate only independent, bounded lanes.
- Each delegated lane must include exact ownership (files/modules), validation command, and completion report.
- Close idle agents after results are captured.

## Git Rule

- Never revert unrelated dirty changes.
- Never use destructive git commands unless explicitly requested.
- Checkpoint verified green states before starting the next risky feature.
