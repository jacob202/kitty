# Session handoff — Kitty

**Updated:** 2026-05-18  
**Branch:** `main` (uncommitted work in tree)  
**Tests last run:** 296 passed, 2 deselected (`pytest tests/ -q --tb=short`, 2026-05-18 cleanup pass).

**Cleanup (2026-05-18):** Calendar routes use `asyncio.to_thread`; `council_graph` uses `PROJECT_ROOT` for env path + logging; MCP council caches compiled graph; ruff F401 sweep on `gateway/` (kept `knowledge.py` test re-exports); `.gitignore` for `duplicate_analysis_report.txt` and `.superpowers/`. **Pass 2:** F841 fixes; `gateway/app.py` slimmed (~90 lines) with routes in `gateway/routes/`; scripts split into `scripts/curation/` and `scripts/ops/` with root shims for `spend_report` / `assign_kb_files`.

## What landed (Codex + Cursor follow-up)

- **`/brief` no longer blocks the UI:** RSS fetch uses short HTTP timeouts; in-memory cache; route uses `asyncio.wait_for` with fast fallback (`gateway/brief.py`, `gateway/app.py`).
- **Single public model route:** `kitty-default` only; removed tiered `kitty-smart` / `kitty-agent` routing; AgentRouter defaults separated from `KITTY_MODEL` (`gateway/llm_client.py`, `gateway/litellm_config.yaml`, tests).
- **Spend visibility:** `gateway/token_spend_report.py` + `scripts/spend_report.py` for estimated usage vs optional `--credits` balance hint (`data/kitty_token_log.jsonl`).
- **AgentRouter:** hosted `https://agentrouter.org/v1` with valid token + model IDs your account lists (e.g. `deepseek-v4-pro`); stale token showed `unauthorized_client` / `invalid token` until rotated.
- **OpenCode (machine):** `~/.config/opencode/opencode.json` — use `{env:NVIDIA_API_KEY}` for NIM, not a literal key; invalid top-level `hooks` breaks startup.
- **Skills:** `.agents/skills/image-gen/SKILL.md` has YAML frontmatter; `journal-entry` already has frontmatter. Repo + `~/.agents` / `~/.codex` / `~/.config/opencode/skills` carry `provider-credit-debugging` variants.

## Do not commit

- `.env` (secrets; gitignored).
- `.superpowers/brainstorm/` (local brainstorm artifact).

## Good next steps

1. Run full pytest, then commit the current gateway + frontend + tests + handoff.
2. Frontend: finish any remaining live brief/search wiring if UI still shows fallback.
3. Rotate any API keys that were pasted into chat logs elsewhere.

## Quick commands

```bash
cd /Users/jacobbrizinski/Projects/kitty
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
python3 scripts/spend_report.py --since 2026-05-18 --credits 150
```
