"""Ingest Engine — High-fidelity technical extraction via Ollama."""

import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_INGEST_MODEL", "llama3.1:8b")

try:
    import fitz  # PyMuPDF

    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

logger = logging.getLogger(__name__)

NOISE_PATTERNS = [
    r"^\s*\d+\s*$",  # bare page numbers
    r"^Page \d+ of \d+",  # "Page 3 of 45"
    r"^[-=]{3,}$",  # divider lines
    r"^\s*(www\.|http)",  # URLs on their own line
    r"Forum post #\d+",  # forum garbage
]


class IngestEngine:
    def __init__(
        self,
        watch_dir: str = "data/staging",
        db_path: str = "data/lightrag",
        model: str = "gemini-flash-latest",
    ):
        self.watch_dir = Path(watch_dir)
        self.db_path = Path(db_path)
        self.model_name = model
        self._seen: set = set()
        self._emb_cache: dict = {}

        self.registry_path = self.db_path / "ingest_registry.db"
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_registry()

    def _init_registry(self):
        """Initialize SQLite registry for fast duplicate checks."""
        import sqlite3

        conn = sqlite3.connect(str(self.registry_path.with_suffix(".sqlite")))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS registry (hash TEXT PRIMARY KEY)"
        )
        conn.commit()
        self._reg_conn = conn

    def _hash_seen(self, h: str) -> bool:

        try:
            cur = self._reg_conn.execute(
                "SELECT 1 FROM registry WHERE hash = ?", (h,)
            ).fetchone()
            return cur is not None
        except Exception:
            return False

    def _mark_seen(self, h: str):
        try:
            self._reg_conn.execute("INSERT OR IGNORE INTO registry (hash) VALUES (?)", (h,))
            self._reg_conn.commit()
        except Exception:
            pass

    def extract_text(self, file_path: Path) -> str:
        if file_path.suffix == ".md":
            return file_path.read_text(errors="ignore")
        if not HAS_FITZ:
            return ""
        import fitz as _fitz  # noqa: PLC0415

        doc = _fitz.open(str(file_path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(pages)

    def strip_noise(self, text: str) -> str:
        lines = text.splitlines()
        clean = []
        for line in lines:
            if not any(re.match(p, line.strip()) for p in NOISE_PATTERNS):
                clean.append(line.strip())
        return "\n".join(clean)

    def process_file(self, file_path: Path) -> str | None:
        raw = self.extract_text(file_path)
        clean = self.strip_noise(raw)

        h = hashlib.sha256(clean.encode()).hexdigest()
        if self._hash_seen(h):
            return None

        logger.info(f"Processing: {file_path.name}")

        prompt = f"""Extract the key facts, context, and actionable information from this document.
Write a dense summary (3-8 sentences) that preserves all specific details: names, numbers, models, diagnoses, decisions, and next steps.
Do not add commentary. Just compress the document into its essential facts.

DOCUMENT:
{clean[:5000]}"""

        try:
            from src.space_kitty.llm_client import call_llm

            pearl = call_llm(
                prompt=prompt,
                system_prompt="You are a knowledge extraction assistant. Return only the compressed fact summary, no preamble.",
                max_tokens=512,
                temperature=0.3,
                model=self.model_name if self.model_name != "gemini-flash-latest" else None,
            )

            # Don't store offline-mode failures in the registry or KB
            if not pearl or pearl.strip().startswith("[offline mode]"):
                logger.warning(f"Skipping registry write — LLM returned offline/empty for {file_path.name}")
                return None

            self._mark_seen(h)

            return pearl
        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            return None

    def embed_chunks(self, chunks: list[str]) -> list[list[float]]:
        """Embed chunks using Ollama with batching and caching."""
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        if not chunks:
            return []

        embeddings: list[list[float]] = []
        uncached_chunks: list[str] = []
        uncached_indices: list[int] = []

        for i, chunk in enumerate(chunks):
            h = hashlib.sha256(chunk.encode()).hexdigest()
            if h in self._emb_cache:
                embeddings.append(self._emb_cache[h])
            else:
                uncached_chunks.append(chunk)
                uncached_indices.append(i)

        if not uncached_chunks:
            return embeddings

        try:
            payload = json.dumps({
                "model": "nomic-embed-text",
                "input": uncached_chunks,
            }).encode()
            req = urllib.request.Request(
                f"{ollama_base_url}/api/embed",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
                batch_embeddings = result.get("embeddings", [])

            for idx, emb in zip(uncached_indices, batch_embeddings):
                h = hashlib.sha256(chunks[idx].encode()).hexdigest()
                self._emb_cache[h] = emb
                embeddings.append(emb)
        except Exception as e:
            logger.warning(f"Ollama batch embedding failed: {e}; using deterministic fallback")
            for idx in uncached_indices:
                chunk = chunks[idx]
                h = hashlib.sha256(chunk.encode()).hexdigest()
                emb = []
                for i in range(0, min(len(h), 768 * 2), 4):
                    if len(emb) >= 768:
                        break
                    val = float(int(h[i : i + 4], 16)) / (16**4)
                    emb.append(val * 2 - 1)
                emb = emb[:768] if len(emb) >= 768 else emb + [0.0] * (768 - len(emb))
                self._emb_cache[h] = emb
                embeddings.append(emb)

        return embeddings

    def dedup_check(self, text: str) -> str | None:
        """Check if text is a duplicate. Returns text if new, None if duplicate."""
        h = hashlib.sha256(text.encode()).hexdigest()
        if self._hash_seen(h):
            return None
        return text

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            if end == len(words):
                break
            start = end - overlap
        return chunks

    def scan_directory(self) -> list[Path]:
        """Scan watch_dir for supported files (.md, .pdf)."""
        files = []
        if not self.watch_dir.exists():
            return files
        for f in self.watch_dir.iterdir():
            if f.is_file() and f.suffix in (".md", ".pdf"):
                files.append(f)
        return files

    def store_embeddings(self, chunks: list[str], source_file: str = None) -> int:
        """Store chunks in LightRAGStore for specialist KB queries.

        Args:
            chunks: Text chunks to store
            source_file: Optional source file path for metadata

        Returns:
            Number of chunks stored
        """
        try:
            from src.memory.kitty_memory_enhanced import KittyMemoryEnhanced

            mem = KittyMemoryEnhanced()
            if source_file and Path(source_file).exists():
                ids = mem.ingest_document(source_file)
                logger.info(f"Stored {len(ids)} chunks in ChromaDB from {source_file}")
                return len(ids)
            # fallback: store synthesized text chunks directly
            for i, chunk in enumerate(chunks):
                chunk_id = hashlib.md5(f"{source_file}{chunk}{i}".encode()).hexdigest()
                mem.documents.upsert(
                    documents=[chunk],
                    ids=[chunk_id],
                    metadatas=[{"source": source_file or "ingest", "timestamp": datetime.now().isoformat()}],
                )
            logger.info(f"Stored {len(chunks)} chunks in ChromaDB")
            return len(chunks)
        except Exception as e:
            logger.error(f"Failed to store in ChromaDB: {e}")
            return 0

    def ingest_file(self, file_path: Path, store_in_kb: bool = True) -> int:
        """Full pipeline for one file. Returns chunk count or 0 if duplicate.

        Args:
            file_path: Path to file to ingest
            store_in_kb: If True, store chunks in LightRAG for specialist queries

        Returns:
            Number of chunks stored (1 for synthesized, or actual chunk count if storing raw)
        """
        pearl = self.process_file(file_path)
        if pearl is None:
            return 0

        if store_in_kb:
            # Store the synthesized content as a chunk for KB retrieval
            chunks = [pearl]
            return self.store_embeddings(chunks, source_file=str(file_path))

        return 1

    def ingest_directory(self, store_in_kb: bool = True) -> dict[str, Any]:
        """Ingest all files in watch_dir. Returns detailed stats."""
        files = self.scan_directory()
        results = {
            "processed": [],
            "skipped": [],
            "failed": [],
            "total_chunks": 0
        }

        for f in files:
            try:
                count = self.ingest_file(f, store_in_kb=store_in_kb)
                if count > 0:
                    results["processed"].append({"file": f.name, "chunks": count})
                    results["total_chunks"] += count
                else:
                    results["skipped"].append({"file": f.name, "reason": "duplicate or empty"})
            except Exception as e:
                results["failed"].append({"file": f.name, "error": str(e)})

        return results
