"""
Sync wrapper around async LightRAG for use in the existing sync Supervisor.
Data directory: data/lightrag/ (absolute, derived from project root).

Uses a dedicated background thread with a persistent event loop — the correct
pattern for calling async code from synchronous code. This avoids the
"event loop closed" errors that occur when using run_until_complete() directly.
"""

import asyncio
import logging
import os
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_WORKING_DIR = str(_PROJECT_ROOT / "data" / "lightrag")

# Load environment variables
load_dotenv(_PROJECT_ROOT / ".env")

# Ensure local lightrag install (tools/lightrag/) is importable regardless of venv
_lightrag_src = str(_PROJECT_ROOT / "tools" / "lightrag")
if _lightrag_src not in sys.path:
    sys.path.insert(0, _lightrag_src)


class LightRAGStore:
    """
    Synchronous facade over LightRAG's async API.

    Runs a persistent asyncio event loop in a daemon thread so LightRAG's
    internal worker coroutines always have a live loop to run in.

    Usage:
        store = LightRAGStore()
        store.add_document("The capacitor C47 is in the power supply section.")
        answer = store.search("What capacitors are in the power supply?")
        store.close()
    """

    def __init__(
        self,
        working_dir: str = _DEFAULT_WORKING_DIR,
        llm_model: str | None = None,
        embed_model: str = "nomic-embed-text",
    ):
        if llm_model is None:
            try:
                import json

                _cfg = json.loads(
                    (
                        _PROJECT_ROOT / "data" / "config" / "kitty_config.json"
                    ).read_text()
                )
                llm_model = _cfg.get("lightrag", {}).get("llm_model", "llama3.2:3b")
            except Exception:
                llm_model = "llama3.2:3b"

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="lightrag-loop"
        )
        self._thread.start()

        # Initialize LightRAG inside the persistent loop
        future = asyncio.run_coroutine_threadsafe(
            self._init(working_dir, llm_model, embed_model), self._loop
        )
        future.result(timeout=60)  # wait up to 60s for storage init

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _init(self, working_dir, llm_model, embed_model):
        import requests
        from lightrag import LightRAG
        from lightrag.llm.ollama import ollama_model_complete
        from lightrag.utils import EmbeddingFunc

        Path(working_dir).mkdir(parents=True, exist_ok=True)

        # Check if Ollama is running
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_available = False

        try:
            resp = requests.get(f"{ollama_base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                ollama_available = True
                # Check if nomic-embed-text is available
                models = resp.json().get("models", [])
                has_nomic = any("nomic-embed-text" in m.get("name", "") for m in models)
                if not has_nomic:
                    logger.info("Pulling nomic-embed-text (first time setup)...")
                    requests.post(
                        f"{ollama_base_url}/api/pull",
                        json={"name": "nomic-embed-text"},
                        timeout=300,
                    )
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")

        if ollama_available:

            async def ollama_embed(texts):
                """Ollama embedding using nomic-embed-text with batching."""
                import json
                import urllib.request

                import numpy as np

                if isinstance(texts, list):
                    batch_size = 100
                    all_results = []
                    for i in range(0, len(texts), batch_size):
                        batch = texts[i:i+batch_size]
                        results = []
                        for text in batch:
                            try:
                                req = urllib.request.Request(
                                    f"{ollama_base_url}/api/embeddings",
                                    data=json.dumps(
                                        {"model": "nomic-embed-text", "prompt": text}
                                    ).encode(),
                                    headers={"Content-Type": "application/json"},
                                )
                                with urllib.request.urlopen(req, timeout=30) as resp:
                                    results.append(
                                        json.loads(resp.read().decode())["embedding"]
                                    )
                            except Exception:
                                results.append([0.0] * 768)
                        all_results.extend(results)
                    return np.array(all_results)
                else:
                    req = urllib.request.Request(
                        f"{ollama_base_url}/api/embeddings",
                        data=json.dumps(
                            {"model": "nomic-embed-text", "prompt": texts}
                        ).encode(),
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        return np.array([json.loads(resp.read().decode())["embedding"]])

            logger.info("Using Ollama embeddings (nomic-embed-text)")
            embedding_func = EmbeddingFunc(
                embedding_dim=768,
                max_token_size=2048,
                func=ollama_embed,
            )
        else:
            # Fallback: use simple hash-based embeddings
            logger.warning("Using fallback embeddings (no Ollama)")

            def fallback_embed(texts):
                """Deterministic fallback embedding using multiple hash rounds for variance across dimensions."""
                import hashlib
                import struct

                import numpy as np

                def _text_to_vector(text: str) -> list:
                    encoded = text.encode("utf-8")
                    vec = []
                    for i in range(768):
                        h = hashlib.sha256(encoded + struct.pack("<I", i)).digest()
                        val = int.from_bytes(h[:4], "little") / (2**32) - 0.5
                        vec.append(val)
                    return vec

                if isinstance(texts, list):
                    return np.array([_text_to_vector(t) for t in texts])
                else:
                    return np.array([_text_to_vector(texts)])

            embedding_func = EmbeddingFunc(
                embedding_dim=768,
                max_token_size=2048,
                func=fallback_embed,
            )

        self._rag = LightRAG(
            working_dir=working_dir,
            llm_model_func=ollama_model_complete,
            llm_model_name=llm_model,
            llm_model_kwargs={"options": {"num_ctx": 32768}},
            embedding_func=embedding_func,
        )
        await self._rag.initialize_storages()

    def add_document(self, text: str, metadata: dict = None) -> None:
        """Insert text. Blocks until ingestion completes (can be slow — Ollama LLM extracts entities)."""
        future = asyncio.run_coroutine_threadsafe(self._rag.ainsert(text), self._loop)
        future.result(timeout=600)  # 10-minute ceiling per document

    def search(self, query: str, top_k: int = 5) -> str:
        """
        Vector search over ingested documents.
        Uses 'naive' mode (embedding similarity only) so it works even when
        LLM entity extraction times out. Switch to 'hybrid' once a faster
        LLM model (qwen2.5:7b or better) is configured.
        """
        from lightrag import QueryParam

        try:
            future = asyncio.run_coroutine_threadsafe(
                self._rag.aquery(query, param=QueryParam(mode="naive", top_k=top_k)),
                self._loop,
            )
            return future.result(timeout=60)
        except Exception as e:
            return f"[LightRAG search error: {e}]"

    def search_tiered(self, query: str, tier: str = "all", top_k: int = 5):
        """
        Search with hierarchical context (L0/L1/L2 tiers).

        Wraps search() with ContextHierarchy for tiered retrieval.
        - L0: abstract (~50 tokens) -- fast
        - L1: overview (~500 tokens) -- moderate
        - L2: detail (full) -- on demand

        Args:
            query: search query
            tier: 'l0', 'l1', 'l2', or 'all'
            top_k: number of documents

        Returns:
            HierarchyQueryResult from ContextHierarchy.query_tiered()
        """
        from src.memory.context_hierarchy import integrate_with_lightrag

        hierarchy = integrate_with_lightrag(self)
        return hierarchy.query_tiered(query, tier=tier, top_k=top_k)

    def close(self) -> None:
        """Flush pending writes and stop the background event loop."""
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._rag.finalize_storages(), self._loop
            )
            future.result(timeout=30)
        except Exception as e:
            from src.core.exceptions import handle_exception
            handle_exception(e, context="lightrag_store.close", silent=True)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=10)
        self._loop.close()
