# Session handoff — compact-ready

_Use before **Compact chat** or any fresh thread: refresh this file, compact, then @ **`SESSION_HANDOFF.md`**. Ritual canon: **`docs/HANDOFF_AND_COMPACT.md`** · **`.cursor/rules/cursor-compact.mdc`** · **`AGENTS.md`**._

## Stack (truth)

- **Runnable:** `/Users/jacobbrizinski/Projects/kitty`
- **Code:** **`gateway/`** FastAPI (`docs/ARCHITECTURE.md`)
- **Roadmap:** **`docs/UNIFIED_IMPLEMENTATION_PLAN.md`** + **`TASKS.md`** · orientation **`docs/STANDUP.md`** · **`docs/README.md`** (canonical map)

## Recent shipped (git)

- Retired stale root indexes + **`docs/HANDOFF_AND_COMPACT`** consolidation + **`PROCESS_UPGRADES`** folding engineering loop · duplicate **`docs/handoffs/*`** trimmed (copies kept under **`docs/archive/handoffs/`**).
- **`branch: claude/fix-oauth-terminal-S0GUx`** — three tool-config fixes:
  - **`.envrc`**: added `dotenv_if_exists .env` so direnv exports `ANTHROPIC_API_KEY` (and other secrets) before `claude` starts → OAuth flow no longer triggered in Terminus.
  - **`.claude/settings.json`**: added `"env": {"BROWSER": "open"}` for correct macOS browser launch; sessionStart now falls back to `docs/STANDUP.md` hook block if `scripts/agent-context-brief.py` is missing.
  - **`opencode.json`**: created with `anthropic/claude-sonnet-4-6` as primary model, `AGENTS.md` as instructions, LiteLLM proxy wired as `openai` provider for local fallback.

## Tests

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
```
Last gate: **244 passed** (pre-tool-config commit).

## LLM fallback order

LiteLLM → AgentRouter → OpenRouter → Gemini → NVIDIA — details **`.env.example`** tier table (see `gateway/llm_client.py`).

## Blocked / pending

- **KB rebuild**: `make rebuild-index` / `python scripts/ingest.py data/knowledge` — run locally after activating venv. Remote cloud env missing deps (`pydantic` etc.). KB source at `data/knowledge/`.
- **voice_gate**: `gateway/voice_gate.py` + `/ask` wiring still local-only; not yet committed.

## Next actions

1. **`git push`** (branch `claude/fix-oauth-terminal-S0GUx`) then merge/PR if clean.
2. Restart Terminus shell (re-triggers direnv) and confirm `echo $ANTHROPIC_API_KEY` is non-empty.
3. Run `claude` in Terminus — should skip OAuth if key is loaded.
4. **KB rebuild**: `cd /Users/jacobbrizinski/Projects/kitty && make rebuild-index` locally.
5. Land **`gateway/voice_gate.py`** + `/ask` wiring in a follow-on commit.
