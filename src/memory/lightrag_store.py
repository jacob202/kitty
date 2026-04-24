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
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_WORKING_DIR = str(_PROJECT_ROOT / "data" / "lightrag")

# Global event loop and thread shared by all LightRAGStore instances
_GLOBAL_LOOP = None
_GLOBAL_THREAD = None
_GLOBAL_LOCK = threading.Lock()

# Load environment variables
load_dotenv(_PROJECT_ROOT / ".env")


def _get_global_loop():
    """Ensure a global asyncio loop is running in a background thread."""
    global _GLOBAL_LOOP, _GLOBAL_THREAD
    with _GLOBAL_LOCK:
        if _GLOBAL_LOOP is None:
            _GLOBAL_LOOP = asyncio.new_event_loop()
            _GLOBAL_THREAD = threading.Thread(
                target=_run_global_loop, daemon=True, name="lightrag-global-loop"
            )
            _GLOBAL_THREAD.start()
    return _GLOBAL_LOOP


def _run_global_loop():
    """Background thread target."""
    asyncio.set_event_loop(_GLOBAL_LOOP)
    _GLOBAL_LOOP.run_forever()


class LightRAGStore:
    """
    Synchronous facade over LightRAG's async API.

    Uses a shared global asyncio event loop in a daemon thread so LightRAG's
    internal worker coroutines always have a live loop to run in.

    Supports domain isolation by using separate working directories.

    Now uses OpenRouter (via call_llm) for extraction instead of Ollama.
    """

    def __init__(
        self,
        domain: str | None = None,
        working_dir: str | None = None,
        llm_model: str | None = None,
        embed_model: str = "nomic-embed-text",
    ):
        # 1. Determine working directory
        if working_dir:
            self.working_dir = working_dir
        elif domain:
            self.working_dir = str(_PROJECT_ROOT / "data" / "lightrag" / domain)
        else:
            self.working_dir = _DEFAULT_WORKING_DIR

        # 2. Determine LLM model (prefer OpenRouter free tier for extraction)
        if llm_model is None:
            llm_model = os.getenv("KITTY_LIGHTRAG_MODEL", "google/gemini-2.0-flash-exp:free")

        # 3. Get shared loop
        self._loop = _get_global_loop()

        # 4. Initialize LightRAG inside the persistent loop
        future = asyncio.run_coroutine_threadsafe(
            self._init(self.working_dir, llm_model, embed_model), self._loop
        )
        future.result(timeout=60)  # wait up to 60s for storage init

    async def _init(self, working_dir, llm_model, embed_model):
        from lightrag import LightRAG
        from lightrag.utils import EmbeddingFunc

        Path(working_dir).mkdir(parents=True, exist_ok=True)

        # ─── LLM Function (OpenRouter via call_llm) ───────────────────────────
        from src.space_kitty.llm_client import call_llm

        async def openrouter_model_complete(prompt, system_prompt=None, history_messages=[], **kwargs) -> str:
            """Adapter for call_llm to fit LightRAG's expectations."""
            # LightRAG sometimes passes system_prompt in kwargs
            sys_p = system_prompt or kwargs.get("system_prompt", "")
            
            # Combine history if present (LightRAG usually handles its own history management)
            full_prompt = prompt
            if history_messages:
                hist_str = "\n".join([f"{m['role']}: {m['content']}" for m in history_messages])
                full_prompt = f"History:\n{hist_str}\n\nTask: {prompt}"

            # call_llm is synchronous, but we are in an async context here.
            # We run it in the loop's default executor.
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: call_llm(
                    prompt=full_prompt,
                    system_prompt=sys_p,
                    model=llm_model,
                    max_tokens=kwargs.get("max_tokens", 2048),
                    temperature=kwargs.get("temperature", 0.1) # Low temp for extraction
                )
            )
            
            # Strip offline mode markers if they appear
            if result.startswith("[offline mode"):
                raise RuntimeError(f"LightRAG LLM call failed: {result}")
                
            return result

        # ─── Embedding Function (Ollama nomic-embed-text) ─────────────────────
        # We keep Ollama for embeddings as it's local and fast.
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        async def ollama_embed(texts):
            """Ollama embedding using nomic-embed-text with batching."""
            import json
            import urllib.request
            import numpy as np

            if isinstance(texts, list):
                batch_size = 100
                all_results = []
                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]
                    results = []
                    for text in batch:
                        try:
                            req = urllib.request.Request(
                                f"{ollama_base_url}/api/embeddings",
                                data=json.dumps({"model": embed_model, "prompt": text}).encode(),
                                headers={"Content-Type": "application/json"},
                            )
                            with urllib.request.urlopen(req, timeout=30) as resp:
                                results.append(json.loads(resp.read().decode())["embedding"])
                        except Exception:
                            results.append([0.0] * 768)
                    all_results.extend(results)
                return np.array(all_results)
            else:
                req = urllib.request.Request(
                    f"{ollama_base_url}/api/embeddings",
                    data=json.dumps({"model": embed_model, "prompt": texts}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return np.array([json.loads(resp.read().decode())["embedding"]])

        embedding_func = EmbeddingFunc(
            embedding_dim=768,
            max_token_size=2048,
            func=ollama_embed,
        )

        # ─── LightRAG Core ────────────────────────────────────────────────────
        self._rag = LightRAG(
            working_dir=working_dir,
            llm_model_func=openrouter_model_complete,
            llm_model_name=llm_model,
            embedding_func=embedding_func,
        )
        await self._rag.initialize_storages()

    def add_document(self, text: str, metadata: dict = None) -> None:
        """Insert text. Blocks until ingestion completes."""
        future = asyncio.run_coroutine_threadsafe(self._rag.ainsert(text), self._loop)
        future.result(timeout=600)  # 10-minute ceiling per document

    def search(self, query: str, top_k: int = 5) -> str:
        """Vector search over ingested documents using 'naive' mode."""
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
        """Search with hierarchical context (L0/L1/L2 tiers)."""
        from src.memory.context_hierarchy import integrate_with_lightrag

        hierarchy = integrate_with_lightrag(self)
        return hierarchy.query_tiered(query, tier=tier, top_k=top_k)

    def close(self) -> None:
        """Flush pending writes."""
        try:
            future = asyncio.run_coroutine_threadsafe(self._rag.finalize_storages(), self._loop)
            future.result(timeout=30)
        except Exception as e:
            from src.core.exceptions import handle_exception

            handle_exception(e, context="lightrag_store.close", silent=True)
