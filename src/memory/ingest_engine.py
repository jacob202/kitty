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

_INVENTORY_PATH = Path("data/knowledge_bases/INVENTORY.md")


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
        """Ingest all files in watch_dir."""
        files = self.scan_directory()
        results = {"processed": [], "skipped": [], "failed": [], "total_chunks": 0}

        for f in files:
            try:
                count = self.ingest_file(f, store_in_kb=store_in_kb, domain=domain)
                if count > 0:
                    results["processed"].append({"file": f.name, "chunks": count})
                    results["total_chunks"] += count
                else:
                    results["skipped"].append({"file": f.name, "reason": "duplicate or empty"})
            except Exception as e:
                results["failed"].append({"file": f.name, "error": str(e)})

        return results

    def scan_directory(self) -> list[Path]:
        """Scan watch_dir for supported files (.md, .pdf)."""
        files = []
        if not self.watch_dir.exists():
            return files
        for f in self.watch_dir.iterdir():
            if f.is_file() and f.suffix in (".md", ".pdf"):
                files.append(f)
        return files
