"""
Resilience patterns for Kitty AI — Circuit Breaker, Retry Handler, and Fallback Chain.
Production-grade fault tolerance for critical operations.
"""

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    window_seconds: float = 60.0  # Time window for failures
    retry_seconds: float = 30.0  # Time before half-open
    success_threshold: int = 2  # Successes to close from half-open


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Tracks success/failure counts and opens circuit after threshold failures.
    Allows half-open retry after cooldown period.

    Usage:
        cb = CircuitBreaker("openrouter", CircuitBreakerConfig())

        @cb.protect
        def call_api():
            return requests.get(url)
    """

    _instances: dict[str, "CircuitBreaker"] = {}

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failures: list[float] = []
        self.successes_in_half_open = 0
        self.last_failure_time: float | None = None
        self.last_state_change: float = time.time()

    @classmethod
    def get(cls, name: str, config: CircuitBreakerConfig | None = None) -> "CircuitBreaker":
        """Get or create a named circuit breaker instance."""
        if name not in cls._instances:
            cls._instances[name] = cls(name, config)
        return cls._instances[name]

    @classmethod
    def reset_all(cls):
        """Reset all circuit breakers (for testing/emergency)."""
        cls._instances.clear()

    def _clean_old_failures(self):
        """Remove failures outside the time window."""
        now = time.time()
        cutoff = now - self.config.window_seconds
        self.failures = [f for f in self.failures if f > cutoff]

    def _should_open(self) -> bool:
        """Check if circuit should open based on failure threshold."""
        self._clean_old_failures()
        return len(self.failures) >= self.config.failure_threshold

    def _can_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.retry_seconds

    def record_success(self):
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.successes_in_half_open += 1
            if self.successes_in_half_open >= self.config.success_threshold:
                logger.info(
                    f"Circuit '{self.name}' closing after {self.successes_in_half_open} successes"
                )
                self.state = CircuitState.CLOSED
                self.failures = []
                self.successes_in_half_open = 0
                self.last_state_change = time.time()
        elif self.state == CircuitState.CLOSED:
            # Clear failures on success in closed state
            if self.failures:
                self._clean_old_failures()

    def record_failure(self):
        """Record a failed call."""
        now = time.time()
        self.failures.append(now)
        self.last_failure_time = now

        if self.state == CircuitState.HALF_OPEN:
            # Back to open on failure in half-open
            logger.warning(f"Circuit '{self.name}' re-opening after half-open failure")
            self.state = CircuitState.OPEN
            self.successes_in_half_open = 0
            self.last_state_change = now
        elif self.state == CircuitState.CLOSED and self._should_open():
            logger.warning(f"Circuit '{self.name}' opening after {len(self.failures)} failures")
            self.state = CircuitState.OPEN
            self.last_state_change = now

    def can_execute(self) -> bool:
        """Check if execution should be allowed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self._can_attempt_reset():
                logger.info(f"Circuit '{self.name}' entering half-open state")
                self.state = CircuitState.HALF_OPEN
                self.successes_in_half_open = 0
                self.last_state_change = time.time()
                return True
            return False

        # HALF_OPEN - allow one probe
        return True

    def protect(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to protect a function with this circuit breaker."""

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if not self.can_execute():
                raise CircuitOpenError(
                    f"Circuit '{self.name}' is OPEN - too many failures, "
                    f"try again after {self.config.retry_seconds}s cooldown"
                )

            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise e

        return wrapper

    def get_state(self) -> dict[str, Any]:
        """Get current circuit breaker state for monitoring."""
        self._clean_old_failures()
        return {
            "name": self.name,
            "state": self.state.value,
            "failures_in_window": len(self.failures),
            "failure_threshold": self.config.failure_threshold,
            "last_failure_time": self.last_failure_time,
            "last_state_change": self.last_state_change,
            "seconds_in_current_state": time.time() - self.last_state_change,
        }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


class RetryStrategy(Enum):
    """Retry backoff strategies."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_delay: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True
    jitter_max: float = 0.1  # Max jitter as fraction of delay
    retryable_exceptions: tuple = (Exception,)  # Exceptions to retry on


class RetryHandler:
    """
    Handles retry logic with exponential backoff and jitter.

    Usage:
        config = RetryConfig(max_attempts=3, initial_delay=1.0)
        handler = RetryHandler(config)
        result = handler.execute(call_api, url)

        # Or as decorator
        @RetryHandler.with_retry(RetryConfig())
        def call_api(url):
            return requests.get(url)
    """

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt with optional jitter."""
        if self.config.strategy == RetryStrategy.LINEAR:
            delay = self.config.initial_delay * attempt
        elif self.config.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.config.initial_delay * (self.config.backoff_multiplier ** (attempt - 1))
        else:  # CONSTANT
            delay = self.config.initial_delay

        delay = min(delay, self.config.max_delay)

        # Add jitter to prevent thundering herd
        if self.config.jitter:
            jitter_amount = delay * self.config.jitter_max
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)  # Ensure non-negative

        return delay

    def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with retry logic."""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except self.config.retryable_exceptions as e:
                last_exception = e

                if attempt < self.config.max_attempts:
                    delay = self.calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt}/{self.config.max_attempts} failed for {func.__name__}: "
                        f"{e}. Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"All {self.config.max_attempts} attempts failed for {func.__name__}: {e}"
                    )

        raise last_exception

    @classmethod
    def with_retry(cls, config: RetryConfig | None = None):
        """Decorator factory for retry logic."""

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            handler = cls(config)

            @wraps(func)
            def wrapper(*args, **kwargs) -> T:
                return handler.execute(func, *args, **kwargs)

            return wrapper

        return decorator


@dataclass
class FallbackService:
    """Represents a service in the fallback chain."""

    name: str
    priority: int
    func: Callable[..., T]
    is_primary: bool = False


class FallbackChain(Generic[T]):
    """
    Fallback chain for critical operations.

    Registers primary and fallback services, auto-fallback on failure.

    Usage:
        chain = FallbackChain[str]("llm_call")
        chain.register_primary("gpt-4", call_gpt4)
        chain.register_fallback("claude", call_claude, priority=1)
        chain.register_fallback("local", call_ollama, priority=2)

        result = chain.execute(prompt="Hello")
    """

    def __init__(self, name: str):
        self.name = name
        self.services: dict[str, FallbackService] = {}
        self.primary: str | None = None
        self.attempt_counts: dict[str, int] = {}
        self.success_counts: dict[str, int] = {}

    def register_primary(self, name: str, func: Callable[..., T]) -> "FallbackChain[T]":
        """Register the primary service."""
        self.services[name] = FallbackService(name=name, priority=0, func=func, is_primary=True)
        self.primary = name
        self.attempt_counts[name] = 0
        self.success_counts[name] = 0
        return self

    def register_fallback(
        self, name: str, func: Callable[..., T], priority: int = 1
    ) -> "FallbackChain[T]":
        """Register a fallback service with priority (lower = tried earlier)."""
        self.services[name] = FallbackService(
            name=name, priority=priority, func=func, is_primary=False
        )
        self.attempt_counts[name] = 0
        self.success_counts[name] = 0
        return self

    def _get_service_order(self) -> list[str]:
        """Get services ordered by priority."""
        # Primary first, then by priority
        services = sorted(
            self.services.values(), key=lambda s: (0 if s.is_primary else 1, s.priority)
        )
        return [s.name for s in services]

    def execute(self, *args, **kwargs) -> T:
        """Execute through the fallback chain."""
        service_order = self._get_service_order()
        last_error = None

        for service_name in service_order:
            service = self.services[service_name]
            self.attempt_counts[service_name] += 1

            try:
                logger.info(f"FallbackChain '{self.name}': Trying {service_name}")
                result = service.func(*args, **kwargs)
                self.success_counts[service_name] += 1

                # Log if we used a fallback
                if not service.is_primary:
                    logger.warning(
                        f"FallbackChain '{self.name}': Used fallback {service_name} "
                        f"(primary {self.primary} failed)"
                    )

                return result
            except Exception as e:
                logger.warning(f"FallbackChain '{self.name}': {service_name} failed: {e}")
                last_error = e
                continue

        # All services failed
        logger.error(f"FallbackChain '{self.name}': All services failed")
        raise FallbackExhaustedError(
            f"All services in fallback chain '{self.name}' failed", last_error
        )

    def get_stats(self) -> dict[str, Any]:
        """Get statistics for the fallback chain."""
        return {
            "name": self.name,
            "primary": self.primary,
            "services": list(self.services.keys()),
            "attempts": self.attempt_counts.copy(),
            "successes": self.success_counts.copy(),
            "success_rates": {
                name: (
                    self.success_counts[name] / self.attempt_counts[name]
                    if self.attempt_counts[name] > 0
                    else 0
                )
                for name in self.services.keys()
            },
        }


class FallbackExhaustedError(Exception):
    """Raised when all fallback services fail."""

    def __init__(self, message: str, last_error: Exception | None = None):
        super().__init__(message)
        self.last_error = last_error


# Convenience decorators and functions


def with_resilience(
    circuit_name: str | None = None,
    retry_config: RetryConfig | None = None,
    fallback_chain: FallbackChain | None = None,
):
    """
    Combined decorator for circuit breaker + retry + fallback.

    Usage:
        @with_resilience(
            circuit_name="openrouter",
            retry_config=RetryConfig(max_attempts=3),
        )
        def call_openrouter(prompt):
            return requests.post(...)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        wrapped = func

        # Apply fallback first (outermost)
        if fallback_chain:
            fallback_chain.execute = lambda *a, **kw: wrapped(*a, **kw)
            def wrapped(*a, **kw):
                return fallback_chain.execute(*a, **kw)

        # Apply retry
        if retry_config:
            retry_handler = RetryHandler(retry_config)
            def wrapped(*a, **kw):
                return retry_handler.execute(func, *a, **kw)

        # Apply circuit breaker (innermost, closest to function)
        if circuit_name:
            cb = CircuitBreaker.get(circuit_name)
            wrapped = cb.protect(wrapped)

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return wrapped(*args, **kwargs)

        return wrapper

    return decorator


def create_llm_resilience_chain(
    primary_func: Callable[..., T],
    fallback_funcs: list[tuple[str, Callable[..., T]]],
    circuit_name: str = "llm",
) -> Callable[..., T]:
    """
    Create a resilient LLM call with circuit breaker, retry, and fallback.

    Usage:
        resilient_call = create_llm_resilience_chain(
            primary_func=call_gpt4,
            fallback_funcs=[("claude", call_claude), ("ollama", call_ollama)],
            circuit_name="llm_api",
        )
        result = resilient_call(prompt="Hello")
    """
    # Create fallback chain
    chain = FallbackChain[T](circuit_name)
    chain.register_primary("primary", primary_func)

    for i, (name, func) in enumerate(fallback_funcs):
        chain.register_fallback(name, func, priority=i + 1)

    # Create retry config for LLM calls
    retry_config = RetryConfig(
        max_attempts=3,
        initial_delay=1.0,
        strategy=RetryStrategy.EXPONENTIAL,
        jitter=True,
    )

    # Get or create circuit breaker
    cb = CircuitBreaker.get(circuit_name)

    # Combine all patterns
    def resilient_call(*args, **kwargs) -> T:
        def execute_with_retry():
            handler = RetryHandler(retry_config)
            return handler.execute(chain.execute, *args, **kwargs)

        return cb.protect(execute_with_retry)()

    return resilient_call


# Resilient wrappers for common operations


class ResilientDatabase:
    """Wrapper for database operations with retry logic."""

    def __init__(self, db_client, retry_config: RetryConfig | None = None):
        self.db = db_client
        self.retry_config = retry_config or RetryConfig(
            max_attempts=3,
            initial_delay=0.5,
            strategy=RetryStrategy.EXPONENTIAL,
            retryable_exceptions=(ConnectionError, TimeoutError),
        )
        self.retry_handler = RetryHandler(self.retry_config)

    def execute(self, query: str, params: tuple = None):
        """Execute query with retry."""
        return self.retry_handler.execute(self.db.execute, query, params)

    def fetchone(self, query: str, params: tuple = None):
        """Fetch one with retry."""

        def fetch():
            cursor = self.db.execute(query, params)
            return cursor.fetchone()

        return self.retry_handler.execute(fetch)

    def fetchall(self, query: str, params: tuple = None):
        """Fetch all with retry."""

        def fetch():
            cursor = self.db.execute(query, params)
            return cursor.fetchall()

        return self.retry_handler.execute(fetch)


class ResilientFileOps:
    """Wrapper for file operations with error recovery."""

    def __init__(self, retry_config: RetryConfig | None = None):
        self.retry_config = retry_config or RetryConfig(
            max_attempts=3,
            initial_delay=0.1,
            strategy=RetryStrategy.LINEAR,
            retryable_exceptions=(IOError, PermissionError),
        )
        self.retry_handler = RetryHandler(self.retry_config)

    def read(self, path: str, mode: str = "r") -> Any:
        """Read file with retry."""

        def read_file():
            with open(path, mode) as f:
                return f.read()

        return self.retry_handler.execute(read_file)

    def write(self, path: str, content: str, mode: str = "w") -> None:
        """Write file with retry."""

        def write_file():
            with open(path, mode) as f:
                f.write(content)

        return self.retry_handler.execute(write_file)

    def exists(self, path: str) -> bool:
        """Check if file exists."""
        import os

        return os.path.exists(path)


# Export key classes and functions
__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "CircuitOpenError",
    "RetryHandler",
    "RetryConfig",
    "RetryStrategy",
    "FallbackChain",
    "FallbackService",
    "FallbackExhaustedError",
    "with_resilience",
    "create_llm_resilience_chain",
    "ResilientDatabase",
    "ResilientFileOps",
]
