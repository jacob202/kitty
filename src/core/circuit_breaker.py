"""
Circuit Breaker Pattern for LLM Provider Resilience

Three states: CLOSED (normal), OPEN (failing, skip provider), HALF_OPEN (testing recovery).
SQLite-backed for persistence across restarts.

Usage:
    cb = CircuitBreaker("openrouter", failure_threshold=3, recovery_timeout=900)
    if cb.is_open():
        # skip this provider
    try:
        result = call_provider()
        cb.record_success()
    except Exception:
        cb.record_failure()
"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "circuit_breaker.db"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Per-provider circuit breaker configuration."""
    failure_threshold: int = 3      # failures before opening
    recovery_timeout: int = 900     # seconds before trying again (15 min default)
    half_open_max_calls: int = 1    # test calls allowed in half_open state
    failure_window: int = 300       # seconds - only count failures within this window (5 min)


@dataclass
class CircuitStats:
    """Current state of a circuit breaker."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    last_state_change: float = 0.0
    total_failures: int = 0
    total_successes: int = 0


class CircuitBreaker:
    """SQLite-backed circuit breaker for LLM providers."""

    def __init__(
        self,
        provider: str,
        config: CircuitBreakerConfig | None = None,
        db_path: Path = DB_PATH,
    ):
        self.provider = provider
        self.config = config or CircuitBreakerConfig()
        self.db_path = db_path
        self._lock = Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._state = self._load_state()

    def _init_db(self):
        """Create circuit breaker tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS circuits (
                    provider TEXT PRIMARY KEY,
                    state TEXT NOT NULL DEFAULT 'closed',
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    last_failure_time REAL NOT NULL DEFAULT 0,
                    last_success_time REAL NOT NULL DEFAULT 0,
                    last_state_change REAL NOT NULL DEFAULT 0,
                    total_failures INTEGER NOT NULL DEFAULT 0,
                    total_successes INTEGER NOT NULL DEFAULT 0,
                    failure_timestamps TEXT NOT NULL DEFAULT '[]'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS circuit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    details TEXT
                )
            """)
            conn.commit()

    def _load_state(self) -> CircuitStats:
        """Load circuit state from SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM circuits WHERE provider = ?", (self.provider,)
            ).fetchone()
            if row:
                stats = CircuitStats(
                    state=CircuitState(row[1]),
                    failure_count=row[2],
                    success_count=row[3],
                    last_failure_time=row[4],
                    last_success_time=row[5],
                    last_state_change=row[6],
                    total_failures=row[7],
                    total_successes=row[8],
                )
                # Check if recovery timeout has elapsed for open circuits
                if stats.state == CircuitState.OPEN:
                    elapsed = time.time() - stats.last_failure_time
                    if elapsed >= self.config.recovery_timeout:
                        self._transition_to(stats, CircuitState.HALF_OPEN)
                        logger.info(
                            f"Circuit for {self.provider} transitioning to HALF_OPEN "
                            f"after {elapsed:.0f}s recovery window"
                        )
                return stats
            return CircuitStats(last_state_change=time.time())

    def _save_state(self, stats: CircuitStats):
        """Persist circuit state to SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO circuits
                   (provider, state, failure_count, success_count,
                    last_failure_time, last_success_time, last_state_change,
                    total_failures, total_successes, failure_timestamps)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.provider,
                    stats.state.value,
                    stats.failure_count,
                    stats.success_count,
                    stats.last_failure_time,
                    stats.last_success_time,
                    stats.last_state_change,
                    stats.total_failures,
                    stats.total_successes,
                    "[]",
                ),
            )
            conn.commit()

    def _log_event(self, event_type: str, details: str = ""):
        """Log circuit event for audit trail."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO circuit_events (provider, event_type, timestamp, details) VALUES (?, ?, ?, ?)",
                (self.provider, event_type, time.time(), details),
            )
            conn.commit()

    def _transition_to(self, stats: CircuitStats, new_state: CircuitState):
        """Transition circuit to a new state."""
        old_state = stats.state
        stats.state = new_state
        stats.last_state_change = time.time()
        if new_state == CircuitState.CLOSED:
            stats.failure_count = 0
            stats.success_count = 0
        self._save_state(stats)
        self._log_event(
            "state_change",
            f"{old_state.value} -> {new_state.value}",
        )
        logger.info(
            f"Circuit {self.provider}: {old_state.value} -> {new_state.value}"
        )

    def _prune_old_failures(self, failure_timestamps: list[float]) -> list[float]:
        """Remove failures outside the failure window."""
        cutoff = time.time() - self.config.failure_window
        return [t for t in failure_timestamps if t > cutoff]

    def _load_failure_timestamps(self) -> list[float]:
        """Load recent failure timestamps from the failure_timestamps JSON column."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT failure_timestamps FROM circuits WHERE provider = ?",
                (self.provider,),
            ).fetchone()
            if row and row[0]:
                try:
                    return json.loads(row[0])
                except (json.JSONDecodeError, TypeError):
                    return []
        return []

    def _save_failure_timestamps(self, timestamps: list[float]):
        """Save failure timestamps as JSON."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE circuits SET failure_timestamps = ? WHERE provider = ?",
                (json.dumps(timestamps), self.provider),
            )
            conn.commit()

    def is_open(self) -> bool:
        """Check if circuit is open (provider should be skipped)."""
        with self._lock:
            self._state = self._load_state()
            if self._state.state == CircuitState.OPEN:
                return True
            if self._state.state == CircuitState.HALF_OPEN:
                # Allow one test call through
                return False
            return False

    def record_success(self):
        """Record a successful provider call."""
        with self._lock:
            self._state = self._load_state()
            self._state.success_count += 1
            self._state.total_successes += 1
            self._state.last_success_time = time.time()

            if self._state.state == CircuitState.HALF_OPEN:
                # Successful test call — close the circuit
                self._transition_to(self._state, CircuitState.CLOSED)
                logger.info(f"Circuit {self.provider} CLOSED after successful recovery test")
            elif self._state.state == CircuitState.CLOSED:
                # Reset failure count on success
                if self._state.failure_count > 0:
                    self._state.failure_count = 0
                    self._save_failure_timestamps([])
                    self._save_state(self._state)

    def record_failure(self, error: str = ""):
        """Record a provider failure."""
        with self._lock:
            self._state = self._load_state()
            now = time.time()
            self._state.failure_count += 1
            self._state.total_failures += 1
            self._state.last_failure_time = now

            # Track timestamps for windowed counting
            timestamps = self._load_failure_timestamps()
            timestamps.append(now)
            timestamps = self._prune_old_failures(timestamps)
            self._save_failure_timestamps(timestamps)

            if self._state.state == CircuitState.HALF_OPEN:
                # Test call failed — reopen
                self._transition_to(self._state, CircuitState.OPEN)
                self._log_event("failure", f"Half-open test failed: {error}")
                logger.warning(
                    f"Circuit {self.provider} re-OPENED after half-open failure"
                )
            elif self._state.state == CircuitState.CLOSED:
                windowed_failures = len(timestamps)
                if windowed_failures >= self.config.failure_threshold:
                    self._transition_to(self._state, CircuitState.OPEN)
                    self._log_event(
                        "failure",
                        f"Threshold reached: {windowed_failures} failures in "
                        f"{self.config.failure_window}s window. Error: {error}",
                    )
                    logger.warning(
                        f"Circuit {self.provider} OPENED after {windowed_failures} "
                        f"failures in {self.config.failure_window}s window"
                    )
                else:
                    self._save_state(self._state)
                    self._log_event("failure", f"Failure {windowed_failures}/{self.config.failure_threshold}. Error: {error}")

    def get_stats(self) -> dict:
        """Return current circuit stats for telemetry."""
        with self._lock:
            self._state = self._load_state()
            return {
                "provider": self.provider,
                "state": self._state.state.value,
                "failure_count": self._state.failure_count,
                "success_count": self._state.success_count,
                "total_failures": self._state.total_failures,
                "total_successes": self._state.total_successes,
                "last_failure_time": self._state.last_failure_time,
                "last_success_time": self._state.last_success_time,
                "recovery_timeout_remaining": max(
                    0,
                    int(self.config.recovery_timeout - (time.time() - self._state.last_failure_time))
                    if self._state.state == CircuitState.OPEN
                    else 0,
                ),
            }

    def reset(self):
        """Manually reset circuit to closed state."""
        with self._lock:
            self._state = self._load_state()
            self._transition_to(self._state, CircuitState.CLOSED)
            self._save_failure_timestamps([])
            self._log_event("manual_reset", "Circuit manually reset")
            logger.info(f"Circuit {self.provider} manually reset to CLOSED")
