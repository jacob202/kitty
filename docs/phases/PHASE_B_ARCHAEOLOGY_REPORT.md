# Phase B Archaeology Report

**Date:** 2026-06-20
**Branch inspected:** `codex/raycast-quick-capture`, then clean `codex/phase-b-prep` from `origin/main`
**Current base:** `c6accd0 fix: repair broken-merge state on main (scrambled doctor.py + duplicated port) (#25)`

## Summary

Kitty is directionally right but has continuity debt: stale handoffs, duplicated architecture docs, runtime state sprawl, and multiple agent systems leaving traces. The next best move is not feature expansion. It is canonical docs, storage consolidation planning, and a repeatable agent wrap-up loop.

## Git And Dirty Work

- `origin/main` is now at `c6accd0`.
- A separate Raycast branch exists: `codex/raycast-quick-capture` at `5a07744 feat(desktop): add Raycast quick capture wrapper`.
- That branch's focused tests passed: `5 passed in 0.16s`.
- One unrelated roadmap hunk was preserved in stash: `phase-b-prep preserve roadmap deepening drift`.
- Older stashes remain and should not be dropped until reviewed.

## Codebase Recon

- Repo age: 2026-04-23 to 2026-06-18.
- Commits inspected: 450.
- Branches: 40.
- Hotspots: `gateway/app.py`, `TASKS.md`, `gateway/kitty-chat/src/app/page.tsx`, `gateway/llm_client.py`, `gateway/kitty-chat/src/lib/gateway.ts`.
- Bug magnets overlap hotspots: `gateway/app.py`, `gateway/llm_client.py`, `gateway/brief.py`, `gateway/knowledge.py`, `kitty`.
- Momentum is intense and branchy, which explains doc drift and stale local work.

## Architecture Findings

- Current product shape is FastAPI gateway + LiteLLM + Next.js `kitty-chat`.
- `gateway/routes/register.py` registers route modules; docs claiming all routes live in `app.py` are stale.
- `gateway/memory_graph.py` already includes Inbox as a read surface on latest main.
- `gateway/context_enrichment.py` still enriches todos separately, so Phase B should check for duplicate todo context before storage work.
- `gateway/llm_client.py` remains a large fallback-chain module and is a later refactor candidate, not a Phase B blocker.

## Storage Findings

Runtime state spans JSON, JSONL, SQLite, ChromaDB, mem0, and scattered caches under `data/`. Important stores include:

- `data/inbox.jsonl` via `gateway/desktop_store.py`
- journal JSONL via `gateway/journal.py`
- todos SQLite via `gateway/todo_store.py`
- cron SQLite via `gateway/cron.py`
- model digest SQLite via `gateway/model_digest.py`
- plugin settings JSON via `gateway/plugin_registry.py`
- semantic memory via mem0 and ChromaDB

Phase B should migrate app-owned episodic state first. Do not move ChromaDB, mem0, imported knowledge, logs, or backups in the first migration.

## Docs And Agent Drift

- `HANDOFF.md` is stale and still describes OpenWebUI.
- `SESSION_HANDOFF.md` is newer but mixes multiple sessions and no longer functions as one clean source.
- `docs/ARCHITECTURE.md` had duplicated sections and contradictory baselines.
- `docs/ARCHITECTURE_COMPLETE.md`, desktop hard-critic docs, and future vision docs are useful history, not current entrypoints.
- `.mcp.json` is local and ignored, but contains absolute paths to this checkout.
- The pre-commit hook runs pytest, then exits before the code-review-graph block, making that block unreachable.

## Local Hygiene

- No Finder metadata files are tracked.
- Many ignored `.DS_Store` and `Icon\r` files exist locally. Leave them untracked; the hook prevents staging.
- Ignored runtime directories include `$HOME/`, `data/`, `logs/`, `.worktrees/`, `.aura/`, `.cursor/`, `.mcp.json`, and stale UI paths.

## Verification Notes

- Focused quick capture tests passed on the Raycast branch.
- A prior full test run hit a pre-existing `gateway.web_tracker` eager model-load failure in `tests/test_antigravity_tools.py`.
- Latest main changed `gateway/doctor.py` and launcher config after that run, so a fresh full baseline is required after docs settle.

## Recommendation

Proceed with Phase B as a preparation and consolidation branch:

1. Establish canonical docs.
2. Add a session wrap-up command.
3. Write a storage migration plan before moving data.
4. Defer Raycast merge and app-code refactors to separate branches.
