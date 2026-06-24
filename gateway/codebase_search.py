"""Codebase Search — Semantic code search using ChromaDB.

This module implements semantic search across the codebase, similar to
Antigravity's codebase_search tool.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Dict, List

from gateway.paths import DATA_DIR

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    from sentence_transformers import SentenceTransformer

    CHROMA_AVAILABLE = True
except Exception as exc:
    CHROMA_AVAILABLE = False
    CHROMA_IMPORT_ERROR = exc
else:
    CHROMA_IMPORT_ERROR = None

logger = logging.getLogger("kitty.codebase_search")

KITTY_DIR = DATA_DIR


class CodebaseSearch:
    """Semantic code search across the project — like Antigravity's codebase_search."""

    VALID_EXTENSIONS = frozenset(
        {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".go",
            ".rs",
            ".java",
            ".rb",
            ".c",
            ".cpp",
            ".h",
            ".sh",
            ".md",
            ".yaml",
            ".yml",
            ".json",
            ".html",
            ".css",
        }
    )

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.chroma_dir = KITTY_DIR / "codebase_index"
        self.indexed_files: Dict[str, str] = {}  # path → hash

        if CHROMA_AVAILABLE:
            self.client = chromadb.Client(
                ChromaSettings(persist_directory=str(self.chroma_dir), anonymized_telemetry=False)
            )
            self.collection = self.client.get_or_create_collection("codebase")
            self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        else:
            self.client = None
            self.collection = None
            self.encoder = None
            logger.warning(
                "ChromaDB not available - codebase search disabled: %s", CHROMA_IMPORT_ERROR
            )

    def index_file(self, filepath: str) -> bool:
        """Index a single file for semantic search."""
        if not CHROMA_AVAILABLE:
            return False

        full_path = self.project_root / filepath
        if not full_path.exists() or full_path.suffix not in self.VALID_EXTENSIONS:
            return False

        try:
            content = full_path.read_text(errors="ignore")
        except Exception as e:
            logger.warning("Could not read %s: %s", filepath, e)
            return False

        file_hash = hashlib.md5(content.encode()).hexdigest()
        if filepath in self.indexed_files and self.indexed_files[filepath] == file_hash:
            return True  # Already indexed and unchanged

        # Chunk by function/class boundaries (simple: split by double newline)
        chunks = content.split("\n\n")
        indexed_count = 0
        for i, chunk in enumerate(chunks):
            if len(chunk.strip()) < 20:
                continue

            chunk_id = f"{filepath}:{i}"
            try:
                emb = self.encoder.encode([chunk])[0].tolist()
                self.collection.upsert(
                    documents=[chunk],
                    embeddings=[emb],
                    ids=[chunk_id],
                    metadatas=[{"source": filepath, "chunk": i}],
                )
                indexed_count += 1
            except Exception as e:
                logger.warning("Could not index chunk from %s: %s", filepath, e)

        self.indexed_files[filepath] = file_hash
        logger.info("Indexed %s: %d chunks", filepath, indexed_count)
        return True

    def index_project(self, max_files: int = 200) -> int:
        """Index the entire project (up to max_files)."""
        if not CHROMA_AVAILABLE:
            logger.warning("Cannot index - ChromaDB not available")
            return 0

        files = list(self.project_root.rglob("*"))
        files = [f for f in files if f.is_file() and f.suffix in self.VALID_EXTENSIONS]
        files = files[:max_files]

        indexed = 0
        for fp in files:
            rel = str(fp.relative_to(self.project_root))
            try:
                if self.index_file(rel):
                    indexed += 1
            except Exception as e:
                logger.warning("Could not index %s: %s", rel, e)

        logger.info("Indexed %d/%d files for semantic search.", indexed, len(files))
        return indexed

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """Semantic search across indexed code."""
        if not CHROMA_AVAILABLE:
            return []

        try:
            q_emb = self.encoder.encode([query])[0].tolist()
            results = self.collection.query(query_embeddings=[q_emb], n_results=top_k)

            out = []
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]

            for doc, meta in zip(docs, metas):
                out.append(
                    {
                        "source": meta.get("source", "unknown"),
                        "content": doc[:500],
                        "chunk": meta.get("chunk", 0),
                    }
                )
            return out
        except Exception as e:
            logger.error("Search failed: %s", e)
            return []

    def is_available(self) -> bool:
        """Check if semantic search is available."""
        return CHROMA_AVAILABLE


# Global instance
codebase_search = CodebaseSearch()
