# PROCESS_UPGRADES.md

Last updated: **2026-05-13**  
Purpose: **Canonical** workflows for humans + AI agents — paired with **`docs/STANDUP.md`** (narrative, hooks, morale).

Former root **`ENGINEERING_LOOP.md`** is folded into § *Engineering loop* below.

---

## Developer workflow

### Quick commands (current tree)

| Task | Command |
|------|--------|
| Start gateway | `./kitty` |
| Full tests | `/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short` or `venv/bin/python -m pytest tests/ -q --tb=short` |
| Quick status / test / health | `./kitty quick status`, `./kitty quick test`, `./kitty quick health` |
| Phased roadmap excerpt | `./kitty quick spec` → `docs/UNIFIED_IMPLEMENTATION_PLAN.md` |
| Improvement audit | `./kitty quick audit` → `docs/IMPROVEMENT_AUDIT.md` |
| Workflow + this file | `./kitty quick plan` → `TASKS.md` |

**Legacy** helpers (`build_file_index.py`, `scaffold.py`, `warm_cache.py`, `start-session.sh`, `run_gates.sh`) lived in scripts that were **pruned**. If you need one, check **`scripts/archive/`** before reinventing.

### Entry points (today)

1. **`./kitty`** — launcher CLI  
2. **Gateway** — `gateway/app.py` (FastAPI); run via `./kitty` / project conventions in **`docs/ARCHITECTURE.md`**  
3. **Books / ingest** — **`scripts/ingest.py`**, **`scripts/enqueue_books.py`**, etc. (`ls scripts/*.py`)

---

## AI agent workflow

### First read order

1. `docs/STANDUP.md` — operating reality & hook summary  
2. `docs/ARCHITECTURE.md` — stack / ports  
3. `docs/LAYER0_CONTROL_PLANE.md` — control-plane authority  
4. `docs/README.md` — documentation index  
5. `CURRENT_FOCUS.md` · `TASKS.md` · `docs/UNIFIED_IMPLEMENTATION_PLAN.md` · `docs/DATA_ROUTING.md`  
6. `AGENTS.md` — mandatory rules  

### Prompt templates

**Debug**
```
inspect: <paths>
pytest: python3.12 -m pytest tests/ -q --tb=short
logs: tail -40 .kitty.log
```

**Add feature**
```
1. Grep/search for existing code
2. Spec under specs/ OR note in TASKS referencing UNIFIED plan section
3. Implement in gateway/ (no new stray roots)
4. pytest until green
```

---

## Session management

Before **compact** or context drop: **`SESSION_HANDOFF.md`** — pattern in **`docs/HANDOFF_AND_COMPACT.md`**.

Validation after substantive Python/config changes:
```bash
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
./kitty quick health
```

---

## Engineering loop (diagnose → audit → improve → ship)

1. **Diagnose:** reproduce → minimize → hypothesis → instrument → fix → regression test  
2. **Audit:** inspect → architecture pass → **`docs/IMPROVEMENT_AUDIT.md`** for scored backlog  
3. **Improve:** implement against **`TASKS.md`** / **`docs/UNIFIED_IMPLEMENTATION_PLAN.md`**  
4. **Ship:** pytest green → small commit → refresh **`SESSION_HANDOFF.md`**

---

## Repo hygiene quick wins

- Delete **`.DS_Store`** / **`Icon`** + carriage-return junk folders if they appear under **`.git/`**, **`venv/`**, or `site-packages/` (they break tools and git refs).  
- Never hardcode `~/Projects/...` paths in Python — use **`gateway/paths.py`**.

---

## Token optimization (reminders)

- Prefer **`./kitty quick *`** over LLM for status / counts  
- Repeated identical completions → dedupe when a cache exists  
- Don’t broaden Firecrawl / crawlers without a scoped spec  

See **`AGENTS.md`** “Token Optimization” for full discipline.

---

## What NOT to do

- ❌ Trust docs that cite removed **`src/`** layouts as active code paths  
- ❌ Add deps without pinning / requirements update  
- ❌ Ignore red **`pytest`** before claiming done  

---

## See also

- `docs/DECISIONS.md` · `docs/OPEN_LOOPS.md`  
