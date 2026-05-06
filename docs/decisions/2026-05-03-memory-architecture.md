# Memory Architecture Decision — 2026-05-03

## Decision

**Canonical store:** SQLite (`data/kitty.db`) with schema-versioned tables, source tagging, content hashing, and idempotent ingestion.

**Vector search:** `sqlite-vec` extension for embeddings, stored in virtual table `vec0`. Replace ChromaDB/LightRAG as the default retrieval engine for specialists.

**Optional layer:** LightRAG kept as an optional graph-RAG layer for specialists that need relationship traversal. Not the default. Not required for v1.

**Rejected options:**
- **Mem0:** Great for assistant memory, not document/book libraries. Adds Docker dependency. Overkill.
- **PostgreSQL/pgvector:** Strong, but heavier ops than SQLite for Jacob-only phase. Migration path preserved.
- **MongoDB:** Schema-less sounds nice but loses query power. Not local-first.
- **Zep/Graphiti:** Cloud-first now, deprecated OSS. Not suitable.

## Schema (Already Preserved)

Tables with `schema_version` and `source` fields:
- `tasks` — task tracker
- `journal` — journal entries with `content_hash`
- `vectors` — embeddings with `source`, `source_id`, `ingested_at`
- `corrections` — user corrections with tags/scope
- `circuits` — circuit breaker state
- `checkpoints` — session state
- `request_log` — budget tracking

## Ingestion Contract (The Real Fix)

The data was garbage because ingestion had no contract. New contract:

1. **Source registration:** Every ingestion records `source` (voice, journal, book_pdf, obsidian, web_scrape)
2. **Content hashing:** SHA-256 before insert. Duplicate = skip.
3. **Idempotency:** Same source + source_id + content_hash = one row, upsert not append
4. **Metadata minimum:** `source`, `source_id`, `ingested_at`, `content_hash`, `metadata_json`
5. **Evaluation gate:** After ingestion, run 3 known queries. If <2 correct, mark source as `untrusted`

## Migration Path

If SQLite + sqlite-vec hits limits (concurrent writes, graph scale):
1. Export raw sources (SELECT * FROM vectors WHERE source='...')
2. Spin up PostgreSQL + pgvector
3. Re-ingest from raw exports (content_hash preserves dedup)
4. Update StorageRouter

If LightRAG graph needed later:
1. Read trusted sources from SQLite
2. Pipe through LightRAG's `insert()` with proper entity extraction
3. Store graph in separate `lightrag.db`

## Specialist Access Pattern

Specialists query via `StorageRouter`:
```python
# Simple keyword + vector
results = router.search(query, k=5, sources=["book_pdf", "obsidian"])

# Graph traversal (optional, LightRAG)
if specialist.needs_graph:
    results = lightrag.query(query, mode="hybrid")
```

## Next Action

Write `docs/decisions/2026-05-03-memory-architecture.md` and commit. Then implement ingestion contract in `src/memory/ingest.py`.
