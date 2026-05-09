"""ChromaDB knowledge base for Kitty Gateway."""
from __future__ import annotations
import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kitty.knowledge")

KNOWLEDGE_DB_PATH = Path("/Users/jacobbrizinski/Projects/kitty/data/knowledge_db")
COLLECTION_NAME = "kitty_knowledge"
EMBED_MODEL = "nomic-embed-text"
OLLAMA_BASE = "http://localhost:11434"

# Chunk sizes tuned per document type
_CHUNK_PROFILES = {
    "service_manual":  {"size": 256,  "overlap": 32},   # small — preserve numbered steps
    "book":            {"size": 768,  "overlap": 96},   # large — prose flows across paragraphs
    "session_log":     {"size": 384,  "overlap": 48},   # medium — conversation turns
    "health_record":   {"size": 256,  "overlap": 32},   # small — clinical data is dense
    "general":         {"size": 512,  "overlap": 64},   # default
}

# Signals used to detect document type from filename + first 500 chars of text
_MANUAL_NAME_SIGNALS = {"manual", "service", "repair", "workshop", "haynes", "chilton",
                        "maintenance", "overhaul", "wiring", "schematic", "diagram",
                        "datasheet", "spec", "specification"}
_MANUAL_TEXT_SIGNALS = re.compile(
    r"(step \d+|torque|ft.?lb|nm\b|part\s+no|oem|exploded\s+view|"
    r"remove\s+and\s+replace|disconnect|reconnect|tighten|loosen|"
    r"warning:|caution:|note:|procedure|specification)", re.I
)
_HEALTH_NAME_SIGNALS = {"blood", "lab", "result", "medical", "health", "rx",
                        "prescription", "biopsy", "pathology", "ecg", "ekg"}
_BOOK_NAME_SIGNALS = {"textbook", "book", "chapter", "edition", "introduction",
                      "fundamentals", "principles", "guide", "handbook"}
_BOOK_TEXT_SIGNALS = re.compile(r"(chapter \d+|table of contents|bibliography|references|abstract)", re.I)
_SESSION_EXTENSIONS = {".jsonl", ".json"}


def detect_doc_type(path: Path, text_preview: str = "") -> str:
    """Infer document type from filename and content preview."""
    name_lower = path.stem.lower()
    name_words = set(re.split(r"[\s_\-\.]+", name_lower))

    if path.suffix.lower() in _SESSION_EXTENSIONS:
        return "session_log"
    if name_words & _HEALTH_NAME_SIGNALS:
        return "health_record"
    if name_words & _MANUAL_NAME_SIGNALS:
        return "service_manual"
    if name_words & _BOOK_NAME_SIGNALS:
        return "book"
    # Content-based fallback for PDFs with generic names
    if text_preview:
        if _MANUAL_TEXT_SIGNALS.search(text_preview[:1000]):
            return "service_manual"
        if _BOOK_TEXT_SIGNALS.search(text_preview[:1000]):
            return "book"
    return "general"


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


def ingest_file(
    file_path: str | Path,
    sensitivity: str = "low",
    source_label: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> int:
    """Ingest a file into ChromaDB. Returns number of chunks stored."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    text = _extract_text(path)
    if not text.strip():
        logger.warning("No text extracted from %s", path)
        return 0

    resolved_type = doc_type or detect_doc_type(path, text[:1000])
    profile = _CHUNK_PROFILES.get(resolved_type, _CHUNK_PROFILES["general"])
    chunks = _chunk_text(text, profile["size"], profile["overlap"])

    collection = _get_collection()
    source = source_label or path.name

    existing = collection.get(where={"source": source})
    if existing["ids"]:
        logger.info("Already ingested %s (%d chunks), skipping", source, len(existing["ids"]))
        return 0

    embeddings = _embed(chunks)
    ids = [f"{source}__chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "source": source,
            "file_path": str(path),
            "sensitivity": sensitivity,
            "doc_type": resolved_type,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]
    collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas)
    logger.info("Ingested %d chunks from %s (type=%s)", len(chunks), source, resolved_type)
    return len(chunks)


def search_knowledge(query: str, limit: int = 5, sensitivity_filter: Optional[str] = None) -> list[dict]:
    """Search ChromaDB for chunks relevant to query."""
    try:
        collection = _get_collection()
        query_embedding = _embed([query])[0]
        where = {"sensitivity": sensitivity_filter} if sensitivity_filter else None
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(limit, max(1, collection.count())),
        }
        if where:
            kwargs["where"] = where
        results = collection.query(**kwargs)
        chunks = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            dist = results["distances"][0][i] if results["distances"] else 1.0
            chunks.append({
                "text": doc,
                "source": meta.get("source", "unknown"),
                "doc_type": meta.get("doc_type", "general"),
                "score": 1.0 - dist,
                "metadata": meta,
            })
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
    for chunk in chunks:
        source = chunk["source"]
        doc_type = chunk.get("doc_type", "general")
        label = f"[Source: {source}" + (f" | type: {doc_type}]" if doc_type != "general" else "]")
        lines.append(f"\n{label}")
        lines.append(chunk["text"][:400])
    return "\n".join(lines)


def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix == ".jsonl":
        return _extract_jsonl_session(path)
    elif suffix == ".json":
        try:
            first_char = path.read_text(errors="ignore").lstrip()[:1]
        except Exception:
            first_char = ""
        if first_char == "[":
            return _extract_chatgpt_json(path)
        return _extract_jsonl_session(path)
    elif suffix in {".txt", ".md", ".rst"}:
        return path.read_text(errors="ignore")
    else:
        try:
            return path.read_text(errors="ignore")
        except Exception:
            return ""


def _extract_pdf(path: Path) -> str:
    """PDF extraction via Phase 9 pipeline (LlamaParse → PyMuPDF → pdfplumber + vision)."""
    from gateway.pdf_pipeline import extract_pdf_enhanced
    chunks = extract_pdf_enhanced(path)
    return "\n\n".join(chunk.combined_text() for chunk in chunks)


def _extract_jsonl_session(path: Path) -> str:
    """Extract human-readable text from Claude Code .jsonl session transcripts."""
    lines = []
    try:
        for raw in path.read_text(errors="ignore").splitlines():
            if not raw.strip():
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            role = obj.get("role", "")
            # Claude Code transcript format: {role, content} or nested message
            msg = obj.get("message", obj)
            content = msg.get("content", "")
            if isinstance(content, list):
                # Multi-part content blocks
                parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                content = " ".join(parts)
            if role and content:
                lines.append(f"{role.upper()}: {content[:800]}")
    except Exception as e:
        logger.warning("JSONL parse failed for %s: %s", path.name, e)
    return "\n\n".join(lines)


def _extract_chatgpt_json(path: Path) -> str:
    """Extract text from OpenAI ChatGPT export JSON (list of conversations)."""
    try:
        data = json.loads(path.read_text(errors="ignore"))
    except Exception as e:
        logger.warning("ChatGPT JSON parse failed for %s: %s", path.name, e)
        return ""
    if not isinstance(data, list):
        return ""
    blocks = []
    for conv in data:
        title = conv.get("title", "Untitled")
        mapping = conv.get("mapping", {})
        messages = []
        for node in mapping.values():
            msg = node.get("message")
            if not msg:
                continue
            role = msg.get("author", {}).get("role", "")
            if role not in {"user", "assistant"}:
                continue
            content = msg.get("content", {})
            parts = content.get("parts", []) if isinstance(content, dict) else []
            text = " ".join(str(p) for p in parts if isinstance(p, str) and p.strip())
            if not text:
                continue
            create_time = msg.get("create_time") or 0
            messages.append((create_time, role.upper(), text[:600]))
        messages.sort(key=lambda x: x[0])
        if messages:
            lines = [f"CONVERSATION: {title}"]
            lines += [f"{role}: {text}" for _, role, text in messages]
            blocks.append("\n".join(lines))
    return "\n\n---\n\n".join(blocks)


def _extract_sqlite_journal(path: Path) -> str:
    """Extract role/content pairs from a SQLite journal table."""
    import sqlite3
    try:
        conn = sqlite3.connect(str(path))
        rows = conn.execute(
            "SELECT role, content FROM journal ORDER BY timestamp, id"
        ).fetchall()
        conn.close()
        lines = [f"{role.upper()}: {content[:600]}" for role, content in rows if content]
        return "\n\n".join(lines)
    except Exception as e:
        logger.warning("SQLite journal extract failed for %s: %s", path.name, e)
        return ""


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i: i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks
