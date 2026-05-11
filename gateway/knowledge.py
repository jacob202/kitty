"""ChromaDB knowledge base for Kitty Gateway.

Facade module that chains Clerk → Librarian → Archivist for document ingestion.
All symbols from the sub-modules are re-exported so existing callers don't break.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kitty.knowledge")

# ---------------------------------------------------------------------------
# Re-export from sub-modules so existing callers are unaffected
# ---------------------------------------------------------------------------
from gateway.clerk import (
    _extract_chatgpt_json,
    _extract_csv,
    _extract_epub,
    _extract_jsonl_session,
    _extract_mobi,
    _extract_pdf,
    _extract_pdf_pages,
    _extract_sqlite_journal,
    _extract_text,
    preprocess_text,
)
from gateway.librarian import detect_doc_type, generate_source_summary
from gateway.archivist import (
    _chunk_text,
    _embed,
    _embed_cached,
    _get_collection,
    _get_content_hash,
    delete_source_chunks,
    is_high_quality,
)

# ---------------------------------------------------------------------------
# Knowledge base constants
# ---------------------------------------------------------------------------
from gateway.paths import DATA_DIR
from gateway.llm_client import call_llm

KNOWLEDGE_DB_PATH = DATA_DIR / "knowledge_db"
COLLECTION_NAME = "kitty_knowledge"
EMBED_MODEL = "nomic-embed-text"

# Chunk sizes tuned per document type
_CHUNK_PROFILES = {
    "service_manual":   {"size": 256,  "overlap": 32},
    "textbook":         {"size": 768,  "overlap": 128},
    "textbook-chapter": {"size": 768,  "overlap": 128},
    "session_log":      {"size": 384,  "overlap": 48},
    "health_record":    {"size": 256,  "overlap": 32},
    "data_table":       {"size": 128,  "overlap": 0},
    "general":          {"size": 512,  "overlap": 64},
}


# ---------------------------------------------------------------------------
# Ingest pipeline: Clerk → Librarian → Archivist
# ---------------------------------------------------------------------------
def ingest_file(
    file_path: str | Path,
    sensitivity: str = "low",
    source_label: Optional[str] = None,
    doc_type: Optional[str] = None,
    force_refresh: bool = False,
) -> int:
    """Ingest a file into ChromaDB with intelligent judgment and rich metadata.

    Pipeline stages:
      1. Clerk extracts raw text from the file.
      2. Librarian judges document type and generates source summary.
      3. Archivist chunks, quality-filters, embeds, and stores in ChromaDB.
    """
    import time

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # ---- Stage 1: Clerk — text extraction ----
    raw_text = _extract_text(path)
    source = source_label or path.name

    # ---- Stage 1b: Archivist — dedup & update check ----
    collection = _get_collection()
    content_hash = _get_content_hash(raw_text) if raw_text else _get_content_hash(str(path))
    existing_hash = collection.get(where={"content_hash": content_hash})
    if existing_hash["ids"] and not force_refresh:
        logger.info("Content from %s already ingested (hash match), skipping", source)
        return 0

    existing_source = collection.get(where={"source": source})
    if existing_source["ids"]:
        logger.info("New content detected for %s, pruning old chunks...", source)
        delete_source_chunks(source)

    # ---- Stage 2: Librarian — doc-type detection & quality judgment ----
    resolved_type = doc_type or detect_doc_type(path, raw_text[:1000] if raw_text else "")
    taste_data = generate_source_summary(source, raw_text[:4000], resolved_type)
    source_brief = taste_data.get("summary", "")
    needs_vision = taste_data.get("needs_vision", False)

    profile = _CHUNK_PROFILES.get(resolved_type, _CHUNK_PROFILES["general"])
    chunks: list[str] = []
    chunk_metadatas: list[dict] = []

    # --- SOURCE BRIEF ---
    chunks.append(f"SOURCE BRIEF: {source_brief}")
    chunk_metadatas.append({
        "chunk_index": -1,
        "is_visual": False,
        "doc_type": "source_summary",
        "authority_score": taste_data.get("authority_score"),
        "relevance_period": taste_data.get("relevance_period"),
        "primary_topic": taste_data.get("primary_topic"),
        "pollution_warning": taste_data.get("pollution_warning"),
    })

    # ---- Stage 3a: Archivist — content extraction & chunking ----
    if path.suffix.lower() == ".pdf":
        pages = _extract_pdf_pages(path)
        for page_num, page_text in pages:
            clean = preprocess_text(page_text)
            if not clean:
                continue
            for i, chunk in enumerate(_chunk_text(clean, profile["size"], profile["overlap"])):
                if is_high_quality(chunk):
                    chunks.append(chunk)
                    chunk_metadatas.append({
                        "chunk_index": len(chunks),
                        "is_visual": False,
                        "page_num": page_num,
                    })
    else:
        clean = preprocess_text(raw_text)
        if clean:
            for i, chunk in enumerate(_chunk_text(clean, profile["size"], profile["overlap"])):
                if is_high_quality(chunk):
                    chunks.append(chunk)
                    chunk_metadatas.append({
                        "chunk_index": i,
                        "is_visual": False,
                    })

    # ---- Stage 3b: Archivist — vision enrichment ----
    if needs_vision or resolved_type == "service_manual":
        logger.info("Intelligent Vision triggered for %s (judgment: %s)", source, needs_vision)
        from gateway.librarian import _extract_visual_descriptions

        visual_info = _extract_visual_descriptions(path)
        for info in visual_info:
            chunks.append(info["text"])
            chunk_metadatas.append({
                **info["metadata"],
                "chunk_index": len(chunks) + 1000,
                "is_visual": True,
            })

    if not chunks:
        logger.warning("No high-quality content found to ingest from %s", path)
        return 0

    # ---- Stage 3c: Archivist — embed & store ----
    embeddings = _embed(chunks)
    ids = [f"{source}__chunk_{i}_{int(time.time())}" for i in range(len(chunks))]

    try:
        stat = path.stat()
        mtime = int(stat.st_mtime)
        ctime = int(stat.st_ctime)
    except Exception:
        mtime = ctime = int(time.time())

    def _safe_meta(val):
        if val is None:
            return ""
        if isinstance(val, (str, int, float, bool)):
            return val
        return str(val)

    final_metadatas = []
    for meta in chunk_metadatas:
        m = {
            "source": _safe_meta(source),
            "file_path": _safe_meta(str(path)),
            "sensitivity": _safe_meta(sensitivity),
            "doc_type": _safe_meta(resolved_type if "doc_type" not in meta else meta["doc_type"]),
            "content_hash": _safe_meta(content_hash),
            "modified_at": mtime,
            "created_at": ctime,
            "ingested_at": int(time.time()),
            "authority_score": _safe_meta(taste_data.get("authority_score")),
            "relevance_period": _safe_meta(taste_data.get("relevance_period")),
            "primary_topic": _safe_meta(taste_data.get("primary_topic")),
        }
        for k, v in meta.items():
            if k not in m:
                m[k] = _safe_meta(v)
        final_metadatas.append(m)

    collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=final_metadatas)
    logger.info(
        "Ingested %d high-quality chunks from %s (type=%s, vision=%s)",
        len(chunks),
        source,
        resolved_type,
        any(m.get("is_visual") for m in chunk_metadatas),
    )
    return len(chunks)


# ---------------------------------------------------------------------------
# Search helpers (live in knowledge.py — thin wrappers around Archivist)
# ---------------------------------------------------------------------------
def search_knowledge(
    query: str,
    limit: int = 5,
    sensitivity_filter: Optional[str] = None,
    sort_by: str = "relevance",
    stitch_context: bool = True,
) -> list[dict]:
    """Search ChromaDB for chunks relevant to query, with optional context stitching."""
    try:
        query_embedding = list(_embed_cached(query))
        where = {"sensitivity": sensitivity_filter} if sensitivity_filter else None

        results = _get_collection().query(
            query_embeddings=[query_embedding],
            n_results=min(limit * 3, max(1, _get_collection().count())),
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

            if stitch_context and "chunk_index" in meta and meta.get("doc_type") not in (
                "source_summary",
                "visual_description",
            ):
                source = meta["source"]
                idx = meta["chunk_index"]
                neighbor_results = _get_collection().get(
                    where={"$and": [{"source": source}, {"chunk_index": {"$in": [idx - 1, idx + 1]}}]}
                )
                if neighbor_results["ids"]:
                    neighbors = {}
                    for n_idx, n_meta in enumerate(neighbor_results["metadatas"]):
                        neighbors[n_meta["chunk_index"]] = neighbor_results["documents"][n_idx]
                    stitched = []
                    if idx - 1 in neighbors:
                        stitched.append(neighbors[idx - 1])
                    stitched.append(doc)
                    if idx + 1 in neighbors:
                        stitched.append(neighbors[idx + 1])
                    chunk_data["text"] = "\n[...]\n".join(stitched)
                    chunk_data["stitched"] = True

            chunks.append(chunk_data)

        if sort_by == "recency":
            chunks.sort(key=lambda x: x["ingested_at"], reverse=True)
        else:
            chunks.sort(key=lambda x: x["score"], reverse=True)

        return chunks[:limit]
    except Exception as e:
        logger.warning("Knowledge search failed: %s", e)
        return []


def get_knowledge_block(query: str, limit: int = 5) -> str:
    """Return a formatted context block to inject into the system prompt."""
    chunks = search_knowledge(query, limit=limit)
    if not chunks:
        return ""
    lines = ["## Relevant knowledge from Kitty's knowledge base:"]
    for chunk in chunks:
        source = chunk["source"]
        doc_type = chunk.get("doc_type", "general")
        label = f"[Source: {source}" + (f" | type: {doc_type}]" if doc_type != "general" else "]")
        lines.append(f"\n{label}")
        lines.append(chunk["text"][:400])
    return "\n".join(lines)