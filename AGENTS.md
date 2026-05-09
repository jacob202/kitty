# Kitty Repo AGENTS

Purpose: keep Codex and delegated workers aligned with the active control system in this repository.

## First Read Order (minimal)

1. `docs/LAYER0_CONTROL_PLANE.md`
2. `docs/README.md` (documentation index and stale-doc rule of thumb)
3. `CURRENT_FOCUS.md`
4. `TASKS.md`
5. `docs/IMPROVEMENT_AUDIT.md` (2026-05-09 - start here for new work)
6. `docs/PROCESS_UPGRADES.md` (quick reference for workflows)

## Read When Relevant

- `docs/AGENT_COORDINATION.md` — **only** when claiming a lane, posting board messages, or resolving overlap (large file; never paste the whole thing into prompts).
- `SESSION_SUMMARY.md` — long-session continuity.
- `docs/DECISIONS.md` — durable decisions touching your task.
- `docs/FILE_GOVERNANCE.md` — before moves, renames, or archival.
- `docs/PARKED_FEATURES.md` — scope checks against parked work.

If these conflict with older notes, these files win.

## Execution Contract

- Before creating new specs, docs, or modules, scan this **canonical checkout**
  `/Users/jacobbrizinski/Projects/kitty` for existing equivalents (git,
  full tree). Prefer extending what exists; avoid duplicate control docs or
  parallel names that drift from old copies.
- Convert request -> one spec -> one build -> one validation -> one completion report.
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

Default `pytest` skips browser + merge-gate tests (see `pytest.ini`). All tests: add `-m ""`.

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

## Token Optimization Practices

Applies to all agents: Claude, Gemini, opencode, Codex, Goose.

### Core Rules
1. **Token Efficiency First** — Every LLM call must justify its token cost
2. **Prevention Over Compression** — Filter context before it becomes a problem
3. **Deterministic > Probabilistic** — Use jq/awk/scripts for deterministic tasks
4. **Cache Everything Static** — System prompts, tool schemas, repeated queries use `src/core/prompt_cache.py`
5. **Just-In-Time Context** — Load only what's needed for the current task

### Mandatory
- **Log token usage** — All LLM calls log to `data/kitty_token_log.jsonl` (JSONL: `{"ts","date","provider","model","operation","usage","metadata"}`)
- **Semantic caching** — Check `SemanticCache` before making repeated queries
- **Truncation** — File reads limited to 2K lines / 50KB via `truncate_to_token_budget()`
- **Local routing** — Route simple queries to cheaper models (`--quick` mode)
- **No broad Firecrawl** — Max 1-2 queries per run, use `scrape()` not `crawl()` for single pages
- **Use research pipeline** — `src/tools/research_pipeline.py` for web research (map+batch_scrape, not deep crawl)

### Quick Reference
| Situation | Action |
|-----------|--------|
| Simple status check | Use `./kitty status` (deterministic) |
| Count lines in file | Use `wc -l file` not LLM |
| Parse JSON | Use `jq` not LLM |
| Repeated query | Check `SemanticCache` first |
| Long system prompt | Use `PromptCache.prepare_system_prompt()` |
| File > 50KB | Truncate with `truncate_to_token_budget()` |
| Web scrape (1 page) | Use `firecrawl scrape` not `crawl` |
| Session start | Use `./kitty quick` for deterministic commands |
| Quick status | `./kitty quick status` — server status |
| Quick test | `./kitty quick test` — run pytest |
| Quick health | `./kitty quick health` — API check |
| Quick tokens | `./kitty quick tokens` — recent token usage |
| Quick index | `./kitty quick index <pattern>` — search file index |
| Quick count | `./kitty quick count <path>` — count lines |
| Scaffold | `python scripts/scaffold.py <tool|route|test|module> <name>` |
| File index | `python scripts/build_file_index.py --search <pattern>` |
