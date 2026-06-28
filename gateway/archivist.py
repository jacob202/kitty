"""Mechanical storage and retrieval for Kitty's knowledge base."""
import hashlib
import logging
import re
from functools import lru_cache

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.knowledge.archivist")

KNOWLEDGE_DB_PATH = DATA_DIR / "knowledge_db"
COLLECTION_NAME = "kitty_knowledge"
EMBED_MODEL = "nomic-embed-text:latest"
OLLAMA_BASE = "http://localhost:11434"
INGEST_EMBED_TIMEOUT_SECONDS = 120
QUERY_EMBED_TIMEOUT_SECONDS = 5

@lru_cache(maxsize=1)
def _get_collection():
    """Lazy-init ChromaDB collection."""
    import chromadb
    KNOWLEDGE_DB_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(KNOWLEDGE_DB_PATH))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _embed(
    texts: list[str],
    timeout: float = INGEST_EMBED_TIMEOUT_SECONDS,
) -> list[list[float]]:
    """Embed texts using nomic-embed-text via Ollama — batched to prevent timeouts."""
    import requests

    batch_size = 50
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            resp = requests.post(
                f"{OLLAMA_BASE}/api/embed",
                json={"model": EMBED_MODEL, "input": batch},
                timeout=timeout,
            )
            resp.raise_for_status()
            all_embeddings.extend(resp.json()["embeddings"])
        except Exception as e:
            logger.error("Embedding batch failed at index %d: %s", i, e)
            raise

    return all_embeddings


@lru_cache(maxsize=256)
def _embed_cached(text: str) -> tuple[float, ...]:
    """Cache embeddings for individual query strings."""
    result = _embed([text], timeout=QUERY_EMBED_TIMEOUT_SECONDS)[0]
    return tuple(result)


def _get_content_hash(text: str) -> str:
    """Generate SHA-256 hash of text."""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def delete_source_chunks(source_name: str) -> bool:
    """Delete all chunks belonging to a specific source from ChromaDB."""
    try:
        collection = _get_collection()
        collection.delete(where={"source": source_name})
        logger.info("Deleted existing chunks for source: %s", source_name)
        return True
    except Exception as e:
        logger.error("Failed to delete source %s: %s", source_name, e)
        return False


def is_high_quality(text: str) -> bool:
    """Heuristic check for chunk quality. Rejects junk/OCR noise."""
    if len(text) < 50:
        return False # Too short to be useful context

    # Check for excessive non-alphanumeric characters (typical of OCR garble)
    alnum_count = sum(c.isalnum() for c in text)
    if alnum_count / len(text) < 0.6:
        return False

    # Check for repetitive patterns (like navigation menus or page numbers)
    if text.count("\n") > (len(text) / 20):
        return False # Too many short lines

    return True


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Robust text chunking strategy.

    Tries to split by paragraphs first, then falls back to word count.
    Ensures structural integrity where possible.
    """
    if not text:
        return []

    # Try splitting by paragraph double-newlines
    paragraphs = re.split(r"\n\n+", text)

    final_chunks = []
    current_chunk_words: list[str] = []

    for para in paragraphs:
        para_words = para.split()
        if not para_words:
            continue

        # If adding this paragraph exceeds chunk size, and we already have words, emit current chunk
        if len(current_chunk_words) + len(para_words) > chunk_size and current_chunk_words:
            final_chunks.append(" ".join(current_chunk_words))
            # Keep overlap words from the end
            current_chunk_words = current_chunk_words[-overlap:] if overlap < len(current_chunk_words) else current_chunk_words

        # If the paragraph itself is larger than chunk size, split it by words
        if len(para_words) > chunk_size:
            # First, add what we have
            if current_chunk_words:
                final_chunks.append(" ".join(current_chunk_words))
                current_chunk_words = []

            # Then split the giant paragraph
            i = 0
            while i < len(para_words):
                chunk_slice = para_words[i : i + chunk_size]
                final_chunks.append(" ".join(chunk_slice))
                i += chunk_size - overlap
        else:
            current_chunk_words.extend(para_words)

    if current_chunk_words:
        final_chunks.append(" ".join(current_chunk_words))

    return [c for c in final_chunks if c.strip()]
