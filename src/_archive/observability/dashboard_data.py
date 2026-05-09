"""
Dashboard Data — Metric aggregation and trend analysis for Kitty AI observability.
Provides aggregated data for dashboards, trend analysis, and health score calculation.
"""

import json
import threading
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Try to import optional dependencies
try:
    import duckdb

    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False


@dataclass
class TrendAnalysis:
    """Trend analysis result."""

    metric_name: str
    current_value: float
    previous_value: float
    change_percent: float
    change_absolute: float
    trend: str  # 'up', 'down', 'stable'
    trend_strength: str  # 'weak', 'moderate', 'strong'


@dataclass
class HealthScore:
    """System health score."""

    overall_score: int  # 0-100
    category: str  # 'excellent', 'good', 'fair', 'poor', 'critical'
    api_health: int
    llm_health: int
    db_health: int
    system_health: int
    factors: list[dict[str, Any]]
    calculated_at: datetime


class DashboardAggregator:
    """
    Aggregates metrics for dashboard display and trend analysis.
    Provides health scores, top N lists, and time-series data.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._lock = threading.RLock()

        # Cache for expensive calculations
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._cache_ttl = timedelta(seconds=30)  # 30 second cache

    def _get_cached(self, key: str) -> Any | None:
        """Get cached value if still valid."""
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if datetime.now() - timestamp < self._cache_ttl:
                    return value
            return None

    def _set_cached(self, key: str, value: Any):
        """Cache a value."""
        with self._lock:
            self._cache[key] = (value, datetime.now())

    def _get_metrics_collector(self):
        """Get the metrics collector instance."""
        try:
            from .metrics_collector import metrics_collector

            return metrics_collector
        except ImportError:
            return None

    def _get_alert_manager(self):
        """Get the alert manager instance."""
        try:
            from .alert_manager import alert_manager

            return alert_manager
        except ImportError:
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    # Current Metrics
    # ═══════════════════════════════════════════════════════════════════════════

    def get_current_metrics(self) -> dict[str, Any]:
        """Get current metrics snapshot for dashboard."""
        cache_key = "current_metrics"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        collector = self._get_metrics_collector()
        alert_manager = self._get_alert_manager()

        metrics = {
            "timestamp": datetime.now().isoformat(),
            "api": {},
            "llm": {},
            "cache": {},
            "system": {},
            "alerts": {},
        }

        if collector:
            # API metrics (last 5 minutes)
            api_stats = collector.get_api_stats(minutes=5)
            metrics["api"] = {
                "requests_per_minute": api_stats.get("total_requests", 0) / 5,
                "avg_response_time_ms": api_stats.get("avg_response_time_ms", 0),
                "p95_response_time_ms": api_stats.get("p95_response_time_ms", 0),
                "error_rate_percent": api_stats.get("error_rate", 0),
                "active_users": api_stats.get("unique_users", 0),
            }

            # LLM metrics (last hour)
            llm_stats = collector.get_llm_stats(hours=1)
            metrics["llm"] = {
                "calls_per_hour": llm_stats.get("total_calls", 0),
                "avg_latency_ms": llm_stats.get("avg_latency_ms", 0),
                "total_cost_usd": llm_stats.get("total_cost_usd", 0),
                "error_count": llm_stats.get("error_count", 0),
                "cache_hit_rate": self._calculate_cache_hit_rate(collector, hours=1),
            }

            # Cache metrics
            cache_stats = collector.get_cache_stats(hours=1)
            metrics["cache"] = {
                "by_type": cache_stats,
                "overall_hit_rate": self._calculate_overall_cache_hit_rate(cache_stats),
            }

        # System metrics
        metrics["system"] = self._get_system_metrics()

        # Active alerts
        if alert_manager:
            active_alerts = alert_manager.get_active_alerts()
            metrics["alerts"] = {
                "active_count": len(active_alerts),
                "critical_count": sum(1 for a in active_alerts if a.severity.value == "critical"),
                "warning_count": sum(1 for a in active_alerts if a.severity.value == "warning"),
            }

        self._set_cached(cache_key, metrics)
        return metrics

    def _get_system_metrics(self) -> dict[str, Any]:
        """Get system resource metrics."""
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2),
            }
        except ImportError:
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "memory_available_gb": 0,
                "disk_percent": 0,
                "disk_free_gb": 0,
            }

    def _calculate_cache_hit_rate(self, collector, hours: int = 1) -> float:
        """Calculate overall cache hit rate."""
        cache_stats = collector.get_cache_stats(hours=hours)

        total_hits = sum(s.get("hits", 0) for s in cache_stats.values())
        total_misses = sum(s.get("misses", 0) for s in cache_stats.values())
        total = total_hits + total_misses

        return round(total_hits / total * 100, 2) if total > 0 else 0

    def _calculate_overall_cache_hit_rate(self, cache_stats: dict) -> float:
        """Calculate overall cache hit rate from stats dict."""
        total_hits = sum(s.get("hits", 0) for s in cache_stats.values())
        total_misses = sum(s.get("misses", 0) for s in cache_stats.values())
        total = total_hits + total_misses

        return round(total_hits / total * 100, 2) if total > 0 else 0

    # ═══════════════════════════════════════════════════════════════════════════
    # Historical Data
    # ═══════════════════════════════════════════════════════════════════════════

    def get_historical_metrics(
        self,
        metric_type: str,
        hours: int = 24,
        granularity: str = "hour",
    ) -> list[dict[str, Any]]:
        """
        Get historical metrics with specified granularity.

        Args:
            metric_type: 'api', 'llm', 'cache', or 'system'
            hours: Number of hours of history
            granularity: 'minute', 'hour', or 'day'
        """
        cache_key = f"hist_{metric_type}_{hours}_{granularity}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        collector = self._get_metrics_collector()
        if not collector:
            return []

        result = []
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        if metric_type == "api":
            result = self._get_api_historical(collector, start_time, end_time, granularity)
        elif metric_type == "llm":
            result = self._get_llm_historical(collector, start_time, end_time, granularity)
        elif metric_type == "cache":
            result = self._get_cache_historical(collector, start_time, end_time, granularity)

        self._set_cached(cache_key, result)
        return result

    def _get_api_historical(
        self,
        collector,
        start_time: datetime,
        end_time: datetime,
        granularity: str,
    ) -> list[dict[str, Any]]:
        """Get historical API metrics."""
        # Use DuckDB if available
        if DUCKDB_AVAILABLE and hasattr(collector, "conn") and collector.conn:
            trunc_func = (
                "DATE_TRUNC('hour', timestamp)"
                if granularity == "hour"
                else "DATE_TRUNC('minute', timestamp)"
            )

            results = collector.conn.execute(
                f"""
                SELECT
                    {trunc_func} as bucket,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time,
                    APPROX_QUANTILE(response_time_ms, 0.95) as p95_response_time,
                    SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count
                FROM api_metrics
                WHERE timestamp BETWEEN ? AND ?
                GROUP BY {trunc_func}
                ORDER BY bucket
            """,
                (start_time, end_time),
            ).fetchall()

            return [
                {
                    "timestamp": r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]),
                    "request_count": r[1],
                    "avg_response_time_ms": round(r[2] or 0, 2),
                    "p95_response_time_ms": round(r[3] or 0, 2),
                    "error_count": r[4],
                    "error_rate": round(r[4] / r[1] * 100, 2) if r[1] > 0 else 0,
                }
                for r in results
            ]

        return []

    def _get_llm_historical(
        self,
        collector,
        start_time: datetime,
        end_time: datetime,
        granularity: str,
    ) -> list[dict[str, Any]]:
        """Get historical LLM metrics."""
        if DUCKDB_AVAILABLE and hasattr(collector, "conn") and collector.conn:
            trunc_func = (
                "DATE_TRUNC('hour', timestamp)"
                if granularity == "hour"
                else "DATE_TRUNC('minute', timestamp)"
            )

            results = collector.conn.execute(
                f"""
                SELECT
                    {trunc_func} as bucket,
                    COUNT(*) as call_count,
                    SUM(tokens_in) as total_tokens_in,
                    SUM(tokens_out) as total_tokens_out,
                    AVG(latency_ms) as avg_latency,
                    SUM(cost_usd) as total_cost,
                    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as error_count
                FROM llm_metrics
                WHERE timestamp BETWEEN ? AND ?
                GROUP BY {trunc_func}
                ORDER BY bucket
            """,
                (start_time, end_time),
            ).fetchall()

            return [
                {
                    "timestamp": r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]),
                    "call_count": r[1],
                    "total_tokens_in": r[2],
                    "total_tokens_out": r[3],
                    "avg_latency_ms": round(r[4] or 0, 2),
                    "total_cost_usd": round(r[5] or 0, 4),
                    "error_count": r[6],
                }
                for r in results
            ]

        return []

    def _get_cache_historical(
        self,
        collector,
        start_time: datetime,
        end_time: datetime,
        granularity: str,
    ) -> list[dict[str, Any]]:
        """Get historical cache metrics."""
        if DUCKDB_AVAILABLE and hasattr(collector, "conn") and collector.conn:
            trunc_func = (
                "DATE_TRUNC('hour', timestamp)"
                if granularity == "hour"
                else "DATE_TRUNC('minute', timestamp)"
            )

            results = collector.conn.execute(
                f"""
                SELECT
                    {trunc_func} as bucket,
                    cache_type,
                    SUM(CASE WHEN operation = 'hit' THEN 1 ELSE 0 END) as hits,
                    SUM(CASE WHEN operation = 'miss' THEN 1 ELSE 0 END) as misses
                FROM cache_metrics
                WHERE timestamp BETWEEN ? AND ?
                GROUP BY {trunc_func}, cache_type
                ORDER BY bucket, cache_type
            """,
                (start_time, end_time),
            ).fetchall()

            # Aggregate by bucket
            bucket_stats = defaultdict(lambda: {"hits": 0, "misses": 0})
            for r in results:
                bucket = r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0])
                bucket_stats[bucket]["hits"] += r[2] or 0
                bucket_stats[bucket]["misses"] += r[3] or 0

            return [
                {
                    "timestamp": bucket,
                    "hits": stats["hits"],
                    "misses": stats["misses"],
                    "hit_rate": round(stats["hits"] / (stats["hits"] + stats["misses"]) * 100, 2)
                    if (stats["hits"] + stats["misses"]) > 0
                    else 0,
                }
                for bucket, stats in sorted(bucket_stats.items())
            ]

        return []

    # ═══════════════════════════════════════════════════════════════════════════
    # Trend Analysis
    # ═══════════════════════════════════════════════════════════════════════════

    def analyze_trend(
        self,
        metric_name: str,
        current_window_hours: int = 1,
        previous_window_hours: int = 1,
    ) -> TrendAnalysis:
        """
        Analyze trend for a metric comparing current vs previous window.

        Returns TrendAnalysis with trend direction and strength.
        """
        collector = self._get_metrics_collector()

        current_value = 0
        previous_value = 0

        if metric_name == "api_requests":
            current = (
                collector.get_api_stats(minutes=current_window_hours * 60) if collector else {}
            )
            datetime.now() - timedelta(
                hours=current_window_hours + previous_window_hours
            )
            datetime.now() - timedelta(hours=current_window_hours)
            # This would need more sophisticated querying for historical windows
            current_value = current.get("total_requests", 0)
            previous_value = current_value  # Placeholder

        elif metric_name == "llm_cost":
            current = collector.get_llm_stats(hours=current_window_hours) if collector else {}
            current_value = current.get("total_cost_usd", 0)
            previous_value = current_value  # Placeholder

        elif metric_name == "error_rate":
            current = (
                collector.get_api_stats(minutes=current_window_hours * 60) if collector else {}
            )
            current_value = current.get("error_rate", 0)
            previous_value = current_value  # Placeholder

        # Calculate change
        change_absolute = current_value - previous_value
        change_percent = (change_absolute / previous_value * 100) if previous_value != 0 else 0

        # Determine trend
        if abs(change_percent) < 5:
            trend = "stable"
        elif change_percent > 0:
            trend = "up"
        else:
            trend = "down"

        # Determine strength
        abs_change = abs(change_percent)
        if abs_change < 10:
            trend_strength = "weak"
        elif abs_change < 30:
            trend_strength = "moderate"
        else:
            trend_strength = "strong"

        return TrendAnalysis(
            metric_name=metric_name,
            current_value=current_value,
            previous_value=previous_value,
            change_percent=round(change_percent, 2),
            change_absolute=round(change_absolute, 4),
            trend=trend,
            trend_strength=trend_strength,
        )

    def get_trends(self, metrics: list[str] = None) -> dict[str, TrendAnalysis]:
        """Get trend analysis for multiple metrics."""
        if metrics is None:
            metrics = ["api_requests", "llm_cost", "error_rate", "avg_latency"]

        trends = {}
        for metric in metrics:
            try:
                trends[metric] = self.analyze_trend(metric)
            except Exception:
                trends[metric] = TrendAnalysis(
                    metric_name=metric,
                    current_value=0,
                    previous_value=0,
                    change_percent=0,
                    change_absolute=0,
                    trend="unknown",
                    trend_strength="weak",
                )

        return trends

    # ═══════════════════════════════════════════════════════════════════════════
    # Top N Analysis
    # ═══════════════════════════════════════════════════════════════════════════

    def get_slowest_endpoints(self, minutes: int = 60, limit: int = 10) -> list[dict[str, Any]]:
        """Get top N slowest endpoints by average response time."""
        collector = self._get_metrics_collector()
        if not collector:
            return []

        endpoints = collector.get_endpoint_stats(minutes=minutes, limit=limit * 2)

        # Sort by average response time (descending)
        sorted_endpoints = sorted(
            endpoints,
            key=lambda e: e.get("avg_response_time_ms", 0),
            reverse=True,
        )

        return sorted_endpoints[:limit]

    def get_error_prone_endpoints(self, minutes: int = 60, limit: int = 10) -> list[dict[str, Any]]:
        """Get top N error-prone endpoints by error rate."""
        collector = self._get_metrics_collector()
        if not collector:
            return []

        endpoints = collector.get_endpoint_stats(minutes=minutes, limit=limit * 2)

        # Calculate error rate and sort
        for endpoint in endpoints:
            total = endpoint.get("request_count", 0)
            errors = endpoint.get("error_count", 0)
            endpoint["error_rate"] = round(errors / total * 100, 2) if total > 0 else 0

        sorted_endpoints = sorted(
            endpoints,
            key=lambda e: e.get("error_rate", 0),
            reverse=True,
        )

        return sorted_endpoints[:limit]

    def get_top_models(self, hours: int = 24, limit: int = 10) -> list[dict[str, Any]]:
        """Get top N models by usage."""
        collector = self._get_metrics_collector()
        if not collector or not DUCKDB_AVAILABLE:
            return []

        try:
            results = collector.conn.execute(
                """
                SELECT
                    model,
                    COUNT(*) as call_count,
                    SUM(tokens_in) as total_tokens_in,
                    SUM(tokens_out) as total_tokens_out,
                    SUM(cost_usd) as total_cost,
                    AVG(latency_ms) as avg_latency
                FROM llm_metrics
                WHERE timestamp >= ?
                GROUP BY model
                ORDER BY call_count DESC
                LIMIT ?
            """,
                (datetime.now() - timedelta(hours=hours), limit),
            ).fetchall()

            return [
                {
                    "model": r[0],
                    "call_count": r[1],
                    "total_tokens_in": r[2],
                    "total_tokens_out": r[3],
                    "total_cost_usd": round(r[4] or 0, 4),
                    "avg_latency_ms": round(r[5] or 0, 2),
                }
                for r in results
            ]
        except Exception:
            return []

    def get_top_features(self, hours: int = 24, limit: int = 10) -> list[dict[str, Any]]:
        """Get top N features by usage."""
        collector = self._get_metrics_collector()
        if not collector or not DUCKDB_AVAILABLE:
            return []

        try:
            results = collector.conn.execute(
                """
                SELECT
                    feature,
                    COUNT(*) as call_count,
                    SUM(cost_usd) as total_cost,
                    AVG(latency_ms) as avg_latency
                FROM llm_metrics
                WHERE timestamp >= ?
                GROUP BY feature
                ORDER BY call_count DESC
                LIMIT ?
            """,
                (datetime.now() - timedelta(hours=hours), limit),
            ).fetchall()

            return [
                {
                    "feature": r[0],
                    "call_count": r[1],
                    "total_cost_usd": round(r[2] or 0, 4),
                    "avg_latency_ms": round(r[3] or 0, 2),
                }
                for r in results
            ]
        except Exception:
            return []

    # ═══════════════════════════════════════════════════════════════════════════
    # Health Score
    # ═══════════════════════════════════════════════════════════════════════════

    def calculate_health_score(self) -> HealthScore:
        """
        Calculate overall system health score (0-100).

        Factors:
        - API response times
        - Error rates
        - LLM performance
        - System resources
        - Active alerts
        """
        cache_key = "health_score"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        collector = self._get_metrics_collector()
        alert_manager = self._get_alert_manager()

        factors = []
        api_health = 100
        llm_health = 100
        db_health = 100
        system_health = 100

        # API Health (weight: 35%)
        if collector:
            api_stats = collector.get_api_stats(minutes=5)

            # Error rate factor (0-40 points)
            error_rate = api_stats.get("error_rate", 0)
            if error_rate > 10:
                api_health -= 40
                factors.append(
                    {
                        "category": "api",
                        "name": "High Error Rate",
                        "impact": -40,
                        "value": f"{error_rate:.1f}%",
                    }
                )
            elif error_rate > 5:
                api_health -= 20
                factors.append(
                    {
                        "category": "api",
                        "name": "Elevated Error Rate",
                        "impact": -20,
                        "value": f"{error_rate:.1f}%",
                    }
                )
            elif error_rate > 1:
                api_health -= 5
                factors.append(
                    {
                        "category": "api",
                        "name": "Minor Error Rate",
                        "impact": -5,
                        "value": f"{error_rate:.1f}%",
                    }
                )

            # Response time factor (0-35 points)
            avg_latency = api_stats.get("avg_response_time_ms", 0)
            if avg_latency > 5000:
                api_health -= 35
                factors.append(
                    {
                        "category": "api",
                        "name": "Very High Latency",
                        "impact": -35,
                        "value": f"{avg_latency:.0f}ms",
                    }
                )
            elif avg_latency > 2000:
                api_health -= 20
                factors.append(
                    {
                        "category": "api",
                        "name": "High Latency",
                        "impact": -20,
                        "value": f"{avg_latency:.0f}ms",
                    }
                )
            elif avg_latency > 1000:
                api_health -= 10
                factors.append(
                    {
                        "category": "api",
                        "name": "Elevated Latency",
                        "impact": -10,
                        "value": f"{avg_latency:.0f}ms",
                    }
                )

            # LLM Health (weight: 25%)
            llm_stats = collector.get_llm_stats(hours=1)

            # LLM error rate
            llm_calls = llm_stats.get("total_calls", 0)
            llm_errors = llm_stats.get("error_count", 0)
            llm_error_rate = (llm_errors / llm_calls * 100) if llm_calls > 0 else 0

            if llm_error_rate > 20:
                llm_health -= 40
                factors.append(
                    {
                        "category": "llm",
                        "name": "High LLM Error Rate",
                        "impact": -40,
                        "value": f"{llm_error_rate:.1f}%",
                    }
                )
            elif llm_error_rate > 10:
                llm_health -= 20
                factors.append(
                    {
                        "category": "llm",
                        "name": "Elevated LLM Error Rate",
                        "impact": -20,
                        "value": f"{llm_error_rate:.1f}%",
                    }
                )

            # LLM latency
            llm_latency = llm_stats.get("avg_latency_ms", 0)
            if llm_latency > 10000:
                llm_health -= 30
                factors.append(
                    {
                        "category": "llm",
                        "name": "Very High LLM Latency",
                        "impact": -30,
                        "value": f"{llm_latency:.0f}ms",
                    }
                )
            elif llm_latency > 5000:
                llm_health -= 15
                factors.append(
                    {
                        "category": "llm",
                        "name": "High LLM Latency",
                        "impact": -15,
                        "value": f"{llm_latency:.0f}ms",
                    }
                )

        # System Health (weight: 20%)
        try:
            import psutil

            # Memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 95:
                system_health -= 40
                factors.append(
                    {
                        "category": "system",
                        "name": "Critical Memory Usage",
                        "impact": -40,
                        "value": f"{memory.percent:.1f}%",
                    }
                )
            elif memory.percent > 90:
                system_health -= 25
                factors.append(
                    {
                        "category": "system",
                        "name": "High Memory Usage",
                        "impact": -25,
                        "value": f"{memory.percent:.1f}%",
                    }
                )
            elif memory.percent > 80:
                system_health -= 10
                factors.append(
                    {
                        "category": "system",
                        "name": "Elevated Memory Usage",
                        "impact": -10,
                        "value": f"{memory.percent:.1f}%",
                    }
                )

            # Disk usage
            disk = psutil.disk_usage("/")
            if disk.percent > 95:
                system_health -= 40
                factors.append(
                    {
                        "category": "system",
                        "name": "Critical Disk Usage",
                        "impact": -40,
                        "value": f"{disk.percent:.1f}%",
                    }
                )
            elif disk.percent > 90:
                system_health -= 25
                factors.append(
                    {
                        "category": "system",
                        "name": "High Disk Usage",
                        "impact": -25,
                        "value": f"{disk.percent:.1f}%",
                    }
                )
            elif disk.percent > 80:
                system_health -= 10
                factors.append(
                    {
                        "category": "system",
                        "name": "Elevated Disk Usage",
                        "impact": -10,
                        "value": f"{disk.percent:.1f}%",
                    }
                )

            # CPU usage (check if consistently high)
            cpu = psutil.cpu_percent(interval=0.1)
            if cpu > 95:
                system_health -= 20
                factors.append(
                    {
                        "category": "system",
                        "name": "High CPU Usage",
                        "impact": -20,
                        "value": f"{cpu:.1f}%",
                    }
                )
            elif cpu > 85:
                system_health -= 10
                factors.append(
                    {
                        "category": "system",
                        "name": "Elevated CPU Usage",
                        "impact": -10,
                        "value": f"{cpu:.1f}%",
                    }
                )

        except ImportError:
            pass

        # Active Alerts Impact (weight: 20%)
        if alert_manager:
            active_alerts = alert_manager.get_active_alerts()
            critical_count = sum(1 for a in active_alerts if a.severity.value == "critical")
            warning_count = sum(1 for a in active_alerts if a.severity.value == "warning")

            if critical_count > 0:
                db_health -= min(50, critical_count * 25)
                factors.append(
                    {
                        "category": "alerts",
                        "name": "Active Critical Alerts",
                        "impact": -min(50, critical_count * 25),
                        "value": str(critical_count),
                    }
                )

            if warning_count > 0:
                db_health -= min(20, warning_count * 5)
                factors.append(
                    {
                        "category": "alerts",
                        "name": "Active Warning Alerts",
                        "impact": -min(20, warning_count * 5),
                        "value": str(warning_count),
                    }
                )

        # Ensure health scores are within bounds
        api_health = max(0, min(100, api_health))
        llm_health = max(0, min(100, llm_health))
        db_health = max(0, min(100, db_health))
        system_health = max(0, min(100, system_health))

        # Calculate weighted overall score
        overall_score = int(
            api_health * 0.35 + llm_health * 0.25 + db_health * 0.20 + system_health * 0.20
        )

        # Determine category
        if overall_score >= 90:
            category = "excellent"
        elif overall_score >= 75:
            category = "good"
        elif overall_score >= 50:
            category = "fair"
        elif overall_score >= 25:
            category = "poor"
        else:
            category = "critical"

        health_score = HealthScore(
            overall_score=overall_score,
            category=category,
            api_health=api_health,
            llm_health=llm_health,
            db_health=db_health,
            system_health=system_health,
            factors=factors,
            calculated_at=datetime.now(),
        )

        self._set_cached(cache_key, health_score)
        return health_score

    # ═══════════════════════════════════════════════════════════════════════════
    # Dashboard Data Export
    # ═══════════════════════════════════════════════════════════════════════════

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get complete dashboard data package."""
        return {
            "timestamp": datetime.now().isoformat(),
            "current_metrics": self.get_current_metrics(),
            "health_score": asdict(self.calculate_health_score()),
            "trends": {name: asdict(trend) for name, trend in self.get_trends().items()},
            "top_slow_endpoints": self.get_slowest_endpoints(limit=10),
            "top_error_endpoints": self.get_error_prone_endpoints(limit=10),
            "top_models": self.get_top_models(limit=10),
            "top_features": self.get_top_features(limit=10),
            "historical": {
                "api": self.get_historical_metrics("api", hours=24, granularity="hour"),
                "llm": self.get_historical_metrics("llm", hours=24, granularity="hour"),
            },
        }

    def export_dashboard_data(self, output_path: str | None = None) -> str:
        """Export dashboard data to JSON file."""
        data = self.get_dashboard_data()

        if output_path is None:
            output_path = (
                Path(__file__).parent.parent.parent
                / "data"
                / "observability"
                / f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        return str(output_path)


# Global singleton instance
dashboard_aggregator = DashboardAggregator()


def get_dashboard_data() -> dict[str, Any]:
    """Convenience function to get dashboard data."""
    return dashboard_aggregator.get_dashboard_data()


def get_health_score() -> HealthScore:
    """Convenience function to get health score."""
    return dashboard_aggregator.calculate_health_score()


if __name__ == "__main__":
    # Demo/test
    print("Dashboard Aggregator Demo")
    print("=" * 50)

    aggregator = DashboardAggregator()

    # Show current metrics
    print("\nCurrent Metrics:")
    metrics = aggregator.get_current_metrics()
    print(json.dumps(metrics, indent=2, default=str))

    # Show health score
    print("\nHealth Score:")
    health = aggregator.calculate_health_score()
    print(f"  Overall: {health.overall_score}/100 ({health.category})")
    print(f"  API Health: {health.api_health}/100")
    print(f"  LLM Health: {health.llm_health}/100")
    print(f"  System Health: {health.system_health}/100")

    # Show trends
    print("\nTrends:")
    trends = aggregator.get_trends()
    for name, trend in trends.items():
        print(f"  {name}: {trend.trend} ({trend.change_percent:+.1f}%)")
