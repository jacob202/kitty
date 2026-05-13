# Session handoff — compact-ready

_Use before **Compact chat** or any fresh thread: refresh this file, compact, then @ **`SESSION_HANDOFF.md`**. Ritual canon: **`docs/HANDOFF_AND_COMPACT.md`** · **`.cursor/rules/cursor-compact.mdc`** · **`AGENTS.md`**._

## Stack (truth)

- **Runnable:** `/Users/jacobbrizinski/Projects/kitty`
- **Code:** **`gateway/`** FastAPI (`docs/ARCHITECTURE.md`)
- **Roadmap:** **`docs/UNIFIED_IMPLEMENTATION_PLAN.md`** + **`TASKS.md`** · orientation **`docs/STANDUP.md`** · **`docs/README.md`** (canonical map)

## Recent shipped (git)

- Retired stale root indexes + **`docs/HANDOFF_AND_COMPACT`** consolidation + **`PROCESS_UPGRADES`** folding engineering loop · duplicate **`docs/handoffs/*`** trimmed (copies kept under **`docs/archive/handoffs/`**).

## Tests

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
```
Last gate: **244 passed** before doc-consolidation commit pending.

## LLM fallback order

LiteLLM → AgentRouter → OpenRouter → Gemini → NVIDIA — details **`SESSION_HANDOFF`/`.env.example`** tier table (AgentRouter slug/env section kept in prior version of this file if needed — see **`gateway/llm_client.py`**).

## Next actions

1. **`git push`** locally if commits not on GitHub yet.  
2. Land **`gateway/app.py`** **voice_gate** `/ask` wiring (+ **`gateway/voice_gate.py`**) in a tiny feature commit when ready — currently **local only**.  
3. Sweep **`docs/`** stray references to deleted manifests on demand (specs/history files still mention retired paths).
