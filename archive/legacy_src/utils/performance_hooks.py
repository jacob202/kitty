"""
Integration hooks for performance monitoring.
Automatically tracks LLM calls throughout the application.
"""

import functools
import time
from collections.abc import Callable
from typing import Any

# Import performance monitor
try:
    from src.utils.performance_monitor import (
        CostTracker,
        MetricsCollector,
        cost_tracker,
        metrics_collector,
    )

    PERFORMANCE_MONITOR_AVAILABLE = True
except ImportError:
    PERFORMANCE_MONITOR_AVAILABLE = False


class ModelCallTracker:
    """
    Wrapper to track model calls with automatic performance monitoring.

    Usage:
        tracker = ModelCallTracker()

        # Wrap any model call function
        @tracker.track("chat")
        def my_model_call(prompt):
            return call_openai(prompt)
    """

    def __init__(self, collector: MetricsCollector | None = None):
        self.collector = collector or (metrics_collector if PERFORMANCE_MONITOR_AVAILABLE else None)

    def track(self, feature: str = "unknown", model: str | None = None):
        """
        Decorator to track model calls.

        Args:
            feature: Feature/module name for categorization
            model: Model name (can be extracted from args if not provided)
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if not PERFORMANCE_MONITOR_AVAILABLE or not self.collector:
                    return func(*args, **kwargs)

                # Determine model name
                model_name = model
                if model_name is None:
                    # Try to extract from kwargs or args
                    model_name = kwargs.get("model", "unknown")
                    if model_name == "unknown" and len(args) > 1:
                        model_name = args[1] if isinstance(args[1], str) else "unknown"

                # Start timing
                start_time = time.time()
                success = True
                response_text = ""
                prompt_text = ""

                try:
                    # Extract prompt for token estimation
                    if args:
                        prompt_text = str(args[0]) if isinstance(args[0], str) else ""
                    if "prompt" in kwargs:
                        prompt_text = kwargs["prompt"]

                    # Call the function
                    result = func(*args, **kwargs)

                    # Extract response text for token estimation
                    if isinstance(result, str):
                        response_text = result
                    elif isinstance(result, dict) and "content" in result:
                        response_text = result["content"]
                    elif hasattr(result, "content"):
                        response_text = str(result.content)

                    return result

                except Exception as e:
                    success = False
                    # Track error
                    self.collector.track_error(
                        error_type=type(e).__name__,
                        model=model_name,
                        feature=feature,
                        context=str(e),
                    )
                    raise

                finally:
                    # Calculate latency and track metrics
                    latency_ms = (time.time() - start_time) * 1000

                    # Estimate tokens (4 chars ≈ 1 token)
                    tokens_in = len(prompt_text) // 4
                    tokens_out = len(response_text) // 4

                    # Calculate cost
                    cost = self.collector.calculate_cost(model_name, tokens_in, tokens_out)

                    # Track the request
                    self.collector.track_request(
                        model=model_name,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        latency_ms=latency_ms,
                        cost=cost,
                        feature=feature,
                        success=success,
                    )

            return wrapper

        return decorator


class MiddlewareTracker:
    """
    Middleware integration for tracking by feature/routing.

    Usage:
        tracker = MiddlewareTracker()

        # In your middleware:
        result = tracker.track_route(middleware_result)
        # Then call the appropriate model based on result.route
    """

    def __init__(self, collector: MetricsCollector | None = None):
        self.collector = collector or (metrics_collector if PERFORMANCE_MONITOR_AVAILABLE else None)
        self._route_counts = {}

    def track_route(self, middleware_result) -> Any:
        """
        Track middleware routing decision.

        Args:
            middleware_result: The MiddlewareResult from KittyMiddleware

        Returns:
            The middleware_result unchanged
        """
        if not PERFORMANCE_MONITOR_AVAILABLE or not self.collector:
            return middleware_result

        # Track routing decision as metadata
        route = getattr(middleware_result, "route", "unknown")
        intent = getattr(middleware_result, "intent", "unknown")
        getattr(middleware_result, "model", "unknown")

        # Update route counts
        key = f"{intent}:{route}"
        self._route_counts[key] = self._route_counts.get(key, 0) + 1

        return middleware_result

    def get_route_stats(self) -> dict:
        """Get routing statistics."""
        return self._route_counts.copy()


class PerformanceMonitorMixin:
    """
    Mixin class for Supervisor to add performance monitoring.

    Usage:
        class Supervisor(PerformanceMonitorMixin):
            def __init__(self):
                super().__init__()
                self._init_performance_monitoring()
    """

    def _init_performance_monitoring(self):
        """Initialize performance monitoring."""
        if PERFORMANCE_MONITOR_AVAILABLE:
            self._metrics_collector = metrics_collector
            self._cost_tracker = cost_tracker
            self._model_tracker = ModelCallTracker(self._metrics_collector)
            self._middleware_tracker = MiddlewareTracker(self._metrics_collector)
        else:
            self._metrics_collector = None
            self._cost_tracker = None
            self._model_tracker = None
            self._middleware_tracker = None

    def track_model_call(
        self,
        model: str,
        prompt: str,
        response: str,
        feature: str = "unknown",
        latency_ms: float = 0.0,
    ):
        """Track a model call."""
        if self._metrics_collector:
            tokens_in = len(prompt) // 4
            tokens_out = len(response) // 4
            cost = self._metrics_collector.calculate_cost(model, tokens_in, tokens_out)

            self._metrics_collector.track_request(
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                cost=cost,
                feature=feature,
            )

            return cost
        return 0.0

    def track_cache_hit(self, cache_type: str):
        """Track a cache hit."""
        if self._metrics_collector:
            self._metrics_collector.track_cache_hit(cache_type)

    def track_cache_miss(self, cache_type: str):
        """Track a cache miss."""
        if self._metrics_collector:
            self._metrics_collector.track_cache_miss(cache_type)

    def track_error(
        self,
        error_type: str,
        model: str | None = None,
        feature: str | None = None,
        context: str | None = None,
    ):
        """Track an error."""
        if self._metrics_collector:
            self._metrics_collector.track_error(
                error_type=error_type, model=model, feature=feature, context=context
            )

    def get_performance_summary(self) -> dict:
        """Get performance summary."""
        if self._metrics_collector:
            return self._metrics_collector.get_performance_summary()
        return {}

    def set_budget_limit(self, daily: float | None = None, monthly: float | None = None):
        """Set budget limits."""
        if self._metrics_collector:
            self._metrics_collector.set_budget_limits(daily, monthly)


def patch_model_caller(model_caller_instance):
    """
    Patch a ModelCaller instance to track all calls.

    Usage:
        from src.core.model_caller import ModelCaller
        model_caller = ModelCaller(supervisor)
        patch_model_caller(model_caller)
    """
    if not PERFORMANCE_MONITOR_AVAILABLE:
        return

    original_call = model_caller_instance.call_with_fallback
    ModelCallTracker()

    @functools.wraps(original_call)
    def tracked_call(prompt, system_prompt=None, model="flash", use_history=True):
        start_time = time.time()
        success = True
        response = ""

        try:
            response = original_call(prompt, system_prompt, model, use_history)
            if isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)
            return response
        except Exception as e:
            success = False
            metrics_collector.track_error(
                error_type=type(e).__name__, model=model, feature="model_caller", context=str(e)
            )
            raise
        finally:
            latency_ms = (time.time() - start_time) * 1000
            tokens_in = len(prompt) // 4
            tokens_out = len(response_text) // 4 if "response_text" in dir() else 0

            # Map short model names to full names
            model_mapping = {
                "claude": "claude-3-5-sonnet-20241022",
                "flash": "google/gemini-2.0-flash-001",
                "local": "llama3.2:3b",
            }
            full_model = model_mapping.get(model, model)

            cost = metrics_collector.calculate_cost(full_model, tokens_in, tokens_out)

            metrics_collector.track_request(
                model=full_model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                cost=cost,
                feature="model_caller",
                success=success,
            )

    model_caller_instance.call_with_fallback = tracked_call


def patch_supervisor_stream_methods(supervisor_instance):
    """
    Patch Supervisor's streaming methods to track all LLM calls.

    Usage:
        sup = Supervisor()
        patch_supervisor_stream_methods(sup)
    """
    if not PERFORMANCE_MONITOR_AVAILABLE:
        return

    methods_to_patch = ["_stream_openrouter", "_stream_claude", "_stream_ollama"]

    for method_name in methods_to_patch:
        if hasattr(supervisor_instance, method_name):
            original_method = getattr(supervisor_instance, method_name)

            @functools.wraps(original_method)
            def make_tracked_method(orig, name):
                def tracked_method(*args, **kwargs):
                    start_time = time.time()
                    success = True
                    response = ""
                    model = kwargs.get("model", args[1] if len(args) > 1 else "unknown")

                    # Extract prompt
                    prompt = args[0] if args else ""

                    try:
                        response = orig(*args, **kwargs)
                        if isinstance(response, str):
                            response_text = response
                        else:
                            response_text = str(response)
                        return response
                    except Exception as e:
                        success = False
                        metrics_collector.track_error(
                            error_type=type(e).__name__,
                            model=model,
                            feature="supervisor",
                            context=str(e),
                        )
                        raise
                    finally:
                        latency_ms = (time.time() - start_time) * 1000
                        tokens_in = len(prompt) // 4
                        tokens_out = len(response_text) // 4 if "response_text" in dir() else 0

                        cost = metrics_collector.calculate_cost(model, tokens_in, tokens_out)

                        metrics_collector.track_request(
                            model=model,
                            tokens_in=tokens_in,
                            tokens_out=tokens_out,
                            latency_ms=latency_ms,
                            cost=cost,
                            feature=name,
                            success=success,
                        )

                return tracked_method

            setattr(
                supervisor_instance, method_name, make_tracked_method(original_method, method_name)
            )


def patch_middleware(middleware_instance):
    """
    Patch KittyMiddleware to track routing decisions.

    Usage:
        from src.middleware import KittyMiddleware
        middleware = KittyMiddleware()
        patch_middleware(middleware)
    """
    if not PERFORMANCE_MONITOR_AVAILABLE:
        return

    original_process = middleware_instance.process
    tracker = MiddlewareTracker()

    @functools.wraps(original_process)
    def tracked_process(prompt, history=None):
        result = original_process(prompt, history)
        return tracker.track_route(result)

    middleware_instance.process = tracked_process


# Convenience function to integrate with existing code
def integrate_performance_monitoring(
    supervisor_instance=None, middleware_instance=None, model_caller_instance=None
):
    """
    Integrate performance monitoring with existing Kitty AI components.

    Args:
        supervisor_instance: Supervisor instance to patch
        middleware_instance: KittyMiddleware instance to patch
        model_caller_instance: ModelCaller instance to patch
    """
    if not PERFORMANCE_MONITOR_AVAILABLE:
        print("[WARN] Performance monitoring not available - skipping integration")
        return

    if supervisor_instance:
        patch_supervisor_stream_methods(supervisor_instance)
        print("[INFO] Performance monitoring integrated with Supervisor")

    if middleware_instance:
        patch_middleware(middleware_instance)
        print("[INFO] Performance monitoring integrated with Middleware")

    if model_caller_instance:
        patch_model_caller(model_caller_instance)
        print("[INFO] Performance monitoring integrated with ModelCaller")

    print("[INFO] Performance monitoring active - metrics available at /admin/metrics")


# Global tracker instances
model_call_tracker = ModelCallTracker() if PERFORMANCE_MONITOR_AVAILABLE else None
middleware_tracker = MiddlewareTracker() if PERFORMANCE_MONITOR_AVAILABLE else None


if __name__ == "__main__":
    # Demo
    print("Performance Monitoring Integration Demo")
    print("=" * 50)

    if PERFORMANCE_MONITOR_AVAILABLE:
        # Create a sample function and track it
        @model_call_tracker.track("demo_feature", model="gpt-4")
        def sample_llm_call(prompt):
            # Simulate LLM call
            time.sleep(0.1)
            return f"Response to: {prompt}"

        # Make some tracked calls
        for i in range(3):
            result = sample_llm_call(f"Test prompt {i}")
            print(f"Call {i + 1}: {result[:30]}...")

        # Show summary
        summary = metrics_collector.get_performance_summary()
        print("\nPerformance Summary:")
        print(f"Today's cost: ${summary['today']['cost']:.4f}")
        print(f"Today's requests: {summary['today']['requests']}")
    else:
        print("Performance monitoring not available")
