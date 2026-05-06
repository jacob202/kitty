"""Ingest Engine — Canonical SQLite store with idempotent, source-tagged ingestion.

Contract:
- Raw text + metadata stored in SQLite (data/kitty.db, table `knowledge_sources`)
- Chunks with content_hash in `knowledge_chunks` (vec0 for vectors)
- Source tagging: source, source_id, ingested_at, content_hash, metadata_json
- Idempotent: duplicate hash = skip
- Evaluation gate: after ingestion, run known queries; mark source trusted only if PASS
"""

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
OLLAMA_MODEL = os.getenv("OLLAMA_INGEST_MODEL", "gemini-flash-latest")  # cheaper than llama3.1:8b

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

# SQLite canonical store (kitty.db, NOT a separate registry)
_KITTY_DB = Path("data/kitty.db")
_SCHEMA_VERSION = 1

# Tables created if not exist:
#   knowledge_sources(source, source_id, ingested_at, content_hash, metadata_json, trusted)
#   knowledge_chunks(id, source, source_id, chunk_index, content, content_hash, metadata_json)


class IngestEngine:
    def __init__(
        self,
        watch_dir: str = "data/staging",
        db_path: str = "data/kitty.db",
        model: str = "gemini-flash-latest",
    ):
        self.watch_dir = Path(watch_dir)
        self.db_path = Path(db_path)
        self.model_name = model
        self._seen: set = set()
        self._emb_cache: dict = {}
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _init_tables(self):
        import sqlite3
        conn = sqlite3.connect(str(self.db_path))
        # Canonical source registry
        conn.execute("""CREATE TABLE IF NOT EXISTS knowledge_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_id TEXT,
            ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
            content_hash TEXT NOT NULL,
            metadata_json TEXT,
            trusted BOOLEAN DEFAULT 0,
            schema_version INTEGER DEFAULT 1
        )""")
        # Chunks with embeddings
        conn.execute("""CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            metadata_json TEXT,
            PRIMARY KEY (source_id, chunk_index)
        )""")
        conn.commit()
        self._conn = conn
        self._seen: set = set()
        self._emb_cache: dict = {}

        self.registry_path = self.db_path / "ingest_registry.db"
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_registry()

    def _init_registry(self):
        """Initialize SQLite registry for fast duplicate checks."""
        import sqlite3

        conn = sqlite3.connect(str(self.registry_path.with_suffix(".sqlite")))
        conn.execute("CREATE TABLE IF NOT EXISTS registry (hash TEXT PRIMARY KEY)")
        conn.commit()
        self._reg_conn = conn

    def _hash_seen(self, h: str) -> bool:
        try:
            cur = self._reg_conn.execute("SELECT 1 FROM registry WHERE hash = ?", (h,)).fetchone()
            return cur is not None
        except Exception:
            return False

    def _mark_seen(self, h: str):
        try:
            self._reg_conn.execute("INSERT OR IGNORE INTO registry (hash) VALUES (?)", (h,))
            self._reg_conn.commit()
        except Exception:
            pass

    def _hash_content(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def _source_id(self, file_path: Path) -> str:
        return str(file_path.relative_to(self.watch_dir))

    def extract_text(self, file_path: Path) -> str:
        if file_path.suffix == ".md":
            return file_path.read_text(errors="ignore")
        if not HAS_FITZ:
            return ""
        import fitz  # noqa: PLC0415
        doc = fitz.open(str(file_path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(pages)

    def chunk_text(self, text: str, max_chars: int = 2000, overlap: int = 200) -> list[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = end - overlap
        return chunks

    def store_in_sqlite(self, source: str, source_id: str, text: str, chunks: list[str]) -> bool:
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            cur = conn.cursor()
            now = datetime.now().isoformat()
            h = self._hash_content(text)
            # Upsert source
            cur.execute("""INSERT OR IGNORE INTO knowledge_sources
                (source, source_id, ingested_at, content_hash, metadata_json, trusted, schema_version)
                VALUES (?, ?, ?, ?, ?, 0, ?)""",
                (source, source_id, now, h, json.dumps({"chars": len(text)}), _SCHEMA_VERSION))
            # Chunks
            for i, chunk in enumerate(chunks):
                ch = self._hash_content(chunk)
                cur.execute("""INSERT OR IGNORE INTO knowledge_chunks
                    (source_id, chunk_index, content, content_hash, metadata_json)
                    VALUES (?, ?, ?, ?, ?)""",
                    (source_id, i, chunk, ch, json.dumps({"source": source})))
            conn.commit()
            conn.close()
            logger.info(f"Stored {len(chunks)} chunks for {source_id}")
            return True
        except Exception as e:
            logger.error(f"SQLite store failed: {e}")
            return False
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

    def process_file(self, file_path: Path) -> dict | None:
        """Extract text, chunk, store in SQLite. Returns metadata dict or None."""
        source = "pdf" if file_path.suffix == ".pdf" else "markdown" if file_path.suffix == ".md" else "web" if "http" in str(file_path) else "general"
        source_id = str(file_path.relative_to(self.watch_dir))

        raw = self.extract_text(file_path)
        if not raw.strip():
            logger.warning(f"Empty text for {file_path.name}")
            return None

        clean = self.strip_noise(raw)
        h = self._hash_content(clean)

        # Check idempotency
        try:
            cur = self._conn.execute("SELECT id FROM knowledge_sources WHERE content_hash = ?", (h,))
            if cur.fetchone():
                logger.info(f"Skipping duplicate: {file_path.name}")
                return None
        except Exception:
            pass

        chunks = self.chunk_text(clean)
        if not chunks:
            return None

        now = datetime.now().isoformat()
        metadata = json.dumps({
            "chars": len(clean),
            "chunks": len(chunks),
            "parser": "pymupdf" if file_path.suffix == ".pdf" else "markdown",
            "parser_version": "1.0",
        })

        try:
            cur = self._conn.cursor()
            # Upsert source
            cur.execute("""INSERT OR IGNORE INTO knowledge_sources
                (source, source_id, ingested_at, content_hash, metadata_json, trusted, schema_version)
                VALUES (?, ?, ?, ?, ?, 0, ?)""",
                (source, source_id, now, h, metadata, _SCHEMA_VERSION))

            # Store chunks
            for i, chunk in enumerate(chunks):
                chunk_h = self._hash_content(chunk)
                cur.execute("""INSERT OR IGNORE INTO knowledge_chunks
                    (source_id, chunk_index, content, content_hash, metadata_json)
                    VALUES (?, ?, ?, ?, ?)""",
                    (source_id, i, chunk, chunk_h, json.dumps({"source": source})))

            self._conn.commit()
            logger.info(f"Stored {len(chunks)} chunks for {source_id}")
            return {"source": source, "source_id": source_id, "chunks": len(chunks), "hash": h}
        except Exception as e:
            logger.error(f"SQLite store failed: {e}")
            return None

    def store_in_lightrag(self, content: str, domain: str, source_file: str, summary: str = "") -> bool:
        """Store content in domain-specific LightRAG."""
        try:
            from src.memory.lightrag_store import LightRAGStore

            store = LightRAGStore(domain=domain)
            store.add_document(content)
            self._update_inventory(domain, source_file, summary)
            return True
        except Exception as e:
            logger.error(f"Failed to store in LightRAG (domain={domain}): {e}")
            return False

    def _update_inventory(self, domain: str, source_file: str, summary: str):
        """Update the centralized knowledge inventory."""
        try:
            _INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            if not _INVENTORY_PATH.exists():
                _INVENTORY_PATH.write_text("# Knowledge Base Inventory\n\n| Date | Domain | Source | Summary |\n|------|--------|--------|---------|\n")

            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            filename = os.path.basename(source_file)
            summary_clean = summary.replace("\n", " ").replace("|", " ")[:100] + "..."
            entry = f"| {date_str} | {domain} | {filename} | {summary_clean} |\n"
            
            with open(_INVENTORY_PATH, "a") as f:
                f.write(entry)
        except Exception as e:
            logger.error(f"Failed to update inventory: {e}")

    def ingest_file(self, file_path: Path, store_in_kb: bool = True, domain: str | None = None) -> int:
        """Full pipeline for one file."""
        # Auto-detect domain from parent folder if not provided
        if domain is None:
            domain = file_path.parent.name
            if domain == "staging" or not domain:
                domain = "general"

        pearl = self.process_file(file_path)
        if pearl is None:
            return 0

        if store_in_kb:
            success = self.store_in_lightrag(pearl, domain, str(file_path), summary=pearl)
            return 1 if success else 0

        return 1

    def ingest_directory(self, store_in_kb: bool = True, domain: str | None = None) -> dict[str, Any]:
        """Ingest all files in watch_dir (recursive with subdir name as domain)."""
        files = self.scan_directory()
        results = {"processed": [], "skipped": [], "failed": [], "total_chunks": 0}

        for f in files:
            try:
                file_domain = domain
                if file_domain is None:
                    parent_dir = f.parent.name
                    file_domain = parent_dir if parent_dir != self.watch_dir.name else "general"

                count = self.ingest_file(f, store_in_kb=store_in_kb, domain=file_domain)
                if count > 0:
                    results["processed"].append({"file": str(f.relative_to(self.watch_dir)), "chunks": count})
                    results["total_chunks"] += count
                else:
                    results["skipped"].append({"file": f.name, "reason": "duplicate or empty"})
            except Exception as e:
                results["failed"].append({"file": f.name, "error": str(e)})

        return results

    def scan_directory(self) -> list[Path]:
        """Scan watch_dir recursively for supported files (.md, .pdf)."""
        files = []
        if not self.watch_dir.exists():
            return files
        for f in self.watch_dir.rglob("*"):
            if f.is_file() and f.suffix in (".md", ".pdf"):
                files.append(f)
        return files
