"""
Specialist Performance Metrics Tracking
Tracks query count, success rate, avg response time, token usage, cost, and errors by type.
"""

import json
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

# Model pricing constants (per 1M tokens)
MODEL_PRICING = {
    "claude-3-5-sonnet-20241022": {"input": 15.0, "output": 75.0},
    "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "google/gemini-2.0-flash-001": {"input": 0.0, "output": 0.0},
    "google/gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
}


def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate cost in USD for given token counts."""
    pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
    return (tokens_in / 1_000_000 * pricing["input"]) + (tokens_out / 1_000_000 * pricing["output"])


@dataclass
class SpecialistMetric:
    """Individual query metric for a specialist."""

    specialist: str
    domain: str
    query: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    latency_ms: float = 0.0
    success: bool = True
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    error_type: str | None = None
    model: str = "unknown"


@dataclass
class SpecialistSummary:
    """Aggregated metrics for a specialist with online update."""

    specialist: str
    domain: str
    query_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost: float = 0.0
    total_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.query_count == 0:
            return 0.0
        return self.success_count / self.query_count

    @property
    def avg_latency_ms(self) -> float:
        if self.query_count == 0:
            return 0.0
        return self.total_latency_ms / self.query_count

    @property
    def avg_tokens(self) -> float:
        if self.query_count == 0:
            return 0.0
        return (self.total_tokens_in + self.total_tokens_out) / self.query_count

    @property
    def avg_cost(self) -> float:
        if self.query_count == 0:
            return 0.0
        return self.total_cost / self.query_count

    def update(self, metric: SpecialistMetric) -> None:
        """Online update with running averages."""
        self.query_count += 1
        self.total_latency_ms += metric.latency_ms
        self.total_tokens_in += metric.tokens_in
        self.total_tokens_out += metric.tokens_out
        self.total_cost += metric.cost

        if metric.success:
            self.success_count += 1
        else:
            self.error_count += 1


class SpecialistMetrics:
    """
    Thread-safe specialist performance metrics tracker.

    Tracks: query count, success rate, avg response time, token usage, cost, errors by type.
    Supports time-window filtering (1h, 24h, 7d).
    """

    SPECIALISTS = {
        "Alex": "audio_electronics",
        "Kelly": "fitness",
        "Mike": "automotive",
        "Taylor": "self_help",
        "Kitty Coder": "code",
    }

    def __init__(self):
        self._lock = threading.RLock()
        self._metrics: list[SpecialistMetric] = []
        self._summaries: dict[str, SpecialistSummary] = {}
        self._error_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._domain_routing: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Initialize summaries for all specialists
        for specialist, domain in self.SPECIALISTS.items():
            self._summaries[specialist] = SpecialistSummary(specialist=specialist, domain=domain)

    def record_query(
        self,
        specialist: str,
        domain: str,
        query: str,
        latency_ms: float = 0.0,
        success: bool = True,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost: float = 0.0,
        error_type: str | None = None,
        model: str = "unknown",
    ) -> None:
        """
        Record a query for a specialist.

        Args:
            specialist: Specialist name (Alex, Kelly, Mike, Taylor, Devin)
            domain: Domain (audio_electronics, fitness, automotive, self_help, code)
            query: User query text
            latency_ms: Response time in milliseconds
            success: Whether query succeeded
            tokens_in: Input tokens
            tokens_out: Output tokens
            cost: Calculated cost in USD
            error_type: Error type if failed
            model: Model used
        """
        with self._lock:
            # Create metric record
            metric = SpecialistMetric(
                specialist=specialist,
                domain=domain,
                query=query,
                latency_ms=latency_ms,
                success=success,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost=cost,
                error_type=error_type,
                model=model,
            )

            self._metrics.append(metric)

            # Update summary - ensure specialist exists
            if specialist not in self._summaries:
                self._summaries[specialist] = SpecialistSummary(
                    specialist=specialist, domain=domain
                )
            self._summaries[specialist].update(metric)

            # Track errors by type
            if not success and error_type:
                self._error_counts[specialist][error_type] += 1

            # Track routing decisions
            self._domain_routing[specialist][domain] += 1

    def get_stats(
        self,
        specialist: str | None = None,
        time_window: str | None = None,
    ) -> dict[str, Any]:
        """
        Get aggregated stats.

        Args:
            specialist: Specific specialist or None for all
            time_window: "1h", "24h", "7d", or None for alltime

        Returns:
            Dict with stats by specialist
        """
        with self._lock:
            # Filter by time window if specified
            metrics = self._filter_by_time_window(time_window)

            if specialist:
                return self._get_specialist_stats(specialist, metrics)

            # Return all specialists
            result = {}
            for spec in self.SPECIALISTS.keys():
                result[spec] = self._get_specialist_stats(spec, metrics)
            return result

    def _filter_by_time_window(self, time_window: str | None) -> list[SpecialistMetric]:
        """Filter metrics by time window."""
        if time_window is None:
            return self._metrics

        now = datetime.now()
        windows = {"1h": 1, "24h": 24, "7d": 7}
        hours = windows.get(time_window, 0)
        cutoff = now - timedelta(hours=hours)

        return [m for m in self._metrics if datetime.fromisoformat(m.timestamp) >= cutoff]

    def _get_specialist_stats(
        self, specialist: str, metrics: list[SpecialistMetric]
    ) -> dict[str, Any]:
        """Get stats for a specific specialist."""
        spec_metrics = [m for m in metrics if m.specialist == specialist]

        if not spec_metrics:
            return {
                "specialist": specialist,
                "query_count": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "errors": {},
            }

        total_tokens = sum(m.tokens_in + m.tokens_out for m in spec_metrics)
        total_cost = sum(m.cost for m in spec_metrics)
        success_count = sum(1 for m in spec_metrics if m.success)
        error_counts = defaultdict(int)
        for m in spec_metrics:
            if not m.success and m.error_type:
                error_counts[m.error_type] += 1

        return {
            "specialist": specialist,
            "domain": self.SPECIALISTS.get(specialist, "unknown"),
            "query_count": len(spec_metrics),
            "success_rate": success_count / len(spec_metrics),
            "avg_latency_ms": sum(m.latency_ms for m in spec_metrics) / len(spec_metrics),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "errors": dict(error_counts),
            "models_used": list(set(m.model for m in spec_metrics if m.model != "unknown")),
        }

    def get_cost_breakdown(self, time_window: str | None = None) -> dict[str, dict[str, float]]:
        """Get cost breakdown by domain."""
        with self._lock:
            metrics = self._filter_by_time_window(time_window)

            breakdown: dict[str, dict[str, float]] = defaultdict(
                lambda: {"total": 0.0, "queries": 0}
            )

            for m in metrics:
                domain = m.domain
                breakdown[domain]["total"] += m.cost
                breakdown[domain]["queries"] += 1

            return {k: v for k, v in breakdown.items()}

    def get_routing_stats(self) -> dict[str, dict[str, int]]:
        """Get routing decision statistics by specialist."""
        with self._lock:
            return {k: dict(v) for k, v in self._domain_routing.items()}

    def export_json(self, time_window: str | None = None, include_metrics: bool = False) -> str:
        """
        Export metrics as JSON.

        Args:
            time_window: Filter by time window
            include_metrics: Include individual metric records

        Returns:
            JSON string
        """
        with self._lock:
            data = {
                "exported_at": datetime.now().isoformat(),
                "time_window": time_window or "alltime",
                "specialists": self.get_stats(time_window=time_window),
                "cost_breakdown": self.get_cost_breakdown(time_window),
                "routing_stats": self.get_routing_stats(),
            }

            if include_metrics:
                metrics = self._filter_by_time_window(time_window)
                data["metrics"] = [
                    {
                        "specialist": m.specialist,
                        "domain": m.domain,
                        "query": m.query[:100] + "..." if len(m.query) > 100 else m.query,
                        "timestamp": m.timestamp,
                        "latency_ms": m.latency_ms,
                        "success": m.success,
                        "tokens_in": m.tokens_in,
                        "tokens_out": m.tokens_out,
                        "cost": m.cost,
                        "error_type": m.error_type,
                        "model": m.model,
                    }
                    for m in metrics
                ]

            return json.dumps(data, indent=2)

    def get_performance_summary(self, time_window: str | None = None) -> dict[str, Any]:
        """Get overall performance summary."""
        with self._lock:
            stats = self.get_stats(time_window=time_window)
            costs = self.get_cost_breakdown(time_window)

            total_queries = sum(s["query_count"] for s in stats.values())
            total_cost = sum(c["total"] for c in costs.values())

            avg_success_rate = 0.0
            avg_latency = 0.0

            if total_queries > 0:
                successes = sum(s["success_count"] for s in self._summaries.values())
                avg_success_rate = successes / total_queries
                avg_latency = (
                    sum(s.total_latency_ms for s in self._summaries.values()) / total_queries
                )

            return {
                "time_window": time_window or "alltime",
                "total_queries": total_queries,
                "success_rate": avg_success_rate,
                "avg_latency_ms": avg_latency,
                "total_cost": total_cost,
                "specialist_count": len(stats),
            }

    def clear(self) -> None:
        """Clear all metrics (for testing)."""
        with self._lock:
            self._metrics.clear()
            self._error_counts.clear()
            self._domain_routing.clear()
            for summary in self._summaries.values():
                summary.query_count = 0
                summary.success_count = 0
                summary.error_count = 0
                summary.total_tokens_in = 0
                summary.total_tokens_out = 0
                summary.total_cost = 0.0
                summary.total_latency_ms = 0.0


# Global singleton
_specialist_metrics: SpecialistMetrics | None = None
_metrics_lock = threading.Lock()


def get_specialist_metrics() -> SpecialistMetrics:
    """Get global SpecialistMetrics singleton."""
    global _specialist_metrics
    if _specialist_metrics is None:
        with _metrics_lock:
            if _specialist_metrics is None:
                _specialist_metrics = SpecialistMetrics()
    return _specialist_metrics


# Demo
if __name__ == "__main__":
    print("Specialist Metrics Tracking Demo")
    print("=" * 50)

    metrics = SpecialistMetrics()

    # Record sample queries
    test_queries = [
        (
            "Alex",
            "audio_electronics",
            "My tube amp is buzzing",
            245.3,
            True,
            120,
            340,
            0.012,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Alex",
            "audio_electronics",
            "Capacitor replacement",
            189.2,
            True,
            85,
            210,
            0.008,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Kelly",
            "fitness",
            "Squat form check",
            312.5,
            True,
            150,
            420,
            0.015,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Mike",
            "automotive",
            "Car won't start",
            278.1,
            True,
            130,
            380,
            0.014,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Taylor",
            "self_help",
            "Feeling anxious",
            198.4,
            True,
            100,
            290,
            0.010,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Devin",
            "code",
            "Python bug fix",
            356.2,
            True,
            180,
            510,
            0.018,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Alex",
            "audio_electronics",
            "Circuit troubleshooting",
            0.0,
            False,
            50,
            0,
            0.0,
            "TimeoutError",
            "claude-3-5-sonnet-20241022",
        ),
    ]

    for spec, domain, query, latency, success, tin, tout, cost, err, model in test_queries:
        metrics.record_query(
            specialist=spec,
            domain=domain,
            query=query,
            latency_ms=latency,
            success=success,
            tokens_in=tin,
            tokens_out=tout,
            cost=cost,
            error_type=err,
            model=model,
        )

    # Get stats
    print("\nAll Specialists (alltime):")
    print("-" * 50)
    for spec, stats in metrics.get_stats().items():
        print(f"\n{spec} ({stats['domain']}):")
        print(f"  Queries: {stats['query_count']}")
        print(f"  Success Rate: {stats['success_rate']:.1%}")
        print(f"  Avg Latency: {stats['avg_latency_ms']:.1f}ms")
        print(f"  Total Cost: ${stats['total_cost']:.4f}")
        if stats["errors"]:
            print(f"  Errors: {stats['errors']}")

    # Cost breakdown
    print("\n\nCost Breakdown by Domain:")
    print("-" * 50)
    for domain, costs in metrics.get_cost_breakdown().items():
        print(f"  {domain}: ${costs['total']:.4f} ({costs['queries']} queries)")

    # Export JSON
    print("\n\nJSON Export (abbreviated):")
    print("-" * 50)
    json_data = json.loads(metrics.export_json())
    print(f"Total queries: {json_data['specialists']['Alex']['query_count']}")
    print(f"Total cost: ${sum(s['total_cost'] for s in json_data['specialists'].values()):.4f}")

    print("\n✅ Specialist Metrics tracking ready!")
