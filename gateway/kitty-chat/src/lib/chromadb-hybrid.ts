/**
 * ChromaDB Hybrid Search — keyword + vector search in a single query.
 *
 * The truth: ChromaDB does NOT natively support hybrid (BM25 + vector) search.
 * It's a pure vector database. Every blog post claiming "hybrid search in
 * ChromaDB" is either:
 *   (a) Running TWO queries and merging results client-side, or
 *   (b) Using the now-deprecated "default_ef" param which was an HNSW efSearch
 *       parameter, NOT a hybrid search parameter.
 *
 * What "hnsw:ef_search" actually does: controls the HNSW graph search width
 * (trade recall for speed). Higher values = better recall, slower queries.
 *
 * TRUE hybrid search requires:
 *   1. A separate keyword index (e.g., Tantivy, Whoosh, SQLite FTS5)
 *   2. Run both searches independently
 *   3. Merge & rerank results (RRF or weighted fusion)
 *
 * Below: the correct pattern for hybrid search with ChromaDB + SQLite FTS5.
 * This is the pattern used by LangChain's SelfQueryRetriever and Qdrant's
 * hybrid search — adapted for Kitty's existing ChromaDB setup.
 *
 * Stolen from: LangChain (MIT), Qdrant hybrid search docs (Apache 2),
 * SQLite FTS5 docs (public domain).
 */

// ── THIS IS NOT NEEDED IN TYPESCRIPT ──────────────────────────────────
// The hybrid search runs in Python (gateway). See gateway/hybrid_search.py
// for the actual implementation. This file exists to document the pattern
// for the TypeScript layer and to provide the API types.
//
// The Kitty gateway already uses ChromaDB via gateway/archivist.py and
// gateway/knowledge.py. Adding SQLite FTS5 to those modules gives us
// true hybrid search with zero new dependencies.

export interface HybridSearchResult {
  text: string
  source: string
  score: number       // Combined (fused) score
  vectorScore: number // Cosine similarity component
  keywordScore: number // BM25 / FTS5 component
  docType: string
}

export interface HybridSearchOptions {
  query: string
  limit?: number
  collections?: string[]
  sensitivityFilter?: string
  /** Weight for vector score in fusion (0-1). keyword weight = 1 - alpha */
  alpha?: number
}
