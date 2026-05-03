# Kitty — Full Project Audit (Verified)

**Date:** 2026-05-02  
**Canonical tree:** `/Users/jacobbrizinski/Projects/kitty`  
**Scope:** Entire canonical repo + all Kitty-related paths under `/Users/jacobbrizinski/Projects/`  
**Method:** Directory inventory, ripgrep, file reads, full `pytest tests/`, diff vs sibling workbench, doc cross-check.

---

## Executive summary

Kitty is a **local-first Flask + Socket.IO backend** with a **Next.js (`garage-ui`)** companion UI, **MLX/local + cloud LLM** routing, and **multiple persistence layers** (LightRAG, ChromaDB, SQLite/journal, MemoryWeave, etc.). The **test suite is green** (**399 passed** on 2026-05-02). **Layer 0** work (single source of truth for agents, config convergence, Dorothy bridge) is **partially documented** but **not fully implemented** — notably **`scripts/dorothy_bridge.py` is absent** and **`StorageRouter` is referenced in `docs/STANDUP.md` but does not exist in Python source** (verified by repo-wide search). A **sibling workbench** at `~/Projects/kitty-system/kitty-workbench` **diverges** from canonical `scripts/kitty_builder.py`, creating **fork risk**.

**Top risks:** (1) storage routing is **conventional**, not **centrally enforced**; (2) **instruction drift** between STANDUP, LAYER0, CURRENT_FOCUS, and TASKS; (3) **parallel trees** (`kitty-system`) and a **446MB tarball** duplicate migration surface; (4) **8GB RAM** reality vs local-model docs.

---

## 1. Audit scope and evidence

| Area | What was checked | Evidence |
|------|------------------|----------|
| Canonical repo | `git log`, structure, tracked files | HEAD `38ec1c8`; `git ls-files '*.py'` → **318** tracked Python files; **~63.5k** lines across tracked `*.py` (wc) |
| Tests | Full suite | `venv/bin/python -m pytest tests/ -q --tb=no` → **399 passed**, 2 DeprecationWarnings (SWIG) |
| “Kitty” under Projects | Glob `**/*kitty*` | Matches under `kitty/`, `kitty-system/kitty-workbench`, `kitty-system/kitty-archives`; **no** `kitty` string hits in `imagegen/` or `mcp-drawthings/` (name-only scan) |
| Secrets | Pattern scan in tracked text | No literal `sk-` keys in sample; env var **names** appear in scripts/docs (expected) |
| Workbench parity | `diff` | `kitty_builder.py`: **canonical vs workbench differ** |
| Eval smoke artifact | JSON | `evals/artifacts/8b94ebff_smoke.json` → smoke **5/5** checks passed |

---

## 2. Inventory: `/Users/jacobbrizinski/Projects/`

| Path | Role | Kitty relation | Notes |
|------|------|------------------|-------|
| **`kitty/`** | **Canonical runnable repo** | Primary product | Single git root; pre-commit + 399 tests |
| **`kitty-system/`** | Legacy / PM / archive bundle | **High** — duplicate scripts, context, benchmarks | Contains **`kitty-workbench`** (builder, intake, specs) and **`kitty-archives`** (benchmarks, chat exports, docs snapshots, backups). **Not** the active runtime per `docs/LAYER0_CONTROL_PLANE.md` |
| **`kitty-system-backup-20260501-125238.tar.gz`** | Full tarball | Archive of `kitty-system`-era material | **~468MB** — recovery asset; do not treat as live |
| **`mcp-drawthings/`** | Separate MCP project | **Low** (no “kitty” grep hits) | Adjacent infra; not merged into Kitty tree |
| **`imagegen/`** | Separate project | **None** in quick grep | Unrelated by name/content scan |
| **`nanoGPT`, `OpenViking-main`, etc.** | Other repos | None | Listed in `ls ~/Projects` only for boundary clarity |

**Kitty-named files elsewhere (glob sample):** e.g. `kitty-system/kitty-workbench/kittybuilder`, `KITTY_CONTEXT.md`, mirrored `scripts/kitty_builder.py`, archived copies under `kitty-archives/docs/archive/...`. Treat as **reference or rollback**, not edit targets.

---

## 3. Canonical repository — structure

**Major top-level buckets (depth ≤3):**

- **`src/`** — Flask API blueprints, core (specialists, domain router, morning brief), memory (LightRAG store, journal DB, MemoryWeave, vector), voice, tools, agents, observability.
- **`tests/`** — **51** tracked test modules (count via `git ls-files`).
- **`garage-ui/`** — Next **16.x**, React 18, Socket.IO client, Vitest; **26** tracked TS/TSX/JS files under `garage-ui` (git count).
- **`config/`** — including `config/specialists/*.md` and `config/kitty_settings.json`.
- **`scripts/`** — standup, builder, gates, voice corpus, intake, merge gates, etc.
- **`docs/`** — control plane, audits, plans, archives, superpowers specs.
- **`data/`** — chroma, lightrag domains, journal, voice corpus, sessions (gitignored subsets per policy).
- **`evals/`**, **`benchmarks/`**, **`specs/`**, **`intake/`**, **`consolidated-skills/`**, **`skills/`**.

**Entry / CLI:** `./kitty`, `kittybuilder`, `kittyintake`, `kitty_v2.py` at repo root (launcher ergonomics).

---

## 4. Runtime architecture (code-verified)

### 4.1 Backend surface

Blueprints span (non-exhaustive): **`core_routes`** (`/api/chat`, `/api/route`, chatbox), **`brief`**, **`commands`**, **`streaming_routes`** (domains, journal GET variant, search, transcribe-legacy, feedback, RLHF hooks, schematic), **`voice_routes`** (`/api/transcribe`), **`memory_routes`** and **`memory_product_routes`**, **`eval_routes`**, **`reasoning_routes`**, **`system_routes`**, **`swarm_routes`**, **`news_routes`**, **`bom_routes`**, **`ai_dev_routes`**, etc. This is a **broad** API — many routes are **feature flags / labs** adjacent to the “companion core.”

### 4.2 Memory and knowledge

| Component | Location | Role |
|-----------|----------|------|
| **LightRAG** | `src/memory/lightrag_store.py`, `data/lightrag/<domain>/` | Per-domain RAG + graph; OpenRouter integration, rate-limit handling |
| **Chroma** | `data/chroma`, `data/vector_store` | Vector retrieval; used in fallback paths via `context_service` |
| **Journal** | `src/memory/journal_db.py`, routes under `memory_routes` / streaming | Personal journal entries (**must not** be mistaken for KB) |
| **MemoryWeave** | `src/memory/memory_weave.py` | Temporal / entity-style memory; used from specialists and API |
| **SQLite paths** | `src/core/db_config.py` | Named DB files under `data/` |

**`query_knowledge_base`** in `src/services/context_service.py` orchestrates LightRAG vs Chroma — **good**, but this is **not** a global “StorageRouter” class; **direct imports** of stores still exist across the tree.

### 4.3 Specialists

**12** `BaseSpecialist` subclasses under `src/core/specialists/`: automotive, code, news, knowledge_acquisition, soul, audio, research, infrastructure, growth, fitness, design, creative. Framework: `src/core/specialist_framework.py` (LightRAG + MemoryWeave hooks).

### 4.4 Frontend

`garage-ui`: Next 16, Tailwind, Socket.IO client, Vitest + Testing Library. Product direction (per control docs): move from “dev console” to **warm companion** UX — **ongoing** design debt, not a absence of code.

### 4.5 Voice

Pipeline per project rules: **Browser → POST `/api/transcribe` → `transcription_service` → faster-whisper**. Dependencies list `faster-whisper>=1.0`.

### 4.6 Dependencies (`requirements.txt` excerpt)

Core: **Flask**, **Flask-SocketIO**, **MLX**, **openai**, **anthropic**, **google-genai**, **chromadb**, **lightrag-hku**, **firecrawl-py**, **duckduckgo_search**, **tavily-python**, **pytest**, etc. **Heavy stack** for an 8GB machine — aligns with documented need for **cheap cloud defaults** + **small local** models.

---

## 5. Documentation and authority — drift matrix

| Document | Claims / role | Conflict or gap |
|----------|---------------|-----------------|
| **`docs/STANDUP.md`** | Jacob-Only Build; **StorageRouter** “exists”; inviolable “route through StorageRouter” | **`StorageRouter` not in codebase** — STANDUP is **ahead of implementation** or stale |
| **`docs/LAYER0_CONTROL_PLANE.md`** | Canonical path; **B launch** framing; Dorothy bridge **after** builder verification | **Product framing** differs from STANDUP’s **Jacob-Only** emphasis — reconcile in one authority pass |
| **`CURRENT_FOCUS.md`** | Phase C — Hardening & Coverage; slash commands, tests, SQLiteVec | Aligns with engineering focus; **does not** mention Jacob-Only four-pack explicitly |
| **`TASKS.md`** | Rich history; mentions deleted **`kitty-system/kitty-app`** migration | Historical narrative **useful** but can confuse if read as “current path” |
| **`docs/PROJECT_AUDIT_2026-05-02.md` (prior)** | Attributed to “Gemini”; some narrative | **Replaced** by this verified audit |

**Recommendation:** One **short “authority delta”** commit: either **implement** `StorageRouter` stub + imports, or **edit STANDUP** to say “planned / not yet enforced in code.”

---

## 6. Security and configuration

- **No committed `sk-*` literals** found in quick secret-pattern grep; **`.aider.conf.yml`** references **OpenRouter model IDs** (not keys).
- **`scripts/kitty_builder.py`** reads **`OPENROUTER_API_KEY`**, **`TAVILY_API_KEY`** from **environment** — correct pattern.
- **Risk:** duplicate **`KITTY_CONTEXT.md`** / **`kitty_builder.py`** in **workbench** may carry **old secrets** if someone copies env into files — **policy:** env only, rotate if ever pasted.

---

## 7. Automation, gates, and missing pieces

| Item | Status |
|------|--------|
| **`scripts/run_gates.sh`** | Exists — bash syntax, `py_compile` on selected scripts, governance + coordination checks, focused pytest subset |
| **Full `pytest tests/`** | **399 passed** |
| **`scripts/dorothy_bridge.py`** | **Not present** in canonical tree (glob 0) — STANDUP / LAYER0 **future work** |
| **Eval smoke JSON** | Example artifact **100%** smoke checks passed (historical run file) |

---

## 8. Sibling workbench diff (fork risk)

```text
diff -q ~/Projects/kitty/scripts/kitty_builder.py \
       ~/Projects/kitty-system/kitty-workbench/scripts/kitty_builder.py
→ Files differ
```

**Implication:** PM-layer improvements on one side may **not** land on the canonical server path. **Mitigation:** designate **only** `~/Projects/kitty/scripts/kitty_builder.py` as write target; periodically **diff** or delete workbench copy after merge.

---

## 9. Roadmap alignment (Jacob-Only / Layer 0)

From **`docs/STANDUP.md`** and **`docs/LAYER0_CONTROL_PLANE.md`**, expected Layer 0 outcomes vs **this audit**:

| Layer 0 expectation | Verified state |
|-------------------|----------------|
| Single canonical checkout | **Yes** — `~/Projects/kitty` |
| Config convergence across CLIs | **Partial** — multiple config roots (`.aider*`, `.claude`, Cursor, etc.); needs systematic inventory per LAYER0 doc |
| Dorothy bridge | **Missing file** |
| No literal secrets in committed configs | **Sample clean**; ongoing discipline required |
| Storage routing enforced | **Not enforced in code**; STANDUP **overstates** |
| Skills reconciled | **~10** top-level skills under `.claude/skills/`; **~12** dirs under `.agents/skills/` — full inventory not repeated here |

**Jacob-Only four themes** (onboarding, memory/continuity, companion UX, data safety): **product** tracks exist in plans/docs; **implementation** is **incremental** across API + UI + scripts — no single “Jacob-Only” flag in code.

---

## 10. Prioritized recommendations

1. **Fix STANDUP vs code on StorageRouter** — either implement a thin router façade used by new code paths, or reword STANDUP/LAYER0 to “target architecture.”
2. **Add `dorothy_bridge.py` or remove from gates** until spec’d — avoids false expectation.
3. **Workbench sync policy** — automated check or doc: “if `kitty-system/kitty-workbench` differs, it is **stale** unless tagged.”
4. **Authority doc pass** — one table: B-launch vs Jacob-Only vs Phase C (single sentence each + which doc wins).
5. **Keep running full pytest** after every change (already project rule); extend with **`scripts/run_gates.sh`** when touching scripts listed there.

---

## 11. Appendix — commands run (2026-05-02)

```bash
pwd   # /Users/jacobbrizinski/Projects/kitty
venv/bin/python -m pytest tests/ -q --tb=no   # 399 passed
rg -i 'StorageRouter|storage_router' --glob '*.py'   # no matches
find . -maxdepth 3 -type d  # structure sample
diff -q .../kitty/scripts/kitty_builder.py .../kitty-workbench/scripts/kitty_builder.py  # differ
ls /Users/jacobbrizinski/Projects
```

---

*End of audit. For day-to-day execution order, continue to follow **`AGENTS.md`** first-read list after any doc updates.*
