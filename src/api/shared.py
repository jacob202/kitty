"""Shared rate limiter middleware, token broadcasting, and utilities for Flask blueprints."""

import queue
import re
import threading
import time

from flask import current_app


class SlidingWindowRateLimiter:
    """Thread-safe sliding window rate limiter with TTL-based eviction."""

    def __init__(self, window: int = 60, max_requests: int = 30, max_entries: int = 10000):
        self._cache: dict[str, list] = {}
        self._lock = threading.Lock()
        self._window = window
        self._max_requests = max_requests
        self._max_entries = max_entries

    def is_allowed(self, key: str) -> bool:
        """Return True if request is allowed, False if rate limited."""
        now = time.time()
        with self._lock:
            if key not in self._cache:
                self._cache[key] = [0, now]
            count, window_start = self._cache[key]
            if now - window_start > self._window:
                self._cache[key] = [0, now]
                return True
            if count >= self._max_requests:
                return False
            self._cache[key] = [count + 1, window_start]
            self._evict_stale(now)
            return True

    def _evict_stale(self, now: float):
        """Remove stale entries to prevent unbounded growth."""
        if len(self._cache) > self._max_entries:
            stale_keys = [
                k for k, (_, ws) in self._cache.items()
                if now - ws > self._window
            ]
            for k in stale_keys:
                del self._cache[k]


core_rate_limiter = SlidingWindowRateLimiter(window=60, max_requests=30)
memory_rate_limiter = SlidingWindowRateLimiter(window=60, max_requests=20)
honcho_rate_limiter = SlidingWindowRateLimiter(window=60, max_requests=20)
chat_rate_limiter = SlidingWindowRateLimiter(window=60, max_requests=10)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[()][A-Z0-9]|\r")


class TokenBroadcaster:
    """Fan-out broadcaster for SSE token streaming."""

    def __init__(self, max_queues: int = 100):
        self._queues: dict[str, queue.Queue] = {}
        self._lock = threading.Lock()
        self._max_queues = max_queues

    def register(self, client_id: str) -> queue.Queue | None:
        with self._lock:
            if len(self._queues) >= self._max_queues:
                oldest = next(iter(self._queues))
                del self._queues[oldest]
            q: queue.Queue = queue.Queue(maxsize=200)
            self._queues[client_id] = q
            return q

    def unregister(self, client_id: str):
        with self._lock:
            self._queues.pop(client_id, None)

    def broadcast(self, kind: str, text: str):
        with self._lock:
            dead_clients = []
            for cid, q in self._queues.items():
                try:
                    q.put_nowait((kind, text))
                except queue.Full:
                    dead_clients.append(cid)
            for cid in dead_clients:
                del self._queues[cid]


token_broadcaster = TokenBroadcaster()


class TokenCapture:
    """Wraps sys.stdout: passes through to terminal AND broadcasts to SSE queues."""

    def __init__(self, original):
        self._orig = original
        self._flush_interval = 0.05
        self._last_flush = time.time()

    def write(self, text):
        self._orig.write(text)
        if text:
            clean = _ANSI_RE.sub("", text)
            if "[STATE:UNHINGED]" in clean:
                token_broadcaster.broadcast("state", "UNHINGED")
                clean = clean.replace("[STATE:UNHINGED]", "")
            elif "[STATE:CALM]" in clean:
                token_broadcaster.broadcast("state", "CALM")
                clean = clean.replace("[STATE:CALM]", "")
            if clean and not clean.lstrip().startswith(("INFO:", "WARNING:", "DEBUG:")):
                token_broadcaster.broadcast("token", clean)

        now = time.time()
        if now - self._last_flush > self._flush_interval:
            self._orig.flush()
            self._last_flush = now

    def flush(self):
        self._orig.flush()
        self._last_flush = time.time()

    def __getattr__(self, name):
        return getattr(self._orig, name)


def get_pka_db():
    """Get the PKA database from the app's supervisor (if loaded)."""
    sup = getattr(current_app, "supervisor", None)
    if sup is None:
        return None
    instance = getattr(sup, "_instance", None)
    if instance is None:
        return getattr(sup, "pka_db", None)
    return getattr(instance, "pka_db", None)
