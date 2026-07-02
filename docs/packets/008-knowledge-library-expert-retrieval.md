# Packet 008 — Knowledge library + expert retrieval

- **Status:** blocked until after packets 002–004 unless Jacob explicitly reprioritizes it
- **Best executor:** Claude Code or Codex
- **Purpose:** Turn Kitty's existing knowledge pipeline into a real user-facing feature: Jacob can upload or locally import documents, books, PDFs, manuals, notes, and reference files; Kitty indexes them; expert modes can answer using those sources with visible citations.

## Existing seams to productize

Do not rebuild the knowledge stack from scratch. This packet exists because the repo already has useful pieces that need a product surface and stricter contracts:

- `gateway/knowledge.py` — ingestion, chunking, vector search, source inventory.
- `gateway/pdf_pipeline.py` — PDF extraction/parsing support.
- `gateway/memory_graph.py` — `KnowledgeAdapter` as part of the unified context path.
- `soul/specialists/researcher.md` — researcher specialist prompt that already names document retrieval from the user's knowledge base.

## Exact scope

1. Document import surface:
   - Add an upload route or local-import route for PDFs, books, manuals, notes, and reference files.
   - The route must return an explicit ingest status: success, skipped, failed, or pending if async.
   - Failures must include a useful reason; no silent success.
2. Knowledge inventory:
   - Add a route that lists ingested sources and chunk counts.
   - Include source metadata where available: title/source, `doc_type`, sensitivity, authority, created/modified time, ingested time, and page/chunk references.
3. Search surface:
   - Add a route for searching uploaded knowledge.
   - Results must include source references and page/chunk references where available.
   - If the search returns nothing useful, say so explicitly.
4. Collections/tags:
   - Add a minimal source grouping mechanism so expert modes can prefer specific source collections.
   - Examples: `recovery`, `audio_repair`, `benefits_admin`, `coding_repo`, `creative`.
5. Expert retrieval mode:
   - Experts are task modes, not separate autonomous agents.
   - Each expert has a specialist prompt, allowed source collections, retrieval rules, citation requirements, and privacy/cloud boundary.
   - Expert answers must cite retrieved sources or state that the uploaded sources do not support the answer.
6. Privacy boundary:
   - Local-first by default.
   - Do not send document contents to cloud models unless Jacob explicitly approves that use.
   - Make cloud use visible in the code path and docs.

## Example experts

- **Recovery expert** — recovery books, Dharma/12-step docs, relapse-prevention notes.
- **Audio repair expert** — service manuals, schematics, forum notes, electronics references.
- **Benefits/admin expert** — SAID/CDB/DTC docs, letters, government PDFs, forms.
- **Coding/repo expert** — repo docs, architecture docs, implementation packets, PR notes.
- **Creative coach** — poems, painting notes, artist references, project notes.

## Files likely touched

- `gateway/knowledge.py`
- `gateway/pdf_pipeline.py`
- `gateway/routes/knowledge.py` or equivalent new route module
- `gateway/routes/register.py`
- `gateway/memory_graph.py` only if a small adapter contract change is necessary
- `contracts/` for route/request/response schemas if needed
- `tests/test_knowledge*.py` and route tests
- `soul/specialists/` only if expert prompts need lightweight metadata

## Files not to touch

- `gateway/action_queue.py` and action routes — this packet is not about actions.
- `gateway/triage.py` — inbox triage is separate.
- `llm_client.py` except for a tiny call-site seam if absolutely necessary.
- Existing migrations unless the packet introduces a narrowly scoped metadata table.
- UI files unless Jacob explicitly promotes this from backend/product contract to UI implementation.

## Non-goals

- No autonomous actions.
- No hidden ingestion of private files.
- No sending document contents to cloud without explicit approval.
- No fake citations.
- No broad rewrite of `knowledge.py` unless tests prove it is necessary.
- No native app, PWA, or UI implementation in this packet.
- No replacing ChromaDB/vector storage as part of v1.

## Acceptance criteria

- A user can import a sample PDF or text document.
- The imported document appears in inventory.
- A query retrieves relevant chunks with source/page or source/chunk references.
- Expert mode can answer using retrieved sources only.
- If no uploaded source supports the answer, Kitty says so instead of guessing.
- Tests cover ingest, inventory, search, citation formatting, expert no-source behavior, and failure reporting.
- Privacy boundary is documented and enforced in the code path used by expert retrieval.

## Verification

```bash
python3.12 -m pytest tests/test_knowledge*.py tests/ -q --tb=short
# Manual: import a sample PDF, confirm inventory lists it, search finds a cited chunk,
# and an expert answer refuses unsupported claims.
```

## Risks / rollback

- **Citation drift:** mitigated by requiring answers to cite retrieved chunks and by testing no-source behavior.
- **Cloud privacy leak:** mitigated by local-first default and explicit approval before document contents leave the machine.
- **Pipeline rewrite creep:** mitigated by productizing existing seams first. Rollback: revert the packet implementation PR; existing knowledge data remains inert.

## Too broad if

It builds a full UI, adds autonomous actions, rewrites the whole knowledge pipeline, swaps vector databases, sends files to cloud silently, adds email/GitHub/calendar actions, or treats experts as independent agents with their own authority to act.

## Jacob reviews

- Source collections/tags.
- Which experts ship first.
- Whether any document type is allowed to use cloud models.
- Citation format that feels trustworthy enough to use daily.
