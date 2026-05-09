"""
Observability Integration — Hooks for web, CLI, and middleware.
Provides middleware for automatic metric collection and background monitoring.
"""

import functools
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

# Import observability modules
try:
    from .alert_manager import alert_manager
    from .dashboard_data import dashboard_aggregator
    from .metrics_collector import metrics_collector, track_api_request, track_llm_call

    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False

    # Create dummy objects
    class _DummyCollector:
        def track_api_request(self, *args, **kwargs):
            pass

        def track_llm_call(self, *args, **kwargs):
            pass

        def track_db_query(self, *args, **kwargs):
            pass

        def track_cache_op(self, *args, **kwargs):
            pass

        def get_metrics_summary(self):
            return {}

    class _DummyManager:
        def start_monitoring(self, *args, **kwargs):
            pass

        def stop_monitoring(self):
            pass

        def get_active_alerts(self, *args, **kwargs):
            return []

    metrics_collector = _DummyCollector()
    alert_manager = _DummyManager()
    dashboard_aggregator = None


class ObservabilityMiddleware:
    """
    Middleware for automatic observability integration.
    Hooks into Flask/FastAPI requests and tracks metrics automatically.
    """

    def __init__(self, app=None):
        self.app = app
        self._background_started = False

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize middleware with Flask app."""
        self.app = app

        # Register before/after request handlers
        if hasattr(app, "before_request"):
            app.before_request(self._before_request)
        if hasattr(app, "after_request"):
            app.after_request(self._after_request)

        # Start background monitoring
        self._start_background_monitoring()

    def _start_background_monitoring(self):
        """Start background monitoring if not already started."""
        if not self._background_started and OBSERVABILITY_AVAILABLE:
            alert_manager.start_monitoring(interval_seconds=30)
            self._background_started = True

    def _before_request(self):
        """Store request start time."""
        from flask import g

        g._observability_start_time = time.time()

    def _after_request(self, response):
        """Track request metrics."""
        from flask import g, request

        if not OBSERVABILITY_AVAILABLE:
            return response

        # Calculate response time
        start_time = getattr(g, "_observability_start_time", None)
        if start_time:
            elapsed_ms = (time.time() - start_time) * 1000
        else:
            elapsed_ms = 0

        # Get request info
        endpoint = request.endpoint or request.path
        method = request.method
        status_code = response.status_code

        # Estimate sizes
        request_size = len(request.data) if request.data else 0
        response_size = len(response.data) if hasattr(response, "data") and response.data else 0

        # Get user ID if available
        user_id = getattr(g, "user_id", None) or request.headers.get("X-User-ID")

        # Determine error type
        error_type = None
        if status_code >= 400:
            error_type = f"http_{status_code}"

        # Track the request
        try:
            metrics_collector.track_api_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time_ms=elapsed_ms,
                request_size_bytes=request_size,
                response_size_bytes=response_size,
                user_id=user_id,
                error_type=error_type,
            )
        except Exception:
            # Don't let observability break the app
            pass

        return response


def track_cli_command(command_name: str):
    """Decorator to track CLI command execution."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not OBSERVABILITY_AVAILABLE:
                return func(*args, **kwargs)

            start_time = time.time()
            error_type = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_type = type(e).__name__
                raise
            finally:
                elapsed_ms = (time.time() - start_time) * 1000

                try:
                    metrics_collector.track_api_request(
                        endpoint=f"/cli/{command_name}",
                        method="CLI",
                        status_code=500 if error_type else 200,
                        response_time_ms=elapsed_ms,
                        error_type=error_type,
                    )
                except Exception:
                    pass

        return wrapper

    return decorator


def track_llm_wrapper(model: str, provider: str, feature: str = "unknown"):
    """
    Decorator/wrapper to track LLM calls.

    Usage:
        @track_llm_wrapper("gpt-4", "openai", "chat")
        def make_llm_call(prompt):
            # ... make actual call
            return response, tokens_in, tokens_out
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not OBSERVABILITY_AVAILABLE:
                return func(*args, **kwargs)

            start_time = time.time()
            error_type = None
            success = True

            try:
                result = func(*args, **kwargs)

                # Try to extract token info from result
                tokens_in = 0
                tokens_out = 0
                cost = 0.0

                if isinstance(result, tuple) and len(result) >= 3:
                    # Assume (response, tokens_in, tokens_out)
                    tokens_in = result[1]
                    tokens_out = result[2]
                    if len(result) >= 4:
                        cost = result[3]

                return result
            except Exception as e:
                error_type = type(e).__name__
                success = False
                raise
            finally:
                elapsed_ms = (time.time() - start_time) * 1000

                try:
                    metrics_collector.track_llm_call(
                        model=model,
                        provider=provider,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        latency_ms=elapsed_ms,
                        cost_usd=cost,
                        feature=feature,
                        success=success,
                        error_type=error_type,
                    )
                except Exception:
                    pass

        return wrapper

    return decorator


@contextmanager
def track_llm_context(model: str, provider: str, feature: str = "unknown"):
    """
    Context manager for tracking LLM calls.

    Usage:
        with track_llm_context("gpt-4", "openai", "chat") as tracker:
            response = make_api_call()
            tracker.set_tokens(tokens_in, tokens_out)
            tracker.set_cost(cost)
    """
    if not OBSERVABILITY_AVAILABLE:
        yield _DummyTracker()
        return

    tracker = _LLMTracker(model, provider, feature)
    start_time = time.time()

    try:
        yield tracker
    except Exception as e:
        tracker._error_type = type(e).__name__
        tracker._success = False
        raise
    finally:
        elapsed_ms = (time.time() - start_time) * 1000
        tracker._record(elapsed_ms)


class _DummyTracker:
    """Dummy tracker when observability is not available."""

    def set_tokens(self, *args):
        pass

    def set_cost(self, *args):
        pass

    def set_cache_hit(self, *args):
        pass


class _LLMTracker:
    """LLM call tracker for context manager."""

    def __init__(self, model: str, provider: str, feature: str):
        self.model = model
        self.provider = provider
        self.feature = feature
        self.tokens_in = 0
        self.tokens_out = 0
        self.cost = 0.0
        self.cache_hit = False
        self._error_type = None
        self._success = True

    def set_tokens(self, tokens_in: int, tokens_out: int):
        """Set token counts."""
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out

    def set_cost(self, cost: float):
        """Set call cost."""
        self.cost = cost

    def set_cache_hit(self, cache_hit: bool = True):
        """Set cache hit status."""
        self.cache_hit = cache_hit

    def _record(self, elapsed_ms: float):
        """Record the metrics."""
        try:
            metrics_collector.track_llm_call(
                model=self.model,
                provider=self.provider,
                tokens_in=self.tokens_in,
                tokens_out=self.tokens_out,
                latency_ms=elapsed_ms,
                cost_usd=self.cost,
                feature=self.feature,
                success=self._success,
                error_type=self._error_type,
                cache_hit=self.cache_hit,
            )
        except Exception:
            pass


def track_middleware_call(middleware_result, latency_ms: float):
    """
    Track a middleware routing decision.

    Args:
        middleware_result: The MiddlewareResult object
        latency_ms: How long the middleware took
    """
    if not OBSERVABILITY_AVAILABLE:
        return

    try:
        # Track as an API request to /middleware
        metrics_collector.track_api_request(
            endpoint="/middleware/route",
            method="INTERNAL",
            status_code=200,
            response_time_ms=latency_ms,
        )

        # Could also track the routing decision
        # This helps understand routing patterns
    except Exception:
        pass


def track_db_operation(query_type: str, table_name: str, execution_time_ms: float, **kwargs):
    """Track a database operation."""
    if not OBSERVABILITY_AVAILABLE:
        return

    try:
        metrics_collector.track_db_query(
            query_type=query_type,
            table_name=table_name,
            execution_time_ms=execution_time_ms,
            **kwargs,
        )
    except Exception:
        pass


def track_cache_operation(cache_type: str, operation: str, **kwargs):
    """Track a cache operation."""
    if not OBSERVABILITY_AVAILABLE:
        return

    try:
        metrics_collector.track_cache_op(cache_type=cache_type, operation=operation, **kwargs)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# Background Monitoring
# ═══════════════════════════════════════════════════════════════════════════

_background_thread: threading.Thread | None = None
_background_running = False


def start_observability_monitoring(interval_seconds: int = 30):
    """
    Start background observability monitoring.

    This should be called once at application startup.
    """
    global _background_running, _background_thread

    if _background_running or not OBSERVABILITY_AVAILABLE:
        return

    _background_running = True

    def monitoring_loop():
        while _background_running:
            try:
                # Run aggregations
                metrics_collector.aggregate_minute_metrics()
                metrics_collector.aggregate_hourly_metrics()

                # Evaluate alert rules
                alert_manager.evaluate_rules()

            except Exception as e:
                # Log but don't crash
                import logging

                logging.getLogger(__name__).error(f"Observability monitoring error: {e}")

            # Sleep
            time.sleep(interval_seconds)

    _background_thread = threading.Thread(target=monitoring_loop, daemon=True)
    _background_thread.start()


def stop_observability_monitoring():
    """Stop background observability monitoring."""
    global _background_running
    _background_running = False

    if _background_thread:
        _background_thread.join(timeout=5)


# ═══════════════════════════════════════════════════════════════════════════
# Session Management
# ═══════════════════════════════════════════════════════════════════════════


def track_session_start(session_id: str, user_id: str | None = None, **kwargs):
    """Track a user session start."""
    if OBSERVABILITY_AVAILABLE:
        try:
            metrics_collector.track_session_start(session_id, user_id, **kwargs)
        except Exception:
            pass


def track_session_activity(session_id: str):
    """Track user session activity."""
    if OBSERVABILITY_AVAILABLE:
        try:
            metrics_collector.track_session_activity(session_id)
        except Exception:
            pass


def track_session_end(session_id: str):
    """Track a user session end."""
    if OBSERVABILITY_AVAILABLE:
        try:
            metrics_collector.track_session_end(session_id)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════════


def get_system_status() -> dict[str, Any]:
    """Get complete system status for health checks."""
    if not OBSERVABILITY_AVAILABLE:
        return {"observability": "unavailable"}

    try:
        return {
            "observability": "available",
            "metrics": metrics_collector.get_metrics_summary(),
            "alerts": {
                "active": len(alert_manager.get_active_alerts()),
                "rules": len(alert_manager.list_rules()),
            },
            "health": dashboard_aggregator.calculate_health_score()
            if dashboard_aggregator
            else None,
        }
    except Exception as e:
        return {"observability": "error", "error": str(e)}


__all__ = [
    "ObservabilityMiddleware",
    "track_cli_command",
    "track_llm_wrapper",
    "track_llm_context",
    "track_middleware_call",
    "track_db_operation",
    "track_cache_operation",
    "track_session_start",
    "track_session_activity",
    "track_session_end",
    "start_observability_monitoring",
    "stop_observability_monitoring",
    "get_system_status",
    "metrics_collector",
    "alert_manager",
    "dashboard_aggregator",
    "OBSERVABILITY_AVAILABLE",
]
