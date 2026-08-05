# ADR 0034: Memory Policy Is a Kitty Concern — Storage Remains an Open Decision

**Date:** 2026-08-05
**Status:** Accepted

## Context

Kitty's memory system is its deepest subsystem: 9 stores, concurrent fetch,
privacy gates, token budgeting, consolidation pipeline, temporal knowledge graph
with confidence decay, and policy-based classification (architecture honesty
audit, 2026-07-24).

The architecture migration analysis (2026-08-05) proposed that Open Brain would
absorb all memory storage concerns (vector store, fact graph, signal store,
consolidation, document ingestion). The repository simplification audit
(2026-08-05) identified the 9-store architecture as excessive for a local-first
personal assistant and recommended consolidation to 3 stores (SQLite + single
vector + JSONL).

However, the product boundary question has never been formalized: what aspects of
memory are Kitty's unique product differentiation versus generic infrastructure?

## Decision

1. **Memory policy is a Kitty concern.** Kitty owns:
   - What surfaces versus what is filtered (privacy gates, sensitivity
     classification).
   - What is relevant to the current context (context assembly — ADR 0004).
   - How confidence decays and facts are corrected (temporal knowledge graph,
     correction with deprecation chains).
   - When consolidation and dreaming occur (session end, nightly cron).
   - How sensitive content is rewritten before being surfaced.

2. **Storage implementation is an open decision.** The current 9 stores may
   become 3 (SQLite + single vector + JSONL) or may eventually migrate to Open
   Brain — but the policy layer above storage does not change regardless of what
   stores the bytes. The memory graph's adapter pattern (`StoreAdapter` ABC,
   concrete adapters per store) was designed for this separation and should be
   preserved.

3. **The consolidation target is 3 stores** (ADR 0030) but the specific vector
   store choice (ChromaDB, SQLite-vec, or other) is deferred to implementation
   evaluation. The mem0 dependency should be removed in favor of direct embedding
   management.

## Alternatives considered

**Keep all 9 stores indefinitely:** Rejected. Nine stores spread across mem0,
ChromaDB, 5 SQLite DBs, 2 JSONL files, and mempalace create maintenance
burden, make the dependency chain heavy (mem0 → ChromaDB → Ollama → nomic
embeddings), and complicate context assembly.

**Migrate memory policy to Open Brain:** Rejected. Memory policy (what is
sensitive, what decays when, what surfaces versus what is filtered) is
Kitty's product judgment. Open Brain may store the facts, but Kitty decides
relevance. This is the same boundary as the foundation replacement study's
conclusion: "Mature shells may own generic interaction and infrastructure.
Kitty owns personal intelligence."

**Consolidate to a single database for everything:** Rejected. Capture/log
data (JSONL) has different access patterns than structured state (SQLite)
and vector embeddings. Three stores is the minimum practical number.

## Evidence

- Architecture honesty audit (2026-07-24): Memory system is 2,800+ lines
  across 7+ files. "The memory system is the most architecturally mature
  subsystem — better than the builder queue, better than the image system."
- Repository simplification audit (2026-08-05): 9 stores identified, 3-store
  consolidation target recommended.
- Architecture migration analysis (2026-08-05): Memory policy, context
  assembly, personality, and prompts classified as KEEP (product intelligence);
  storage backends classified as MERGE → Open Brain.
- mem0 dependency: Memory.py wraps mem0 with lazy init, ChromaDB backend,
  Ollama embeddings (nomic-embed-text), and LLM via LiteLLM — a chain of 4
  external dependencies for one storage concern.

## Consequences

- **Positive:** Clear separation: policy = Kitty, storage = replaceable.
  The adapter pattern is validated as the correct architectural seam.
- **Negative:** Storage consolidation is migration work with data integrity
  risk. The 3-store architecture may still be heavier than necessary if
  Open Brain matures and subsumes storage entirely.
- **Open question:** SQLite-vec versus ChromaDB as the single vector store.
  SQLite-vec eliminates an external process dependency but may have different
  performance characteristics.

## Risks

- Consolidation loses data: Mitigated by additive migrations, preserved
  originals, shadow reads, and per-phase rollback (Product Architecture §17).
- The policy layer is too tightly coupled to current store implementations:
  The `StoreAdapter` ABC and `GraphResult` pattern already exist. Consolidation
  should strengthen this abstraction, not bypass it.

## Follow-up work

- Remove mem0 dependency; replace with direct embedding management.
- Choose single vector backend: ChromaDB (keep current) or SQLite-vec (zero
  external process).
- Consolidate 5 SQLite stores + mempalace → main kitty.db.
- Preserve StoreAdapter pattern as the stable memory interface.

## Related ADRs

- ADR 0004: memory_graph owns context reads
- ADR 0030: Repository simplification is a strategic priority
- ADR 0031: Architecture migration deferred
