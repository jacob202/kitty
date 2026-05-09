"""ChromaDB knowledge base for Kitty Gateway."""
from __future__ import annotations
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kitty.knowledge")

KNOWLEDGE_DB_PATH = Path("/Users/jacobbrizinski/Projects/kitty/data/knowledge_db")
COLLECTION_NAME = "kitty_knowledge"
EMBED_MODEL = "nomic-embed-text"
OLLAMA_BASE = "http://localhost:11434"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


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


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed texts using nomic-embed-text via Ollama."""
    import requests
    embeddings = []
    for text in texts:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=30,
        )
        resp.raise_for_status()
        embeddings.append(resp.json()["embedding"])
    return embeddings


def ingest_file(file_path: str | Path, sensitivity: str = "low", source_label: Optional[str] = None) -> int:
    """Ingest a file into ChromaDB. Returns number of chunks stored."""
    from pathlib import Path as P
    path = P(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Extract text
    text = _extract_text(path)
    if not text.strip():
        logger.warning("No text extracted from %s", path)
        return 0

    # Chunk text
    chunks = _chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)

    # Check for existing chunks from this file (idempotent)
    collection = _get_collection()
    source = source_label or path.name
    existing = collection.get(where={"source": source})
    if existing["ids"]:
        logger.info("File %s already ingested (%d chunks), skipping", source, len(existing["ids"]))
        return 0

    # Embed and store
    embeddings = _embed(chunks)
    ids = [f"{source}__chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {"source": source, "file_path": str(path), "sensitivity": sensitivity, "chunk_index": i}
        for i in range(len(chunks))
    ]
    collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas)
    logger.info("Ingested %d chunks from %s", len(chunks), source)
    return len(chunks)


def search_knowledge(query: str, limit: int = 5, sensitivity_filter: Optional[str] = None) -> list[dict]:
    """Search ChromaDB for chunks relevant to query."""
    try:
        collection = _get_collection()
        query_embedding = _embed([query])[0]
        where = {"sensitivity": sensitivity_filter} if sensitivity_filter else None
        kwargs = {"query_embeddings": [query_embedding], "n_results": min(limit, max(1, collection.count()))}
        if where:
            kwargs["where"] = where
        results = collection.query(**kwargs)
        chunks = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            dist = results["distances"][0][i] if results["distances"] else 1.0
            chunks.append({"text": doc, "source": meta.get("source", "unknown"), "score": 1.0 - dist, "metadata": meta})
        return chunks
    except Exception as e:
        logger.warning("Knowledge search failed (non-fatal): %s", e)
        return []


def get_knowledge_block(query: str, limit: int = 5) -> str:
    """Return a formatted context block to inject into the system prompt."""
    chunks = search_knowledge(query, limit=limit)
    if not chunks:
        return ""
    lines = ["## Relevant knowledge from Kitty's knowledge base:"]
    seen_sources = set()
    for chunk in chunks:
        source = chunk["source"]
        lines.append(f"\n[Source: {source}]")
        lines.append(chunk["text"][:400])
        seen_sources.add(source)
    return "\n".join(lines)


def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix in {".txt", ".md", ".rst"}:
        return path.read_text(errors="ignore")
    else:
        # Try plain text for unknown types
        try:
            return path.read_text(errors="ignore")
        except Exception:
            return ""


def _extract_pdf(path: Path) -> str:
    """Extract text from PDF using PyMuPDF (primary) then pdfplumber (fallback)."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return ""


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks
