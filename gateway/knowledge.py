"""Robust Knowledge Pipeline — orchestrates document ingestion and retrieval.

This is a DEEP module. Callers should only use the high-leverage public interface:
- ingest(): Handle full document lifecycle (extract -> judge -> chunk -> store).
- search(): Unified vector search with context stitching.
- delete_source(): Prune document chunks.
- get_inventory(): Get source/chunk counts.

Internal pipeline stages (Clerk, Librarian, Archivist) are implementation details.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from contracts.knowledge_pipeline import LibrarianReport, KnowledgeMetadata, IngestionResult
from gateway import clerk, librarian, archivist

logger = logging.getLogger("kitty.knowledge")

# Configuration moved from implementation details
_CHUNK_PROFILES = librarian._CHUNK_PROFILES


async def ingest(
    file_path: str | Path,
    sensitivity: str = "low",
    source_label: Optional[str] = None,
    doc_type: Optional[str] = None,
    force_refresh: bool = False,
) -> IngestionResult:
    """High-leverage entry point for document ingestion."""
    path = Path(file_path)
    if not path.exists():
        return IngestionResult(
            source=str(file_path), 
            status="failed", 
            content_hash="", 
            error_message=f"File not found: {path}"
        )

    # 1. Extraction (Clerk)
    raw_text = clerk._extract_text(path)
    source = source_label or path.name

    # 2. Ingestion Contract (Hashing & Dedup)
    content_hash = archivist._get_content_hash(raw_text) if raw_text else archivist._get_content_hash(str(path))
    collection = archivist._get_collection()
    
    if not force_refresh:
        existing = collection.get(where={"content_hash": content_hash})
        if existing["ids"]:
            logger.info("Content from %s already ingested (hash match), skipping", source)
            return IngestionResult(source=source, status="skipped", content_hash=content_hash)

    # 3. Cleanup existing chunks for this source name
    existing_source = collection.get(where={"source": source})
    if existing_source["ids"]:
        logger.info("New content detected for %s, pruning old chunks...", source)
        archivist.delete_source_chunks(source)

    # 4. Judgment (Librarian)
    resolved_type = doc_type or librarian.detect_doc_type(path, raw_text[:1000] if raw_text else "")
    taste_report: LibrarianReport = await asyncio.to_thread(
        librarian.generate_source_summary, source, raw_text[:4000], resolved_type
    )

    # 5. Pipeline Execution
    chunks, chunk_metadatas = await _run_pipeline(path, raw_text, source, resolved_type, taste_report)

    if not chunks:
        logger.warning("No high-quality content found to ingest from %s", path)
        return IngestionResult(source=source, status="skipped", content_hash=content_hash)

    # 6. Storage (Archivist)
    embeddings = await asyncio.to_thread(archivist._embed, chunks)
    ids = [f"{source}__chunk_{i}_{int(time.time())}" for i in range(len(chunks))]

    final_metadatas = _prepare_metadatas(path, source, sensitivity, resolved_type, content_hash, taste_report, chunk_metadatas)
    collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=final_metadatas)
    
    logger.info("Ingested %d chunks from %s (type=%s)", len(chunks), source, resolved_type)
    return IngestionResult(source=source, status="success", chunks_count=len(chunks), content_hash=content_hash)


async def search(
    query: str,
    limit: int = 5,
    sensitivity_filter: Optional[str] = None,
    sort_by: str = "relevance",
    stitch_context: bool = True,
) -> List[Dict[str, Any]]:
    """Unified search with optional context stitching."""
    try:
        query_embedding = list(archivist._embed_cached(query))
        where = {"sensitivity": sensitivity_filter} if sensitivity_filter else None
        collection = archivist._get_collection()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit * 3, max(1, collection.count())),
            where=where,
        )

        chunks = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            dist = results["distances"][0][i] if results["distances"] else 1.0

            chunk_data = {
                "text": doc,
                "source": meta.get("source", "unknown"),
                "doc_type": meta.get("doc_type", "general"),
                "score": 1.0 - dist,
                "ingested_at": meta.get("ingested_at", 0),
                "index": meta.get("chunk_index", 0),
                "metadata": meta,
            }
            
            if stitch_context and "chunk_index" in meta and meta.get("doc_type") not in ("source_summary", "visual_description"):
                chunk_data["text"] = _stitch_neighbor_context(collection, meta, doc)
                chunk_data["stitched"] = True

            chunks.append(chunk_data)
        
        chunks.sort(key=lambda x: x["ingested_at" if sort_by == "recency" else "score"], reverse=True)
        return chunks[:limit]
    except Exception as e:
        logger.warning("Knowledge search failed: %s", e)
        return []


def delete_source(source_name: str) -> bool:
    """Prune all chunks belonging to a source."""
    return archivist.delete_source_chunks(source_name)


def get_inventory() -> Dict[str, int]:
    """Get source/chunk counts for status reporting."""
    try:
        collection = archivist._get_collection()
        count = collection.count()
        if count == 0: return {}
        
        metas = collection.get(include=["metadatas"])["metadatas"]
        inventory = {}
        for m in metas:
            name = m.get("source", "unknown")
            inventory[name] = inventory.get(name, 0) + 1
        return inventory
    except Exception as e:
        logger.error("Failed to get knowledge inventory: %s", e)
        return {}


# --- Private Implementation Details ---

async def _run_pipeline(path: Path, raw_text: str, source: str, doc_type: str, taste: LibrarianReport) -> tuple[list[str], list[dict]]:
    """Private orchestration of the pipeline stages."""
    profile = _CHUNK_PROFILES.get(doc_type, _CHUNK_PROFILES["general"])
    chunks: list[str] = []
    chunk_metadatas: list[dict] = []

    # A. Source Brief
    chunks.append(f"SOURCE BRIEF: {taste.summary}")
    chunk_metadatas.append({"chunk_index": -1, "doc_type": "source_summary", "is_visual": False})

    # B. Content Extraction & Chunking
    if path.suffix.lower() == ".pdf":
        pages = clerk._extract_pdf_pages(path)
        for page_num, page_text in pages:
            clean = clerk.preprocess_text(page_text)
            if not clean: continue
            for chunk in archivist._chunk_text(clean, profile["size"], profile["overlap"]):
                if archivist.is_high_quality(chunk):
                    chunks.append(chunk)
                    chunk_metadatas.append({"chunk_index": len(chunks), "is_visual": False, "page_num": page_num})
    else:
        clean = clerk.preprocess_text(raw_text)
        if clean:
            for i, chunk in enumerate(archivist._chunk_text(clean, profile["size"], profile["overlap"])):
                if archivist.is_high_quality(chunk):
                    chunks.append(chunk)
                    chunk_metadatas.append({"chunk_index": i, "is_visual": False})

    # C. Vision Enrichment
    if taste.needs_vision or doc_type == "service_manual":
        visual_info = await asyncio.to_thread(clerk._extract_visual_descriptions, path)
        for info in visual_info:
            chunks.append(info.text)
            chunk_metadatas.append({
                "chunk_index": len(chunks) + 1000,
                "is_visual": True,
                "page_num": info.page_num,
                "analysis_type": info.analysis_type
            })

    return chunks, chunk_metadatas


def _prepare_metadatas(path: Path, source: str, sensitivity: str, doc_type: str, content_hash: str, taste: LibrarianReport, chunk_metadatas: list[dict]) -> list[dict]:
    """Standardize metadata for all chunks using KnowledgeMetadata contract."""
    try:
        stat = path.stat()
        mtime, ctime = int(stat.st_mtime), int(stat.st_ctime)
    except Exception:
        mtime = ctime = int(time.time())

    final = []
    for meta in chunk_metadatas:
        km = KnowledgeMetadata(
            source=source,
            file_path=str(path),
            sensitivity=sensitivity,
            doc_type=meta.get("doc_type", doc_type),
            content_hash=content_hash,
            modified_at=mtime,
            created_at=ctime,
            ingested_at=int(time.time()),
            authority_score=taste.authority_score,
            relevance_period=taste.relevance_period,
            primary_topic=taste.primary_topic,
            chunk_index=meta["chunk_index"],
            is_visual=meta.get("is_visual", False),
            page_num=meta.get("page_num"),
            analysis_type=meta.get("analysis_type"),
            pollution_warning=taste.pollution_warning
        )
        final.append(km.to_chroma())
    return final


def _stitch_neighbor_context(collection: Any, meta: dict, doc: str) -> str:
    """Fetch and join neighboring chunks (+/- 1) for better context."""
    source = meta["source"]
    idx = meta["chunk_index"]
    neighbor_results = collection.get(
        where={"$and": [{"source": source}, {"chunk_index": {"$in": [idx-1, idx+1]}}]}
    )
    
    if neighbor_results["ids"]:
        neighbors = {n_meta["chunk_index"]: n_doc for n_idx, (n_meta, n_doc) in enumerate(zip(neighbor_results["metadatas"], neighbor_results["documents"]))}
        parts = []
        if idx - 1 in neighbors: parts.append(neighbors[idx-1])
        parts.append(doc)
        if idx + 1 in neighbors: parts.append(neighbors[idx+1])
        return "\n[...]\n".join(parts)
    return doc


# Backward compatibility aliases
async def ingest_file(*args, **kwargs): return await ingest(*args, **kwargs)
def search_knowledge(*args, **kwargs): return search(*args, **kwargs)

# Backwards-compat re-exports so existing tests can import/patch these names directly
# on the knowledge module rather than on the sub-modules.
from gateway.clerk import (  # noqa: E402
    _extract_text,
    _extract_jsonl_session,
    _extract_chatgpt_json,
    _extract_sqlite_journal,
)
from gateway.librarian import detect_doc_type  # noqa: E402
from gateway.archivist import _chunk_text, _get_collection, _embed  # noqa: E402
def get_knowledge_block(query: str, limit: int = 5) -> str:
    """Return a formatted context block to inject into the system prompt."""
    import asyncio
    # search is now async but this legacy helper is sync
    try:
        # Note: This is risky in a pure async loop, but this helper is only used by legacy sync callers
        # In Phase 3 (Context Control Plane), this will be replaced.
        chunks = asyncio.run(search(query, limit=limit))
    except RuntimeError:
        # If already in an event loop (e.g. FastAPI), we need another approach
        # For now, just return empty to avoid blocking
        return ""

    if not chunks: return ""
    lines = ["## Relevant knowledge from Kitty's knowledge base:"]
    for chunk in chunks:
        label = f"[Source: {chunk['source']} | type: {chunk['doc_type']}]"
        lines.append(f"\n{label}\n{chunk['text'][:400]}")
    return "\n".join(lines)
