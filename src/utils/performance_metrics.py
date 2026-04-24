"""
Performance Metrics Utility for Persona Testing

Standalone module for tracking, aggregating, and reporting performance
metrics from persona-based test runs. Designed to be imported by
agents/swarm_test_runner.py and any other test harnesses.

Usage:
    from src.utils.performance_metrics import PerformanceMetrics, QueryMetric

    pm = PerformanceMetrics()
    pm.record(QueryMetric(persona="hobbyist", query="...", latency_ms=320.5, success=True))
    print(pm.summary_report())
    pm.save("data/test_results/metrics.json")
"""

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Model pricing table (input_per_1k, output_per_1k) in USD
# ---------------------------------------------------------------------------
MODEL_PRICING: dict[str, tuple] = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-haiku": (0.00025, 0.00125),
    "google/gemini-2.0-flash": (0.0001, 0.0004),
    "google/gemini-1.5-flash": (0.000075, 0.0003),
    "openrouter/free": (0.0, 0.0),
    "google/gemini-2.0-flash-exp:free": (0.0, 0.0),
    "meta-llama/llama-3.3-70b-instruct:free": (0.0, 0.0),
    "qwen/qwen3-coder:free": (0.0, 0.0),
    "deepseek/deepseek-chat": (0.00014, 0.00028),
    "meta-llama/llama-3.1-70b": (0.00052, 0.00075),
    "ollama": (0.0, 0.0),
    "local": (0.0, 0.0),
}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate USD cost for a request given model and token counts."""
    model_key = model.lower()
    for key, (price_in, price_out) in MODEL_PRICING.items():
        if key.lower() in model_key:
            return (tokens_in / 1000) * price_in + (tokens_out / 1000) * price_out
    return 0.0  # unknown model = free (local/unknown)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class QueryMetric:
    """Metrics for a single query execution."""

    persona: str
    query: str
    latency_ms: float
    success: bool
    response: str = ""
    model: str = "unknown"
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    time_to_first_token_ms: float = 0.0
    accuracy_score: float | None = None  # 0.0–1.0 when ground truth available
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class PersonaSummary:
    """Aggregated metrics for one persona type."""

    persona: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    avg_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0
    avg_ttft_ms: float = 0.0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost: float = 0.0
    avg_accuracy: float | None = None
    _accuracy_count: int = field(default=0, repr=False)

    def update(self, m: QueryMetric) -> None:
        """Incorporate a new QueryMetric into this summary (online update)."""
        self.total += 1
        if m.success:
            self.passed += 1
        else:
            self.failed += 1

        # Latency
        self.min_latency_ms = min(self.min_latency_ms, m.latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, m.latency_ms)
        self.avg_latency_ms += (m.latency_ms - self.avg_latency_ms) / self.total

        # TTFT
        if m.time_to_first_token_ms > 0:
            self.avg_ttft_ms += (m.time_to_first_token_ms - self.avg_ttft_ms) / self.total

        # Tokens / cost
        self.total_tokens_in += m.tokens_in
        self.total_tokens_out += m.tokens_out
        self.total_cost += m.cost

        # Accuracy (only when ground truth provided)
        if m.accuracy_score is not None:
            self._accuracy_count += 1
            prev = self.avg_accuracy or 0.0
            self.avg_accuracy = prev + (m.accuracy_score - prev) / self._accuracy_count

    @property
    def success_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0


# ---------------------------------------------------------------------------
# Main collector
# ---------------------------------------------------------------------------


class PerformanceMetrics:
    """
    Collects and aggregates performance metrics across persona test runs.

    Thread-safe for sequential use. For concurrent use, wrap add() calls
    with an external lock.
    """

    def __init__(self) -> None:
        self._queries: list[QueryMetric] = []
        self._summaries: dict[str, PersonaSummary] = {}
        self._started_at: str = datetime.now().isoformat()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, metric: QueryMetric) -> None:
        """Record a single query metric."""
        self._queries.append(metric)
        if metric.persona not in self._summaries:
            self._summaries[metric.persona] = PersonaSummary(persona=metric.persona)
        self._summaries[metric.persona].update(metric)

    def record_timed(
        self,
        persona: str,
        query: str,
        fn,
        model: str = "unknown",
        ground_truth: str | None = None,
    ) -> QueryMetric:
        """
        Execute fn() while measuring latency, then record the result.

        Args:
            persona: Persona name
            query: Query string
            fn: Callable() -> str  (the LLM call)
            model: Model identifier for cost calculation
            ground_truth: Expected answer for accuracy scoring (optional)

        Returns:
            The recorded QueryMetric
        """
        start = time.perf_counter()
        error = None
        response = ""
        success = False

        try:
            response = fn()
            success = True
        except Exception as exc:
            error = str(exc)[:200]

        latency_ms = (time.perf_counter() - start) * 1000
        tokens_in = len(query) // 4
        tokens_out = len(response) // 4
        cost = estimate_cost(model, tokens_in, tokens_out)

        accuracy = None
        if ground_truth and response:
            accuracy = _simple_accuracy(response, ground_truth)

        m = QueryMetric(
            persona=persona,
            query=query,
            latency_ms=latency_ms,
            success=success,
            response=response,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            accuracy_score=accuracy,
            error=error,
        )
        self.record(m)
        return m

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary_report(self) -> str:
        """Return a human-readable summary report."""
        lines = [
            "=" * 70,
            "PERSONA TESTING — PERFORMANCE METRICS REPORT",
            "=" * 70,
            f"Generated : {datetime.now().isoformat()}",
            f"Started   : {self._started_at}",
            "",
            f"Total queries : {len(self._queries)}",
            f"Unique personas: {len(self._summaries)}",
            "",
            "-" * 70,
            "BY PERSONA",
            "-" * 70,
        ]

        grand_cost = 0.0
        grand_in = grand_out = 0

        for name, s in sorted(self._summaries.items()):
            lines += [
                f"\n{name}",
                f"  Queries   : {s.total}  (✓ {s.passed}  ✗ {s.failed}  {s.success_rate:.0%})",
                f"  Latency   : avg {s.avg_latency_ms:.1f}ms  "
                f"min {s.min_latency_ms:.1f}ms  max {s.max_latency_ms:.1f}ms",
                f"  TTFT      : avg {s.avg_ttft_ms:.1f}ms",
                f"  Tokens    : {s.total_tokens_in} in / {s.total_tokens_out} out",
                f"  Cost      : ${s.total_cost:.4f}",
            ]
            if s.avg_accuracy is not None:
                lines.append(f"  Accuracy  : {s.avg_accuracy:.1%}")
            grand_cost += s.total_cost
            grand_in += s.total_tokens_in
            grand_out += s.total_tokens_out

        lines += [
            "",
            "-" * 70,
            "TOTALS",
            "-" * 70,
            f"Cost   : ${grand_cost:.4f}",
            f"Tokens : {grand_in} in / {grand_out} out",
            "=" * 70,
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialise all metrics to a plain dict."""
        return {
            "generated_at": datetime.now().isoformat(),
            "started_at": self._started_at,
            "total_queries": len(self._queries),
            "personas": {
                name: {
                    "total": s.total,
                    "passed": s.passed,
                    "failed": s.failed,
                    "success_rate": round(s.success_rate, 4),
                    "avg_latency_ms": round(s.avg_latency_ms, 2),
                    "min_latency_ms": round(s.min_latency_ms, 2),
                    "max_latency_ms": round(s.max_latency_ms, 2),
                    "avg_ttft_ms": round(s.avg_ttft_ms, 2),
                    "total_tokens_in": s.total_tokens_in,
                    "total_tokens_out": s.total_tokens_out,
                    "total_cost": round(s.total_cost, 6),
                    "avg_accuracy": round(s.avg_accuracy, 4)
                    if s.avg_accuracy is not None
                    else None,
                }
                for name, s in self._summaries.items()
            },
            "queries": [asdict(q) for q in self._queries],
        }

    def save(self, path: str) -> str:
        """Save metrics JSON to disk. Returns the resolved path."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2))
        return str(out)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_accuracy(response: str, ground_truth: str) -> float:
    """
    Lightweight accuracy heuristic when no LLM judge is available.

    Computes token-level F1 between response and ground truth (case-insensitive).
    Returns 0.0–1.0.
    """
    r_tokens = set(response.lower().split())
    g_tokens = set(ground_truth.lower().split())
    if not g_tokens:
        return 1.0 if not r_tokens else 0.0
    if not r_tokens:
        return 0.0
    precision = len(r_tokens & g_tokens) / len(r_tokens)
    recall = len(r_tokens & g_tokens) / len(g_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)
