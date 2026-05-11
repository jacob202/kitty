"""
Outbound Rate Limiter for LLM Providers

Sliding window rate limiter that tracks request counts per provider per time window.
Preemptively throttles before hitting provider rate limits.

NOTE: This is for LLM provider-specific rate limiting (SQLite-backed).
For general API rate limiting, see src/utils/rate_limiter.py (token bucket).

Usage:
    limiter = RateLimiter("openrouter", max_requests=100, window_seconds=60)
    if limiter.should_throttle():
        # use fallback provider
    limiter.record_request()
"""

import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "rate_limiter.db"


@dataclass
class ProviderRateLimit:
    """Known rate limits for LLM providers."""
    provider: str
    max_requests: int
    window_seconds: int
    safety_margin: float = 0.8  # throttle at 80% of limit by default


# Default rate limits — update as providers change their limits
# These are conservative estimates; adjust based on actual tier limits
DEFAULT_RATE_LIMITS: dict[str, ProviderRateLimit] = {
    "openrouter": ProviderRateLimit("openrouter", max_requests=120, window_seconds=60, safety_margin=0.8),
    "anthropic": ProviderRateLimit("anthropic", max_requests=50, window_seconds=60, safety_margin=0.8),
    "mlx_local": ProviderRateLimit("mlx_local", max_requests=1000, window_seconds=60, safety_margin=0.9),
    # Gemini free tier (if used): 60 req/min
    "gemini": ProviderRateLimit("gemini", max_requests=60, window_seconds=60, safety_margin=0.8),
}


class RateLimiter:
    """Sliding window rate limiter for LLM providers."""

    def __init__(
        self,
        provider: str,
        config: ProviderRateLimit | None = None,
        db_path: Path = DB_PATH,
    ):
        self.provider = provider
        self.config = config or DEFAULT_RATE_LIMITS.get(
            provider, ProviderRateLimit(provider, max_requests=100, window_seconds=60)
        )
        self.db_path = db_path
        self._lock = Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create rate limiter tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS request_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_provider_timestamp
                ON request_log (provider, timestamp)
            """)
            # Clean up old entries on startup
            cutoff = time.time() - 3600  # keep 1 hour of history
            conn.execute("DELETE FROM request_log WHERE timestamp < ?", (cutoff,))
            conn.commit()

    def _count_recent_requests(self) -> int:
        """Count requests within the current window."""
        cutoff = time.time() - self.config.window_seconds
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM request_log WHERE provider = ? AND timestamp > ?",
                (self.provider, cutoff),
            ).fetchone()
            return row[0] if row else 0

    def _cleanup_old_entries(self):
        """Remove entries older than 2x the window to keep DB small."""
        cutoff = time.time() - (self.config.window_seconds * 2)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM request_log WHERE provider = ? AND timestamp < ?",
                (self.provider, cutoff),
            )
            conn.commit()

    def should_throttle(self) -> bool:
        """Check if we should throttle (approaching rate limit)."""
        with self._lock:
            count = self._count_recent_requests()
            threshold = int(self.config.max_requests * self.config.safety_margin)
            return count >= threshold

    def record_request(self):
        """Record a request to the provider."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO request_log (provider, timestamp) VALUES (?, ?)",
                    (self.provider, time.time()),
                )
                conn.commit()
            # Periodic cleanup
            self._cleanup_old_entries()

    def get_remaining(self) -> int:
        """Return estimated remaining requests in current window."""
        with self._lock:
            count = self._count_recent_requests()
            return max(0, self.config.max_requests - count)

    def get_usage(self) -> dict:
        """Return current usage stats for telemetry."""
        with self._lock:
            count = self._count_recent_requests()
            threshold = int(self.config.max_requests * self.config.safety_margin)
            return {
                "provider": self.provider,
                "requests_in_window": count,
                "max_requests": self.config.max_requests,
                "window_seconds": self.config.window_seconds,
                "throttle_threshold": threshold,
                "remaining": self.get_remaining(),
                "should_throttle": count >= threshold,
                "utilization_pct": round(
                    (count / self.config.max_requests) * 100, 1
                ) if self.config.max_requests > 0 else 0,
            }

    def reset(self):
        """Clear request log for this provider."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM request_log WHERE provider = ?", (self.provider,)
                )
                conn.commit()
            logger.info(f"Rate limiter reset for {self.provider}")


class RateLimiterRegistry:
    """Central registry for all provider rate limiters."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._limiters: dict[str, RateLimiter] = {}
        self._lock = Lock()

    def get(self, provider: str) -> RateLimiter:
        """Get or create a rate limiter for a provider."""
        with self._lock:
            if provider not in self._limiters:
                config = DEFAULT_RATE_LIMITS.get(provider)
                self._limiters[provider] = RateLimiter(
                    provider, config=config, db_path=self.db_path
                )
            return self._limiters[provider]

    def get_all_usage(self) -> list[dict]:
        """Return usage stats for all providers."""
        with self._lock:
            return [limiter.get_usage() for limiter in self._limiters.values()]

    def reset_all(self):
        """Reset all rate limiters."""
        with self._lock:
            for limiter in self._limiters.values():
                limiter.reset()
