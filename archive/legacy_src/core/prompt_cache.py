"""
Prompt Caching Infrastructure for Kitty.

Implements provider-native prompt caching and semantic response caching
to reduce token costs by 50-90% on repeated calls.

Based on research: docs/optimizer/token-optimization-research-2026-05-06.md
"""

import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Minimum tokens required for Anthropic cache control to activate
ANTHROPIC_MIN_CACHE_TOKENS = 1024

# Default TTL for cached responses (1 hour)
DEFAULT_CACHE_TTL_SECONDS = 3600

# Default max cache size (1000 entries)
DEFAULT_MAX_CACHE_SIZE = 1000


class PromptCache:
    """
    Provider-native prompt caching abstraction.

    Supports:
    - Anthropic Claude: Explicit cache_control breakpoints
    - OpenAI: Automatic caching (no explicit markers needed)
    - Google Gemini: Implicit + explicit cache objects
    """

    def __init__(self, provider: str = "openai"):
        self.provider = provider.lower()
        self.cache_hits = 0
        self.cache_misses = 0

    def prepare_system_prompt(
        self, system_prompt: str, cacheable: bool = True
    ) -> Any:
        """
        Prepare system prompt with appropriate cache control markers.

        For Anthropic: Adds cache_control to system message
        For OpenAI/Gemini: Returns prompt as-is (automatic caching)

        Returns:
            - Anthropic: List of message dicts with cache_control
            - Others: String (unchanged)
        """
        if self.provider == "anthropic" and cacheable:
            if len(system_prompt) >= ANTHROPIC_MIN_CACHE_TOKENS:
                return [
                    {
                        "role": "system",
                        "content": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                logger.debug("System prompt too short for Anthropic caching")
                return system_prompt
        return system_prompt

    def prepare_messages(self, messages: list, cache_last_n: int = 0) -> list:
        """
        Add cache_control to message history for Anthropic.

        Args:
            messages: List of message dicts
            cache_last_n: Cache the last N messages (0 = none)

        Returns:
            Modified message list with cache_control markers
        """
        if self.provider != "anthropic":
            return messages

        if cache_last_n > 0 and len(messages) > cache_last_n:
            for msg in messages[-cache_last_n:]:
                if isinstance(msg, dict) and "content" in msg:
                    msg["cache_control"] = {"type": "ephemeral"}

        return messages

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        return {
            "provider": self.provider,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate_percent": round(hit_rate, 2),
        }


class SemanticCache:
    """
    Application-layer semantic response caching.

    Caches LLM responses based on:
    - Provider + model
    - System prompt hash
    - User prompt hash

    Uses SQLite for persistent storage with LRU eviction and TTL.
    """

    def __init__(
        self,
        db_path: str = "data/semantic_cache.db",
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        max_size: int = DEFAULT_MAX_CACHE_SIZE,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._init_db()
        self.hits = 0
        self.misses = 0

    def _init_db(self):
        """Initialize SQLite cache database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    system_prompt_hash TEXT NOT NULL,
                    user_prompt_hash TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_accessed REAL NOT NULL,
                    access_count INTEGER DEFAULT 1
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_created_at ON cache_entries(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_last_accessed ON cache_entries(last_accessed)"
            )

    def _compute_key(
        self, provider: str, model: str, system_prompt: str, user_prompt: str
    ) -> str:
        """Compute cache key from inputs."""
        system_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:16]
        user_hash = hashlib.sha256(user_prompt.encode()).hexdigest()[:16]
        return f"{provider}:{model}:{system_hash}:{user_hash}"

    def get(
        self, provider: str, model: str, system_prompt: str, user_prompt: str
    ) -> Optional[str]:
        """
        Retrieve cached response if exists and not expired.

        Returns:
            Cached response string or None if not found/expired.
        """
        cache_key = self._compute_key(provider, model, system_prompt, user_prompt)
        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT response, created_at FROM cache_entries
                WHERE cache_key = ? AND ? - created_at < ?
                """,
                (cache_key, now, self.ttl_seconds),
            ).fetchone()

            if row:
                response, created_at = row
                # Update last_accessed and access_count
                conn.execute(
                    """
                    UPDATE cache_entries
                    SET last_accessed = ?, access_count = access_count + 1
                    WHERE cache_key = ?
                    """,
                    (now, cache_key),
                )
                self.hits += 1
                logger.debug(f"Semantic cache hit: {cache_key[:32]}...")
                return response
            else:
                self.misses += 1
                return None

    def put(
        self,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
    ):
        """Store response in cache."""
        cache_key = self._compute_key(provider, model, system_prompt, user_prompt)
        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            # Evict LRU if at capacity
            count = conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]
            if count >= self.max_size:
                # Delete least recently used
                conn.execute(
                    """
                    DELETE FROM cache_entries
                    WHERE cache_key = (
                        SELECT cache_key FROM cache_entries
                        ORDER BY last_accessed ASC LIMIT 1
                    )
                    """
                )

            conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries
                (cache_key, provider, model, system_prompt_hash, user_prompt_hash,
                 response, created_at, last_accessed, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    provider,
                    model,
                    hashlib.sha256(system_prompt.encode()).hexdigest()[:16],
                    hashlib.sha256(user_prompt.encode()).hexdigest()[:16],
                    response,
                    now,
                    now,
                    1,
                ),
            )
            logger.debug(f"Cached response: {cache_key[:32]}...")

    def clear_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                "DELETE FROM cache_entries WHERE ? - created_at >= ?",
                (now, self.ttl_seconds),
            )
            return result.rowcount

    def clear_all(self):
        """Clear all cached entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache_entries")

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]
            hits = self.hits
            misses = self.misses
            total_requests = hits + misses
            hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "cached_entries": total,
                "cache_hits": hits,
                "cache_misses": misses,
                "hit_rate_percent": round(hit_rate, 2),
                "ttl_seconds": self.ttl_seconds,
                "max_size": self.max_size,
            }


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation (4 chars ≈ 1 token for English).
    For precise counts, use tiktoken library.
    """
    return len(text) // 4


def truncate_to_token_budget(
    text: str, max_tokens: int, truncation_marker: str = "\n[...truncated]"
) -> str:
    """
    Truncate text to approximate token budget.

    Args:
        text: Text to truncate
        max_tokens: Maximum tokens allowed
        truncation_marker: Appended when truncation occurs

    Returns:
        Truncated text if over budget, original otherwise.
    """
    estimated = estimate_tokens(text)
    if estimated <= max_tokens:
        return text

    # Approximate chars to keep
    chars_to_keep = max_tokens * 4
    truncated = text[:chars_to_keep]
    return truncated + truncation_marker
