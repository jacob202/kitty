# Kitty Repo AGENTS

Purpose: keep Codex and delegated workers aligned with the active control system in this repository.

## First Read Order

1. `docs/LAYER0_CONTROL_PLANE.md`
2. `CURRENT_FOCUS.md`
3. `TASKS.md`
4. `docs/AGENT_COORDINATION.md` (active lanes, messages, handoffs — claim a lane before overlapping work)
5. `SESSION_SUMMARY.md`
6. `docs/DECISIONS.md`
7. `docs/FILE_GOVERNANCE.md`
8. `docs/PARKED_FEATURES.md`

If these conflict with older notes, these files win.

## Execution Contract

- Before creating new specs, docs, or modules, scan the **legacy checkout**
  `/Users/jacobbrizinski/Projects/kitty` for existing equivalents (canonical git,
  full tree). Prefer extending what exists; avoid duplicate control docs or
  parallel names that drift from migrated copies.
- Convert request -> one spec -> one build -> one validation -> one completion report.
- No raw idea goes directly to implementation.
- Dry-run defaults for intake/builder tools; require explicit write flags.
- Every meaningful change must include:
  - files changed
  - commands run
  - tests run
  - outcome and remaining risks

## Handoff Detail Rule

- Jacob's latest live instruction beats older handoff constraints, including "concise," "no narrative," "no new decisions," and "no clarifying questions."
- If Jacob asks for a detailed, full, complete, or best-possible handoff, preserve more detail than he asked for.
- Detailed handoffs must include chronology, decisions, rejected options, exact files, commit SHAs, commands, tests, current dirty state, open questions, risks, and next actions.
- Do not compress grilling sessions into only a decision list. Keep or reference the raw transcript/source context, then add a decision ledger.
- Concise transfer mode applies only when Jacob has not asked for detail and has not said prior context was missed.

## Scope Guards

- Respect `CURRENT_FOCUS.md` forbidden work list.
- Do not expand MCP, QLoRA, proactive nudging, or unrelated UI polish unless a new approved spec explicitly allows it.
- Do not delete raw chat logs.
- Do not delete or rename `/Users/jacobbrizinski/Projects/kitty`; it is the canonical runnable checkout.

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
