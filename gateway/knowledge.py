"""Robust Knowledge Pipeline — orchestrates document ingestion and retrieval.

This is a DEEP module. Callers should only use the high-leverage public interface:
- ingest(): Handle full document lifecycle (extract -> judge -> chunk -> store).
- search(): Unified vector search with context stitching.
- answer_as_expert(): Local-only, collection-scoped answers with citations.
- delete_source(): Prune document chunks.
- get_inventory(): Get source/chunk counts.

Internal pipeline stages (Clerk, Librarian, Archivist) are implementation details.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx

from contracts.knowledge_pipeline import (
    IngestionResult,
    KnowledgeMetadata,
    LibrarianReport,
)
from gateway import archivist, clerk, librarian
from gateway.paths import PROJECT_ROOT

logger = logging.getLogger("kitty.knowledge")

# Configuration moved from implementation details
_CHUNK_PROFILES = librarian._CHUNK_PROFILES

LOCAL_EXPERT_URL = "http://127.0.0.1:8010/v1/chat/completions"
LOCAL_EXPERT_MODEL = "default_model"
EXPERT_PROFILES: dict[str, dict[str, Any]] = {
    "coding_repo": {
        "prompt_path": PROJECT_ROOT / "soul" / "specialists" / "coder.md",
        "collections": ["coding_repo"],
    }
}


class KnowledgeSearchError(RuntimeError):
    """Raised when retrieval failed instead of legitimately finding no matches."""


class ExpertAnswerError(RuntimeError):
    """Raised when a local expert cannot produce a supported, cited answer."""


class UnknownExpertError(ExpertAnswerError):
    """Raised when a caller requests an expert profile that does not exist."""


async def ingest(
    file_path: str | Path,
    sensitivity: str = "low",
    source_label: Optional[str] = None,
    doc_type: Optional[str] = None,
    collection: str = "general",
    tags: Optional[list[str]] = None,
    force_refresh: bool = False,
) -> IngestionResult:
    """High-leverage entry point for document ingestion."""
    path = Path(file_path)
    if not path.exists():
        return IngestionResult(
            source=str(file_path),
            status="failed",
            content_hash="",
            error_message=f"File not found: {path}",
        )

    # 1. Extraction (Clerk)
    raw_text = clerk._extract_text(path)
    source = source_label or path.name

    # 2. Ingestion Contract (Hashing & Dedup)
    content_hash = (
        archivist._get_content_hash(raw_text)
        if raw_text
        else archivist._get_content_hash(str(path))
    )
    store = archivist._get_collection()

    if not force_refresh:
        existing = store.get(where={"content_hash": content_hash})
        if existing["ids"]:
            logger.info("Content from %s already ingested (hash match), skipping", source)
            return IngestionResult(source=source, status="skipped", content_hash=content_hash)

    # 3. Cleanup existing chunks for this source name
    existing_source = store.get(where={"source": source})
    if existing_source["ids"]:
        logger.info("New content detected for %s, pruning old chunks...", source)
        archivist.delete_source_chunks(source)

    # 4. Judgment (Librarian)
    resolved_type = doc_type or librarian.detect_doc_type(path, raw_text[:1000] if raw_text else "")
    taste_report: LibrarianReport = await asyncio.to_thread(
        librarian.generate_source_summary, source, raw_text[:4000], resolved_type
    )

    # 5. Pipeline Execution
    chunks, chunk_metadatas = await _run_pipeline(
        path, raw_text, source, resolved_type, taste_report
    )

    if not chunks:
        logger.warning("No high-quality content found to ingest from %s", path)
        return IngestionResult(source=source, status="skipped", content_hash=content_hash)

    # 6. Storage (Archivist)
    embeddings = await asyncio.to_thread(archivist._embed, chunks)
    ids = [f"{source}__chunk_{i}_{int(time.time())}" for i in range(len(chunks))]

    final_metadatas = _prepare_metadatas(
        path,
        source,
        sensitivity,
        resolved_type,
        collection,
        tags or [],
        content_hash,
        taste_report,
        chunk_metadatas,
    )
    store.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=final_metadatas)

    logger.info("Ingested %d chunks from %s (type=%s)", len(chunks), source, resolved_type)
    return IngestionResult(
        source=source,
        status="success",
        chunks_count=len(chunks),
        content_hash=content_hash,
    )


async def search(
    query: str,
    limit: int = 5,
    sensitivity_filter: Optional[str] = None,
    collections: Optional[list[str]] = None,
    sort_by: str = "relevance",
    stitch_context: bool = True,
) -> List[Dict[str, Any]]:
    """Unified search with optional context stitching."""
    try:
        query_embedding = list(archivist._embed_cached(query))
        where = _build_search_filter(sensitivity_filter, collections)
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

            if (
                stitch_context
                and "chunk_index" in meta
                and meta.get("doc_type") not in ("source_summary", "visual_description")
            ):
                chunk_data["text"] = _stitch_neighbor_context(collection, meta, doc)
                chunk_data["stitched"] = True

            chunks.append(chunk_data)

        chunks.sort(
            key=lambda x: x["ingested_at" if sort_by == "recency" else "score"],
            reverse=True,
        )
        return chunks[:limit]
    except Exception as exc:
        logger.exception("Knowledge search failed for query=%r", query)
        raise KnowledgeSearchError(
            f"knowledge search failed for query={query!r}: {type(exc).__name__}: {exc}"
        ) from exc


def _build_search_filter(
    sensitivity_filter: Optional[str],
    collections: Optional[list[str]],
) -> Optional[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    if sensitivity_filter:
        filters.append({"sensitivity": sensitivity_filter})
    if collections:
        filters.append({"collection": {"$in": sorted(set(collections))}})
    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    return {"$and": filters}


async def answer_as_expert(
    query: str,
    expert: str = "coding_repo",
    limit: int = 5,
    answerer: Optional[Callable[[str], str]] = None,
) -> dict[str, Any]:
    """Answer from an expert's allowed uploaded collections, entirely locally."""
    profile = EXPERT_PROFILES.get(expert)
    if profile is None:
        raise UnknownExpertError(
            f"unknown knowledge expert {expert!r}; available experts: {sorted(EXPERT_PROFILES)}"
        )

    collections = list(profile["collections"])
    chunks = await search(
        query,
        limit=limit,
        collections=collections,
        stitch_context=False,
    )
    if not chunks:
        collection_names = ", ".join(collections)
        return {
            "expert": expert,
            "supported": False,
            "answer": (
                f"Uploaded sources in collection '{collection_names}' do not support this answer."
            ),
            "citations": [],
            "privacy": "local",
        }

    citations = [_citation_from_chunk(index, chunk) for index, chunk in enumerate(chunks, start=1)]
    prompt = _build_expert_prompt(query, profile, chunks, citations)
    answer_fn = answerer or _call_local_expert_model
    try:
        answer = await asyncio.to_thread(answer_fn, prompt)
    except ExpertAnswerError:
        raise
    except Exception as exc:
        raise ExpertAnswerError(
            f"local expert answerer failed: {type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(answer, str) or not answer.strip():
        raise ExpertAnswerError("local expert answerer returned an empty response")
    answer = answer.strip()
    if not any(f"[{citation['id']}]" in answer for citation in citations):
        raise ExpertAnswerError("local expert answer did not include a retrieved-source citation")

    return {
        "expert": expert,
        "supported": True,
        "answer": answer,
        "citations": citations,
        "privacy": "local",
    }


def _citation_from_chunk(
    citation_id: int,
    chunk: dict[str, Any],
) -> dict[str, Any]:
    source = str(chunk.get("source") or "").strip()
    text = str(chunk.get("text") or "").strip()
    if not source or not text:
        raise ExpertAnswerError(f"retrieved chunk {citation_id} is missing source or text")

    metadata = chunk.get("metadata") or {}
    page_num = metadata.get("page_num")
    chunk_index = metadata.get("chunk_index", chunk.get("index"))
    if page_num is not None:
        label = f"{source}, page {page_num}"
    elif chunk_index is not None:
        label = f"{source}, chunk {chunk_index}"
    else:
        label = source
    return {
        "id": citation_id,
        "source": source,
        "page_num": page_num,
        "chunk_index": chunk_index,
        "label": label,
    }


def _build_expert_prompt(
    query: str,
    profile: dict[str, Any],
    chunks: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> str:
    prompt_path = Path(profile["prompt_path"])
    try:
        specialist_prompt = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExpertAnswerError(f"could not read expert prompt {prompt_path}: {exc}") from exc

    excerpts: list[str] = []
    for chunk, citation in zip(chunks, citations):
        excerpts.append(f"[{citation['id']}] {citation['label']}\n{str(chunk['text']).strip()}")

    return (
        f"{specialist_prompt}\n\n"
        "## RETRIEVAL CONTRACT\n"
        "Use only the uploaded source excerpts below. "
        "Cite every supported claim with [n]. "
        "If the excerpts do not support the answer, say so plainly.\n\n"
        f"Question: {query.strip()}\n\n"
        "Uploaded source excerpts:\n" + "\n\n".join(excerpts)
    )


def _call_local_expert_model(prompt: str) -> str:
    """Call the loopback-only MLX server; this path never contacts cloud models."""
    payload = {
        "model": LOCAL_EXPERT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1200,
        "temperature": 0.1,
    }
    response: httpx.Response | None = None
    for attempt in range(2):
        try:
            response = httpx.post(
                LOCAL_EXPERT_URL,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            break
        except httpx.HTTPError as exc:
            if attempt == 0:
                logger.warning(
                    "Local MLX expert request failed; retrying once: url=%s model=%s error=%s",
                    LOCAL_EXPERT_URL,
                    LOCAL_EXPERT_MODEL,
                    exc,
                )
                continue
            failed_response = getattr(exc, "response", None)
            status = getattr(failed_response, "status_code", "unavailable")
            body = str(getattr(failed_response, "text", "") or "<no response body>")
            raise ExpertAnswerError(
                "local MLX expert request failed after 2 attempts: "
                f"url={LOCAL_EXPERT_URL} model={LOCAL_EXPERT_MODEL} "
                f"status={status} response={body[:500]!r} error={exc}"
            ) from exc

    if response is None:
        raise ExpertAnswerError("local MLX expert request produced no response")
    try:
        data = response.json()
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ExpertAnswerError(
            "local MLX expert returned an invalid response: "
            f"status={response.status_code} response={response.text[:500]!r}"
        ) from exc
    if not isinstance(answer, str) or not answer.strip():
        raise ExpertAnswerError("local MLX expert returned empty message content")
    return answer.strip()


def delete_source(source_name: str) -> bool:
    """Prune all chunks belonging to a source."""
    return archivist.delete_source_chunks(source_name)


def get_inventory() -> Dict[str, int]:
    """Get source/chunk counts for status reporting."""
    try:
        collection = archivist._get_collection()
        count = collection.count()
        if count == 0:
            return {}

        metas = collection.get(include=["metadatas"])["metadatas"]
        inventory: dict[str, int] = {}
        for m in metas:
            name = m.get("source", "unknown")
            inventory[name] = inventory.get(name, 0) + 1
        return inventory
    except Exception as e:
        logger.error("Failed to get knowledge inventory: %s", e)
        return {}


# --- Private Implementation Details ---


async def _run_pipeline(
    path: Path, raw_text: str, source: str, doc_type: str, taste: LibrarianReport
) -> tuple[list[str], list[dict]]:
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
            if not clean:
                continue
            for chunk in archivist._chunk_text(clean, profile["size"], profile["overlap"]):
                if archivist.is_high_quality(chunk):
                    chunks.append(chunk)
                    chunk_metadatas.append(
                        {
                            "chunk_index": len(chunks),
                            "is_visual": False,
                            "page_num": page_num,
                        }
                    )
    else:
        clean = clerk.preprocess_text(raw_text)
        if clean:
            for i, chunk in enumerate(
                archivist._chunk_text(clean, profile["size"], profile["overlap"])
            ):
                if archivist.is_high_quality(chunk):
                    chunks.append(chunk)
                    chunk_metadatas.append({"chunk_index": i, "is_visual": False})

    # C. Vision Enrichment
    if taste.needs_vision or doc_type == "service_manual":
        visual_info = await asyncio.to_thread(clerk._extract_visual_descriptions, path)
        for info in visual_info:
            chunks.append(info.text)
            chunk_metadatas.append(
                {
                    "chunk_index": len(chunks) + 1000,
                    "is_visual": True,
                    "page_num": info.page_num,
                    "analysis_type": info.analysis_type,
                }
            )

    return chunks, chunk_metadatas


def _prepare_metadatas(
    path: Path,
    source: str,
    sensitivity: str,
    doc_type: str,
    collection: str,
    tags: list[str],
    content_hash: str,
    taste: LibrarianReport,
    chunk_metadatas: list[dict],
) -> list[dict]:
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
            collection=collection,
            tags_json=json.dumps(tags, separators=(",", ":")),
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
            pollution_warning=taste.pollution_warning,
        )
        final.append(km.to_chroma())
    return final


def _stitch_neighbor_context(collection: Any, meta: dict, doc: str) -> str:
    """Fetch and join neighboring chunks (+/- 1) for better context."""
    source = meta["source"]
    idx = meta["chunk_index"]
    neighbor_results = collection.get(
        where={"$and": [{"source": source}, {"chunk_index": {"$in": [idx - 1, idx + 1]}}]}
    )

    if neighbor_results["ids"]:
        neighbors = {
            n_meta["chunk_index"]: n_doc
            for n_idx, (n_meta, n_doc) in enumerate(
                zip(neighbor_results["metadatas"], neighbor_results["documents"])
            )
        }
        parts = []
        if idx - 1 in neighbors:
            parts.append(neighbors[idx - 1])
        parts.append(doc)
        if idx + 1 in neighbors:
            parts.append(neighbors[idx + 1])
        return "\n[...]\n".join(parts)
    return doc


# Backward compatibility aliases
async def ingest_file(*args, **kwargs):
    return await ingest(*args, **kwargs)


async def search_knowledge(*args, **kwargs):
    return await search(*args, **kwargs)


# Backwards-compat re-exports so existing tests can import/patch these names directly
# on the knowledge module rather than on the sub-modules.
from gateway.archivist import _chunk_text, _embed, _get_collection  # noqa: E402, F401
from gateway.clerk import (  # noqa: E402, F401
    _extract_chatgpt_json,
    _extract_jsonl_session,
    _extract_sqlite_journal,
    _extract_text,
)
from gateway.librarian import detect_doc_type  # noqa: E402, F401


def get_knowledge_block(query: str, limit: int = 5) -> str:
    """Format a knowledge context block for **synchronous** callers (scripts, tests).

    **Do not** call this from inside an async request handler or running event loop:
    use ``await knowledge.search(...)`` or ``await context_builder.get_system_prompt(...)``
    instead. Inside a loop, this function returns an empty string to avoid nest-async bugs.

    For new code, prefer ``await search()`` and assemble prompts in ``context_builder``.
    """
    import asyncio

    try:
        chunks = asyncio.run(search(query, limit=limit))
    except RuntimeError:
        return ""

    if not chunks:
        return ""
    lines = ["## Relevant knowledge from Kitty's knowledge base:"]
    for chunk in chunks:
        src = chunk.get("source", "unknown")
        dtype = chunk.get("doc_type", "general")
        text = (chunk.get("text") or "")[:400]
        label = f"[Source: {src} | type: {dtype}]"
        lines.append(f"\n{label}\n{text}")
    return "\n".join(lines)
