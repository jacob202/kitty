"""
Kitty AI Observability & Alerting System

Production-grade observability for monitoring API performance, LLM usage,
database queries, error rates, and system health.

Components:
- metrics_collector: Time-series metric collection and storage
- alert_manager: Alert rules, channels, and deduplication
- dashboard_data: Metric aggregation and health scoring
- integration: Hooks for web, CLI, and middleware

Quick Start:
    from src.observability import metrics_collector, alert_manager
    from src.observability.integration import start_observability_monitoring

    # Start background monitoring
    start_observability_monitoring()

    # Track metrics manually
    metrics_collector.track_api_request(
        endpoint="/api/chat",
        method="POST",
        status_code=200,
        response_time_ms=1250.5,
    )
"""

__version__ = "1.0.0"

# Import main components
try:
    from .alert_manager import (
        Alert,
        AlertChannel,
        AlertManager,
        AlertRule,
        AlertSeverity,
        AlertStatus,
        alert_manager,
    )
    from .dashboard_data import (
        DashboardAggregator,
        HealthScore,
        TrendAnalysis,
        dashboard_aggregator,
        get_dashboard_data,
        get_health_score,
    )
    from .integration import (
        OBSERVABILITY_AVAILABLE,
        ObservabilityMiddleware,
        get_system_status,
        start_observability_monitoring,
        stop_observability_monitoring,
        track_cache_operation,
        track_cli_command,
        track_db_operation,
        track_llm_context,
        track_llm_wrapper,
        track_middleware_call,
        track_session_activity,
        track_session_end,
        track_session_start,
    )
    from .metrics_collector import (
        APIMetric,
        CacheMetric,
        DBMetric,
        LLMMetric,
        MetricsCollector,
        metrics_collector,
        track_api_request,
        track_cache_op,
        track_db_query,
        track_llm_call,
    )

    __all__ = [
        # Classes
        "MetricsCollector",
        "AlertManager",
        "DashboardAggregator",
        "ObservabilityMiddleware",
        "AlertRule",
        "Alert",
        "AlertSeverity",
        "AlertStatus",
        "AlertChannel",
        "HealthScore",
        "TrendAnalysis",
        "APIMetric",
        "LLMMetric",
        "DBMetric",
        "CacheMetric",
        # Singletons
        "metrics_collector",
        "alert_manager",
        "dashboard_aggregator",
        # Functions
        "track_api_request",
        "track_llm_call",
        "track_db_query",
        "track_cache_op",
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
        "get_dashboard_data",
        "get_health_score",
        # Constants
        "OBSERVABILITY_AVAILABLE",
        "__version__",
    ]

except ImportError as e:
    # Graceful degradation if dependencies are missing
    import warnings

    warnings.warn(f"Observability module not fully available: {e}")

    OBSERVABILITY_AVAILABLE = False

    # Define placeholders
    class _Unavailable:
        def __init__(self, *args, **kwargs):
            raise ImportError("Observability dependencies not available")

    MetricsCollector = _Unavailable
    AlertManager = _Unavailable
    DashboardAggregator = _Unavailable
    ObservabilityMiddleware = _Unavailable
    metrics_collector = None
    alert_manager = None
    dashboard_aggregator = None
