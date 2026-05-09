"""
Integration module - connects SpecialistMetrics with performance hooks.
Hooks into performance_hooks.py and domain_router.py.
"""

import functools
import threading
import time

# Import performance hooks
try:
    from src.utils.performance_hooks import (
        PERFORMANCE_MONITOR_AVAILABLE,
        MiddlewareTracker,
        ModelCallTracker,
    )

    PERFORMANCE_HOOKS_AVAILABLE = True
except ImportError:
    PERFORMANCE_HOOKS_AVAILABLE = False

# Import specialist metrics
try:
    from src.dashboard.specialist_metrics import (
        SpecialistMetrics,
        calculate_cost,
        get_specialist_metrics,
    )

    SPECIALIST_METRICS_AVAILABLE = True
except ImportError:
    SPECIALIST_METRICS_AVAILABLE = False

# Import domain router
try:
    from src.core.query_router import Domain, QueryRouter, RoutingDecision

    DOMAIN_ROUTER_AVAILABLE = True
except ImportError:
    DOMAIN_ROUTER_AVAILABLE = False


class SpecialistMetricsTracker:
    """
    Tracks specialist-level metrics by integrating with performance hooks.

    Works by:
    1. Intercepting domain routing decisions to know which specialist handles each query
    2. Listening to model call events from performance_hooks
    3. Recording metrics to SpecialistMetrics
    """

    def __init__(self):
        self._metrics = get_specialist_metrics() if SPECIALIST_METRICS_AVAILABLE else None
        self._lock = threading.RLock()
        self._current_query: str | None = None
        self._current_specialist: str | None = None
        self._current_domain: str | None = None

    def set_current_query(self, specialist: str, domain: str, query: str) -> None:
        """Set current query context before making model call."""
        with self._lock:
            self._current_specialist = specialist
            self._current_domain = domain
            self._current_query = query

    def record_response(
        self,
        latency_ms: float,
        success: bool,
        tokens_in: int,
        tokens_out: int,
        model: str = "unknown",
        error_type: str | None = None,
    ) -> None:
        """Record response after model call completes."""
        if not self._metrics:
            return

        with self._lock:
            if not self._current_specialist or not self._current_domain:
                return

            cost = calculate_cost(model, tokens_in, tokens_out)

            self._metrics.record_query(
                specialist=self._current_specialist,
                domain=self._current_domain,
                query=self._current_query or "",
                latency_ms=latency_ms,
                success=success,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost=cost,
                error_type=error_type,
                model=model,
            )

            # Clear context after recording
            self._current_specialist = None
            self._current_domain = None
            self._current_query = None

    def record_from_routing(
        self, query: str, routing: RoutingDecision, latency_ms: float = 0.0
    ) -> None:
        """Record query based on routing decision (for LLM-fallback cases)."""
        if not self._metrics:
            return

        specialist = routing.specialist
        domain = routing.domain.value if hasattr(routing.domain, "value") else str(routing.domain)

        self._metrics.record_query(
            specialist=specialist,
            domain=domain,
            query=query,
            latency_ms=latency_ms,
            success=True,
            tokens_in=0,
            tokens_out=0,
            cost=0.0,
            error_type=None,
            model="llm",
        )


# Global singleton
_specialist_tracker: SpecialistMetricsTracker | None = None
_tracker_lock = threading.Lock()


def get_specialist_tracker() -> SpecialistMetricsTracker:
    """Get global SpecialistMetricsTracker singleton."""
    global _specialist_tracker
    if _specialist_tracker is None:
        with _tracker_lock:
            if _specialist_tracker is None:
                _specialist_tracker = SpecialistMetricsTracker()
    return _specialist_tracker


# ── Domain Router Integration ─────────────────────────────────────────────────────────


def patch_domain_router():
    """
    Patch DomainRouter to track routing decisions.

    After patching, all routing decisions will also be recorded to SpecialistMetrics.
    """
    if not DOMAIN_ROUTER_AVAILABLE or not SPECIALIST_METRICS_AVAILABLE:
        return False

    original_route = QueryRouter.route

    @functools.wraps(original_route)
    def tracked_route(self, query: str) -> RoutingDecision:
        result = original_route(self, query)
        specialist = result.specialist
        domain = result.domain.value if hasattr(result.domain, "value") else str(result.domain)
        tracker = get_specialist_tracker()
        tracker.set_current_query(specialist, domain, query)
        return result

    QueryRouter.route = tracked_route
    return True


# ── Performance Hooks Integration ───────────────────────────────────────────


class SpecialistModelTracker:
    """
    Wraps model calls to track specialist-level performance.

    Usage:
        tracker = SpecialistModelTracker()

        @tracker.track(specialist="Alex", domain="audio_electronics")
        def call_model(prompt):
            return openai.ChatCompletion.create(...)
    """

    def __init__(self):
        self._metrics = get_specialist_metrics() if SPECIALIST_METRICS_AVAILABLE else None
        self._tracker = get_specialist_tracker()

    def track(self, specialist: str, domain: str, model: str = "unknown"):
        """
        Decorator to track specialist model calls.

        Args:
            specialist: Specialist name
            domain: Domain name
            model: Model name
        """

        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                error_type = None

                self._tracker.set_current_query(specialist, domain, str(args[0]) if args else "")

                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error_type = type(e).__name__
                    raise
                finally:
                    latency_ms = (time.time() - start_time) * 1000
                    tokens_in = 0
                    tokens_out = 0

                    # Try to extract token counts
                    if "result" in dir():
                        if hasattr(result, "usage"):
                            tokens_in = result.usage.get("prompt_tokens", 0)
                            tokens_out = result.usage.get("completion_tokens", 0)

                    self._tracker.record_response(
                        latency_ms=latency_ms,
                        success=success,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        model=model,
                        error_type=error_type,
                    )

            return wrapper

        return decorator


# ── Supervisor Integration ─────────────────────────────────────────────


def integrate_with_supervisor(supervisor_instance):
    """
    Integrate specialist metrics tracking with Supervisor.

    This patches key Supervisor methods to track metrics automatically.

    Args:
        supervisor_instance: Supervisor instance to patch
    """
    if not SPECIALIST_METRICS_AVAILABLE:
        print("[WARN] Specialist metrics not available - skipping integration")
        return False

    tracker = SpecialistModelTracker()

    # Track streaming calls
    original_stream = getattr(supervisor_instance, "_stream_openrouter", None)
    if original_stream:

        @functools.wraps(original_stream)
        def tracked_stream(*args, **kwargs):
            start_time = time.time()
            success = True
            error_type = None

            # Try to get specialist from routing
            query = args[0] if args else ""
            domain = "general"
            specialist = "Kitty"

            # Extract query context
            tracker._tracker.set_current_query(specialist, domain, query)

            try:
                result = original_stream(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_type = type(e).__name__
                raise
            finally:
                latency_ms = (time.time() - start_time) * 1000
                model = kwargs.get("model", args[1] if len(args) > 1 else "unknown")

                tracker._tracker.record_response(
                    latency_ms=latency_ms,
                    success=success,
                    tokens_in=0,
                    tokens_out=0,
                    model=model,
                    error_type=error_type,
                )

        setattr(supervisor_instance, "_stream_openrouter", tracked_stream)

    print("[INFO] Specialist metrics integrated with Supervisor")
    return True


# ── Initialization ───────────────────────────────────────────────────


def initialize_integration():
    """
    Initialize all integrations.

    This should be called at startup to enable automatic tracking.
    """
    print("[INFO] Initializing specialist metrics integration...")

    if not SPECIALIST_METRICS_AVAILABLE:
        print("[WARN] SpecialistMetrics not available")
        return False

    # Patch domain router
    if patch_domain_router():
        print("[INFO] Domain router patched for specialist tracking")

    print("[INFO] Specialist metrics integration active")
    return True


# ── CLI Integration ─────────────────────────────────────────────────────


def register_dashboard_commands() -> dict:
    """
    Get dashboard CLI command handlers.

    Returns:
        Dict mapping command names to handlers
    """
    try:
        from src.dashboard.performance_dashboard import (
            DASHBOARD_COMMANDS,
            handle_dashboard_command,
        )

        return DASHBOARD_COMMANDS
    except ImportError:
        return {}


# Demo
if __name__ == "__main__":
    print("Specialist Metrics Integration Demo")
    print("=" * 50)

    print("\n1. Testing domain router integration...")
    if patch_domain_router():
        router = DomainRouter()
        decision = router.route("My tube amp is making a buzzing sound")
        print(f"   Routed to: {decision.specialist} ({decision.domain.value})")
        print("   ✓ Domain router patched")
    else:
        print("   ✗ Could not patch domain router")

    print("\n2. Manual query recording...")
    if SPECIALIST_METRICS_AVAILABLE:
        metrics = get_specialist_metrics()

        # Record some test queries
        metrics.record_query(
            specialist="Alex",
            domain="audio_electronics",
            query="Test query 1",
            latency_ms=250.0,
            success=True,
            tokens_in=100,
            tokens_out=200,
            cost=0.01,
            model="claude-3-5-sonnet-20241022",
        )

        print("   ✓ Query recorded")

        # Show stats
        stats = metrics.get_stats()
        print(f"\n   Specialist stats: {stats['Alex']['query_count']} queries")
    else:
        print("   ✗ SpecialistMetrics not available")

    print("\n✅ Integration demo complete")
