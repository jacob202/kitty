# MCP Agent Bundle Triage

Date: 2026-04-30
Status: reviewed, remains parked
Scope: governance review only (no MCP expansion)

## Summary

User approved reviewing the parked MCP lane. Review completed.

Disposition:

- Keep MCP bundle parked.
- Do not adopt into `main` runtime.
- Treat this as a future spec lane only.

## Evidence

### Main branch current state

- `src/agents/knowledge_getter.py`: not present
- `src/agents/librarian.py`: not present
- `src/agents/vision_guide.py`: not present
- `src/agents/code_reviewer.py`: not present
- `src/agents/overnighter.py`: not present

Only legacy files exist under `src/agents/`:

- `auto_fix_loop.py`
- `custom_agents.py`

### Parked branch state

Branch: `parked/mcp-agent-bundle-20260429`

Contains:

- `specs/knowledge-getter.spec.md`
- `specs/librarian.spec.md`
- `specs/vision-guide.spec.md`
- `specs/code-reviewer.spec.md`
- `specs/overnighter.spec.md`
- `src/agents/{knowledge_getter,librarian,vision_guide,code_reviewer,overnighter}.py`
- `src/agents/knowledge_getter_config.json`
- `src/tools/image_gen.py` change

### Dependency probe on current environment

- `chromadb`: available
- `sentence_transformers`: available
- `mcp`: missing
- `exa_py`: missing
- `firecrawl`: missing

## Risks

- Missing optional deps prevent straightforward import/runtime adoption.
- Bundle includes subprocess-capable surfaces (`code_reviewer`) and generated stores.
- `src/tools/image_gen.py` rides along with bundle and must be reviewed separately.

## Decision

Remain parked and out-of-phase.

No merge from `parked/mcp-agent-bundle-20260429` without a new approved spec that includes:

1. dependency policy and installation guardrails
2. security boundaries for subprocess/tools
3. storage/data governance
4. import-smoke + behavior tests
5. rollback plan
