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

# Semaphore to cap concurrent OpenRouter calls from LightRAG (bypasses call_llm circuit breaker)
_LIGHTRAG_OPENROUTER_SEM = asyncio.Semaphore(5)

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
            llm_model = os.getenv("KITTY_LIGHTRAG_MODEL", "google/gemini-2.0-flash-001")

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

        # ─── LLM Function (OpenRouter direct via aiohttp) ────────────────────
        # Bypasses call_llm's circuit breaker, which is intended for real-time
        # user-facing conversation, not background ingestion parallelism.
        import aiohttp

        _openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

        async def openrouter_model_complete(prompt, system_prompt=None, history_messages=[], **kwargs) -> str:
            """Direct async OpenRouter call for LightRAG graph extraction.

            Uses a module-level semaphore to cap concurrency at 5, and retries
            up to 3 times with exponential backoff on HTTP 429.
            """
            # LightRAG sometimes passes system_prompt in kwargs
            sys_p = system_prompt or kwargs.get("system_prompt", "")

            # Combine history if present
            full_prompt = prompt
            if history_messages:
                hist_str = "\n".join([f"{m['role']}: {m['content']}" for m in history_messages])
                full_prompt = f"History:\n{hist_str}\n\nTask: {prompt}"

            messages = []
            if sys_p:
                messages.append({"role": "system", "content": sys_p})
            messages.append({"role": "user", "content": full_prompt})

            payload = {
                "model": llm_model,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", 2048),
                "temperature": kwargs.get("temperature", 0.1),
            }
            headers = {
                "Authorization": f"Bearer {_openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/kitty",
            }

            async with _LIGHTRAG_OPENROUTER_SEM:
                for attempt in range(3):
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                "https://openrouter.ai/api/v1/chat/completions",
                                json=payload,
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=120),
                            ) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    return data["choices"][0]["message"]["content"]
                                if resp.status == 429:
                                    backoff = 2 ** attempt
                                    logger.warning(
                                        f"OpenRouter rate limit (429) for LightRAG, "
                                        f"attempt {attempt + 1}/3, backing off {backoff}s"
                                    )
                                    await asyncio.sleep(backoff)
                                    continue
                                text = await resp.text()
                                raise RuntimeError(
                                    f"OpenRouter {resp.status} for LightRAG: {text[:200]}"
                                )
                    except RuntimeError:
                        raise
                    except Exception as e:
                        if attempt < 2:
                            backoff = 2 ** attempt
                            logger.warning(
                                f"OpenRouter request error for LightRAG (attempt {attempt + 1}/3): "
                                f"{e}, retrying in {backoff}s"
                            )
                            await asyncio.sleep(backoff)
                        else:
                            raise
                raise RuntimeError(
                    f"OpenRouter LightRAG call failed after 3 attempts (persistent 429)"
                )

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
