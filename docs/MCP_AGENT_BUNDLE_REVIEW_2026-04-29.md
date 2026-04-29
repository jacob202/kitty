# MCP Agent Bundle Review

Date: 2026-04-29
Status: parked / unverified

## Summary

A dirty worker lane added a Phase 6+ MCP agent bundle while the active focus forbids MCP expansion. The bundle should not be accepted into canonical done state before a separate review spec.

## Source-Like Dirty Items

- `specs/knowledge-getter.spec.md`
- `specs/librarian.spec.md`
- `specs/vision-guide.spec.md`
- `specs/code-reviewer.spec.md`
- `specs/overnighter.spec.md`
- `src/agents/knowledge_getter.py`
- `src/agents/knowledge_getter_config.json`
- `src/agents/librarian.py`
- `src/agents/vision_guide.py`
- `src/agents/code_reviewer.py`
- `src/agents/overnighter.py`
- `requirements.txt`

## Generated / Tool-Local Items

- `knowledge_db/`
- `librarian_db/`
- `.agents/`
- `.claude/skills/`
- `skills/`
- `skills-lock.json`
- local tool folders such as `.goose/`, `.qwen/`, `.vibe/`, `.codebuddy/`, and similar

## Validation Run

Syntax compile:

```bash
/opt/homebrew/bin/python3.12 -m py_compile \
  src/agents/knowledge_getter.py \
  src/agents/librarian.py \
  src/agents/vision_guide.py \
  src/agents/code_reviewer.py \
  src/agents/overnighter.py
```

Result: passed.

Import smoke:

```bash
/opt/homebrew/bin/python3.12 -c "import src.agents.knowledge_getter"
/opt/homebrew/bin/python3.12 -c "import src.agents.librarian"
/opt/homebrew/bin/python3.12 -c "import src.agents.vision_guide"
/opt/homebrew/bin/python3.12 -c "import src.agents.code_reviewer"
/opt/homebrew/bin/python3.12 -c "import src.agents.overnighter"
```

Result: failed.

Observed failures:

- `src.agents.knowledge_getter`: `ModuleNotFoundError: No module named 'exa_py'`
- `src.agents.librarian`: `ModuleNotFoundError: No module named 'mcp'`
- `src.agents.vision_guide`: `ModuleNotFoundError: No module named 'mcp'`
- `src.agents.code_reviewer`: `ModuleNotFoundError: No module named 'mcp'`
- `src.agents.overnighter`: `ModuleNotFoundError: No module named 'mcp'`

Dependency probe:

- `chromadb`: available
- `sentence_transformers`: available
- `mcp`: missing
- `exa_py`: missing
- `firecrawl`: missing as imported by the dirty code

## Review Notes

- The specs only require import smoke, but the imports currently fail.
- `CodeReviewer` can launch `aider` and `goose` subprocesses from MCP tools and needs a safety gate before acceptance.
- `Librarian` creates persistent Chroma/SQLite stores under `librarian_db/`; that is generated data, not source.
- `Overnighter` writes `data/agent_logs` and `docs/morning_brief.md`; both need explicit storage and doc-governance rules.
- `KnowledgeGetter` adds external search/scraping dependencies and a new `knowledge_db/` store.
- `src/tools/image_gen.py` also has an unrelated tracked diff and needs a separate review.

## Disposition

Park the MCP bundle. Do not accept it as complete. Do not proceed with physical workspace separation until the dirty tree is clean or intentionally checkpointed without generated databases and tool-local installs.

## Next Safe Action

Create a future MCP review spec that decides whether to reject, salvage, or rewrite the bundle. Until then, keep MCP expansion in the blocked list.
