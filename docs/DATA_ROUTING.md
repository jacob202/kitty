# Data routing (canonical)

**CRITICAL:** Wrong store for a data type is the #1 source of data-loss bugs. This file is the single source of truth for **where data lives**. For **how the gateway is laid out**, see **`docs/ARCHITECTURE.md`** and **`gateway/paths.py`**.

**Last updated:** 2026-05-13

---

## Doc index (memory / storage pointers)

| Topic | Canonical doc / code |
|-------|----------------------|
| Ports, Open WebUI, LiteLLM | `docs/ARCHITECTURE.md` |
| Append-only session narrative | `docs/SESSION_LOG.md` |
| Improvement backlog | `docs/IMPROVEMENT_AUDIT.md` |
| Deferred product ideas | `docs/PARKED_FEATURES.md` |
| Open questions | `docs/OPEN_LOOPS.md` |
| Runtime path helper | `gateway/paths.py` (`DATA_DIR`, `LOGS_DIR`, …) |

---

## Storage routing (do not cross the streams)

| Data type | Store | NEVER use for this |
|-----------|--------|---------------------|
| KB / knowledge ingestion | LightRAG | JournalDB |
| Journal entries | JournalDB (SQLite / journal pipeline) | LightRAG |
| Semantic search | ChromaDB (as configured) | ad-hoc duplicate stores |
| MCP entities / relations | `@modelcontextprotocol/server-memory` | random SQLite |
| Corrections, misc | Dedicated SQLite (e.g. `corrections.db`) | KB store |
| Raw chat logs | `data/sessions/` (or configured path) | — |

Same table is mirrored in **`AGENTS.md`** (“Storage Targets”) for agent rules.

---

## Implementation surface (gateway-era)

Legacy references to `src/memory/*` are obsolete in this checkout.

- **Knowledge / RAG / search:** Wire through **`gateway/knowledge.py`** and related gateway modules (see repo).
- **Journal:** **`gateway/journal.py`** (routes in **`gateway/app.py`**).
- **Cross-store context:** **`gateway/memory_graph.py`** (unified-ish fetch; evolving per `docs/UNIFIED_IMPLEMENTATION_PLAN.md` Phase 1).

When adding a **new** persistence type: update **this file**, **`AGENTS.md`**, and **`docs/DECISIONS.md`** if behaviour is contract-level.

---

## Related

- `docs/IMPROVEMENT_AUDIT.md` — scores and backlog  
- `docs/PROCESS_UPGRADES.md` — workflows and engineering loop  
- `config/README.md` — config touchpoints (when present)
