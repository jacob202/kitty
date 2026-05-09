# Data Routing

**CRITICAL**: This document maps data types to their storage backends. Incorrect routing is the #1 source of data-loss bugs.

## Storage Routing

| Data Type | Store | NEVER use |
|----------|-------|----------|
| KB / knowledge | LightRAG | JournalDB |
| Journal entries | JournalDB | LightRAG |
| Semantic search | ChromaDB | - |
| Corrections | SQLite (corrections.db) | - |
| Hardware BOM | SQLite (hardware_bom.db) | - |
| Eval artifacts | SQLite (kitty.db) | - |
| Chat logs | data/sessions/ | - |

## Store Details

### LightRAG (`src/memory/lightrag_store.py`)
- Used for: Knowledge base, embeddings, semantic search over documents
- Location: `data/chroma/`
- Use when: Building KB, RAG queries

### JournalDB (`src/memory/journal_db.py`)
- Used for: User journal entries, personal notes
- Location: `data/journal.db`
- Use when: Storing user reflections, daily logs

### ChromaDB (`src/memory/chroma_manager.py`)
- Used for: Legacy semantic search
- Location: `data/chroma/`
- Use when: Deprecated, prefer LightRAG

### SQLite (corrections.db)
- Used for: Correction memory, mistake tracking
- Location: `data/corrections.db`
- Use when: Tracking AI mistakes/corrections

## Code References

```python
#正确:
from src.memory.lightrag_store import LightRAGStore
kb = LightRAGStore()  # knowledge

from src.memory.journal_db import JournalDB
journal = JournalDB()  # personal entries

#错误 (will cause data loss):
journal = LightRAGStore()  # for personal entries
kb = JournalDB()  # for knowledge
```

---

## CLAUDE.md Reference

This routing is documented in CLAUDE.md under "Storage Targets". Check there first.

## Related Docs

- `config/README.md` - Config index
- `docs/IMPROVEMENT_AUDIT.md` - Full audit
- `docs/REFACTOR_PLAN.md` - Future improvements

**Last updated**: 2026-05-09