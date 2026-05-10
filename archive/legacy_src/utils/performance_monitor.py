"""
Performance Monitoring & Cost Tracking System for Kitty AI.

Tracks LLM API usage, costs, latency, and performance metrics.
Provides dashboards, budget alerts, and detailed reporting.
"""

import json
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import duckdb

    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    logger.warning("duckdb not available - performance monitoring will use JSON fallback")

try:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available - plotting features disabled")

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# Import cost constants from existing codebase
try:
    from src.utils.cli_helpers import _cost as calculate_token_cost

    COSTS_AVAILABLE = True
except ImportError:
    COSTS_AVAILABLE = False
    logger.warning("Cost calculation not available - using fallback pricing")


# Extended pricing for all supported models (cost per 1K tokens in USD)
MODEL_PRICING = {
    # OpenAI models
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-4": (0.03, 0.06),
    "gpt-4-0613": (0.03, 0.06),
    "gpt-3.5-turbo": (0.0005, 0.0015),
    # Anthropic models
    "claude-3-5-sonnet-20241022": (0.003, 0.015),
    "anthropic/claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-opus-20240229": (0.015, 0.075),
    "claude-3-sonnet-20240229": (0.003, 0.015),
    "claude-3-haiku-20240307": (0.00025, 0.00125),
    # Google/Gemini models
    "google/gemini-2.0-flash-001": (0.0001, 0.0004),
    "google/gemini-1.5-flash": (0.000075, 0.0003),
    "google/gemini-1.5-pro": (0.00125, 0.005),
    "gemini-pro": (0.0005, 0.0015),
    # OpenRouter models
    "openrouter/free": (0.0, 0.0),
    "google/gemini-2.0-flash-exp:free": (0.0, 0.0),
    "meta-llama/llama-3.3-70b-instruct:free": (0.0, 0.0),
    "qwen/qwen3-coder:free": (0.0, 0.0),
    "deepseek/deepseek-chat": (0.00014, 0.00028),
    "qwen/qwen2.5-coder-32b-instruct": (0.00007, 0.00028),
    "meta-llama/llama-3.1-70b-instruct": (0.00052, 0.00075),
    "meta-llama/llama-3.1-8b-instruct": (0.00006, 0.00006),
}


@dataclass
class RequestMetrics:
    """Metrics for a single LLM request."""

    timestamp: datetime
    model: str
    feature: str
    tokens_in: int
    tokens_out: int
    cost: float
    latency_ms: float
    success: bool = True
    error_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheStats:
    """Cache performance statistics."""

    cache_type: str
    hits: int = 0
    misses: int = 0
    last_hit_at: datetime | None = None
    last_miss_at: datetime | None = None


@dataclass
class BudgetAlert:
    """Budget alert configuration and state."""

    daily_limit: float = 10.0
    monthly_limit: float = 100.0
    alert_threshold_percent: float = 80.0
    last_alert_sent: datetime | None = None
    alert_cooldown_hours: float = 1.0


class MetricsCollector:
    """
    Collects and stores performance metrics for LLM API calls.

    Thread-safe singleton for tracking all metrics across the application.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str | None = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str | None = None):
        if self._initialized:
            return

        self._initialized = True
        self.db_path = db_path or self._get_default_db_path()
        self._local = threading.local()
        self._cache_stats: dict[str, CacheStats] = {}
        self._error_counts: dict[str, int] = {}
        self._budget_alert = BudgetAlert()

        # Initialize database
        if DUCKDB_AVAILABLE:
            self._init_database()
        else:
            self._init_json_fallback()

    def _get_default_db_path(self) -> str:
        """Get default database path."""
        project_dir = Path(__file__).parent.parent.parent
        data_dir = project_dir / "data"
        data_dir.mkdir(exist_ok=True)
        return str(data_dir / "performance_metrics.db")

    def _init_database(self):
        """Initialize DuckDB tables."""
        self.conn = duckdb.connect(self.db_path)

        # Requests table - main metrics storage
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER,
                timestamp TIMESTAMP NOT NULL,
                model VARCHAR NOT NULL,
                feature VARCHAR,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                cost DECIMAL(10, 6) DEFAULT 0.0,
                latency_ms DECIMAL(10, 2) DEFAULT 0.0,
                success BOOLEAN DEFAULT TRUE,
                error_type VARCHAR,
                metadata JSON
            )
        """)

        # Errors table - detailed error tracking
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                error_type VARCHAR NOT NULL,
                model VARCHAR,
                feature VARCHAR,
                context TEXT,
                stack_trace TEXT
            )
        """)

        # Cache stats table - cache performance
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_stats (
                cache_type VARCHAR PRIMARY KEY,
                hits INTEGER DEFAULT 0,
                misses INTEGER DEFAULT 0,
                last_hit_at TIMESTAMP,
                last_miss_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Budget alerts table - budget configuration
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS budget_config (
                id INTEGER PRIMARY KEY,
                daily_limit DECIMAL(10, 2) DEFAULT 10.0,
                monthly_limit DECIMAL(10, 2) DEFAULT 100.0,
                alert_threshold_percent DECIMAL(5, 2) DEFAULT 80.0,
                last_alert_sent TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert default budget config if not exists
        self.conn.execute("""
            INSERT OR IGNORE INTO budget_config (id) VALUES (1)
        """)

        # Create indexes for common queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_timestamp
            ON requests(timestamp)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_model
            ON requests(model)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_feature
            ON requests(feature)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_errors_timestamp
            ON errors(timestamp)
        """)

    def _init_json_fallback(self):
        """Initialize JSON file fallback when DuckDB is not available."""
        self.json_path = self.db_path.replace(".db", ".json")
        self._data = {
            "requests": [],
            "errors": [],
            "cache_stats": {},
            "budget_config": {
                "daily_limit": 10.0,
                "monthly_limit": 100.0,
                "alert_threshold_percent": 80.0,
            },
        }
        self._load_json_data()

    def _load_json_data(self):
        """Load data from JSON file."""
        if Path(self.json_path).exists():
            try:
                with open(self.json_path) as f:
                    loaded = json.load(f)
                    self._data.update(loaded)
            except Exception as e:
                logger.warning(f"Failed to load metrics JSON: {e}")

    def _save_json_data(self):
        """Save data to JSON file."""
        try:
            with open(self.json_path, "w") as f:
                json.dump(self._data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save metrics JSON: {e}")

    def track_request(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        cost: float | None = None,
        feature: str = "unknown",
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> RequestMetrics:
        """
        Track a single LLM API request.

        Args:
            model: The model name used
            tokens_in: Number of input tokens
            tokens_out: Number of output tokens
            latency_ms: Request latency in milliseconds
            cost: Optional pre-calculated cost (will calculate if None)
            feature: Feature/module that made the request
            success: Whether the request succeeded
            metadata: Additional metadata as dict

        Returns:
            RequestMetrics object with the recorded data
        """
        timestamp = datetime.now()

        # Calculate cost if not provided
        if cost is None:
            cost = self.calculate_cost(model, tokens_in, tokens_out)

        metrics = RequestMetrics(
            timestamp=timestamp,
            model=model,
            feature=feature,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            latency_ms=latency_ms,
            success=success,
            metadata=metadata or {},
        )

        # Store in database
        if DUCKDB_AVAILABLE:
            self.conn.execute(
                """
                INSERT INTO requests
                (id, timestamp, model, feature, tokens_in, tokens_out, cost, latency_ms, success, error_type, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    None,
                    metrics.timestamp,
                    metrics.model,
                    metrics.feature,
                    metrics.tokens_in,
                    metrics.tokens_out,
                    metrics.cost,
                    metrics.latency_ms,
                    metrics.success,
                    metrics.error_type,
                    json.dumps(metrics.metadata),
                ),
            )
        else:
            self._data["requests"].append(
                {
                    "timestamp": timestamp.isoformat(),
                    "model": model,
                    "feature": feature,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost": cost,
                    "latency_ms": latency_ms,
                    "success": success,
                    "metadata": metadata or {},
                }
            )
            self._save_json_data()

        # Check budget alerts
        self._check_budget_alert()

        return metrics

    def track_cache_hit(self, cache_type: str):
        """Track a cache hit."""
        timestamp = datetime.now()

        if cache_type not in self._cache_stats:
            self._cache_stats[cache_type] = CacheStats(cache_type=cache_type)

        self._cache_stats[cache_type].hits += 1
        self._cache_stats[cache_type].last_hit_at = timestamp

        if DUCKDB_AVAILABLE:
            self.conn.execute(
                """
                INSERT INTO cache_stats (cache_type, hits, last_hit_at)
                VALUES (?, 1, ?)
                ON CONFLICT (cache_type) DO UPDATE SET
                    hits = cache_stats.hits + 1,
                    last_hit_at = ?,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (cache_type, timestamp, timestamp),
            )
        else:
            if cache_type not in self._data["cache_stats"]:
                self._data["cache_stats"][cache_type] = {"hits": 0, "misses": 0}
            self._data["cache_stats"][cache_type]["hits"] += 1
            self._data["cache_stats"][cache_type]["last_hit_at"] = timestamp.isoformat()
            self._save_json_data()

    def track_cache_miss(self, cache_type: str):
        """Track a cache miss."""
        timestamp = datetime.now()

        if cache_type not in self._cache_stats:
            self._cache_stats[cache_type] = CacheStats(cache_type=cache_type)

        self._cache_stats[cache_type].misses += 1
        self._cache_stats[cache_type].last_miss_at = timestamp

        if DUCKDB_AVAILABLE:
            self.conn.execute(
                """
                INSERT INTO cache_stats (cache_type, misses, last_miss_at)
                VALUES (?, 1, ?)
                ON CONFLICT (cache_type) DO UPDATE SET
                    misses = cache_stats.misses + 1,
                    last_miss_at = ?,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (cache_type, timestamp, timestamp),
            )
        else:
            if cache_type not in self._data["cache_stats"]:
                self._data["cache_stats"][cache_type] = {"hits": 0, "misses": 0}
            self._data["cache_stats"][cache_type]["misses"] += 1
            self._data["cache_stats"][cache_type]["last_miss_at"] = timestamp.isoformat()
            self._save_json_data()

    def track_error(
        self,
        error_type: str,
        model: str | None = None,
        feature: str | None = None,
        context: str | None = None,
        stack_trace: str | None = None,
    ):
        """
        Track an error.

        Args:
            error_type: Type/category of error
            model: Model being used when error occurred
            feature: Feature that triggered the error
            context: Additional context about the error
            stack_trace: Full stack trace if available
        """
        timestamp = datetime.now()

        # Update error count
        key = f"{error_type}:{model or 'unknown'}"
        self._error_counts[key] = self._error_counts.get(key, 0) + 1

        if DUCKDB_AVAILABLE:
            self.conn.execute(
                """
                INSERT INTO errors (timestamp, error_type, model, feature, context, stack_trace)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (timestamp, error_type, model, feature, context, stack_trace),
            )
        else:
            self._data["errors"].append(
                {
                    "timestamp": timestamp.isoformat(),
                    "error_type": error_type,
                    "model": model,
                    "feature": feature,
                    "context": context,
                    "stack_trace": stack_trace,
                }
            )
            self._save_json_data()

    @staticmethod
    def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
        """
        Calculate the cost for a model request.

        Args:
            model: Model identifier
            tokens_in: Input token count
            tokens_out: Output token count

        Returns:
            Cost in USD
        """
        # Use existing cost function if available
        if COSTS_AVAILABLE:
            try:
                return calculate_token_cost(model, tokens_in, tokens_out)
            except Exception:
                pass

        # Fallback to local pricing
        pricing = MODEL_PRICING.get(model, (0.0, 0.0))
        return (tokens_in / 1000) * pricing[0] + (tokens_out / 1000) * pricing[1]

    def _check_budget_alert(self):
        """Check if budget alert should be triggered."""
        daily_cost = self.get_daily_costs(days=1)[0]["cost"]

        threshold = self._budget_alert.daily_limit * (
            self._budget_alert.alert_threshold_percent / 100
        )

        if daily_cost >= threshold:
            now = datetime.now()
            if (
                self._budget_alert.last_alert_sent is None
                or (now - self._budget_alert.last_alert_sent).total_seconds()
                >= self._budget_alert.alert_cooldown_hours * 3600
            ):
                self._budget_alert.last_alert_sent = now
                logger.warning(
                    f"Daily cost ${daily_cost:.4f} approaching limit ${self._budget_alert.daily_limit:.2f}"
                )

    def set_budget_limits(self, daily: float | None = None, monthly: float | None = None):
        """Set budget alert limits."""
        if daily is not None:
            self._budget_alert.daily_limit = daily
        if monthly is not None:
            self._budget_alert.monthly_limit = monthly

        if DUCKDB_AVAILABLE:
            self.conn.execute(
                """
                UPDATE budget_config SET
                    daily_limit = ?,
                    monthly_limit = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """,
                (self._budget_alert.daily_limit, self._budget_alert.monthly_limit),
            )

    def get_daily_costs(self, days: int = 30) -> list[dict[str, Any]]:
        """Get cost breakdown by day."""
        start_date = datetime.now() - timedelta(days=days)

        if DUCKDB_AVAILABLE:
            result = self.conn.execute(
                """
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as requests,
                    SUM(tokens_in) as tokens_in,
                    SUM(tokens_out) as tokens_out,
                    SUM(cost) as cost,
                    AVG(latency_ms) as avg_latency,
                    SUM(CASE WHEN success THEN 0 ELSE 1 END) as errors
                FROM requests
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """,
                (start_date,),
            ).fetchall()

            return [
                {
                    "date": row[0],
                    "requests": row[1],
                    "tokens_in": row[2] or 0,
                    "tokens_out": row[3] or 0,
                    "cost": float(row[4] or 0),
                    "avg_latency": float(row[5] or 0),
                    "errors": row[6] or 0,
                }
                for row in result
            ]
        else:
            # JSON fallback
            costs = {}
            for req in self._data["requests"]:
                date = req["timestamp"][:10]
                if date not in costs:
                    costs[date] = {
                        "date": date,
                        "requests": 0,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "cost": 0.0,
                        "latency_sum": 0.0,
                        "errors": 0,
                    }
                costs[date]["requests"] += 1
                costs[date]["tokens_in"] += req.get("tokens_in", 0)
                costs[date]["tokens_out"] += req.get("tokens_out", 0)
                costs[date]["cost"] += req.get("cost", 0)
                costs[date]["latency_sum"] += req.get("latency_ms", 0)
                if not req.get("success", True):
                    costs[date]["errors"] += 1

            result = []
            for date, data in sorted(costs.items(), reverse=True)[:days]:
                if data["requests"] > 0:
                    data["avg_latency"] = data["latency_sum"] / data["requests"]
                del data["latency_sum"]
                result.append(data)
            return result

    def get_cost_by_feature(self, days: int = 30) -> list[dict[str, Any]]:
        """Get cost breakdown by feature."""
        start_date = datetime.now() - timedelta(days=days)

        if DUCKDB_AVAILABLE:
            result = self.conn.execute(
                """
                SELECT
                    feature,
                    COUNT(*) as requests,
                    SUM(cost) as cost,
                    AVG(latency_ms) as avg_latency
                FROM requests
                WHERE timestamp >= ?
                GROUP BY feature
                ORDER BY cost DESC
            """,
                (start_date,),
            ).fetchall()

            return [
                {
                    "feature": row[0],
                    "requests": row[1],
                    "cost": float(row[2] or 0),
                    "avg_latency": float(row[3] or 0),
                }
                for row in result
            ]
        else:
            # JSON fallback
            features = {}
            for req in self._data["requests"]:
                feature = req.get("feature", "unknown")
                if feature not in features:
                    features[feature] = {
                        "feature": feature,
                        "requests": 0,
                        "cost": 0.0,
                        "latency_sum": 0.0,
                    }
                features[feature]["requests"] += 1
                features[feature]["cost"] += req.get("cost", 0)
                features[feature]["latency_sum"] += req.get("latency_ms", 0)

            result = []
            for feature, data in sorted(features.items(), key=lambda x: x[1]["cost"], reverse=True):
                if data["requests"] > 0:
                    data["avg_latency"] = data["latency_sum"] / data["requests"]
                del data["latency_sum"]
                result.append(data)
            return result

    def get_cost_by_model(self, days: int = 30) -> list[dict[str, Any]]:
        """Get cost breakdown by model."""
        start_date = datetime.now() - timedelta(days=days)

        if DUCKDB_AVAILABLE:
            result = self.conn.execute(
                """
                SELECT
                    model,
                    COUNT(*) as requests,
                    SUM(cost) as cost,
                    AVG(latency_ms) as avg_latency
                FROM requests
                WHERE timestamp >= ?
                GROUP BY model
                ORDER BY cost DESC
            """,
                (start_date,),
            ).fetchall()

            return [
                {
                    "model": row[0],
                    "requests": row[1],
                    "cost": float(row[2] or 0),
                    "avg_latency": float(row[3] or 0),
                }
                for row in result
            ]
        else:
            # JSON fallback
            models = {}
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            for req in self._data["requests"]:
                if req["timestamp"] < cutoff:
                    continue
                model = req.get("model", "unknown")
                if model not in models:
                    models[model] = {"model": model, "requests": 0, "cost": 0.0, "latency_sum": 0.0}
                models[model]["requests"] += 1
                models[model]["cost"] += req.get("cost", 0)
                models[model]["latency_sum"] += req.get("latency_ms", 0)

            result = []
            for model, data in sorted(models.items(), key=lambda x: x[1]["cost"], reverse=True):
                if data["requests"] > 0:
                    data["avg_latency"] = data["latency_sum"] / data["requests"]
                del data["latency_sum"]
                result.append(data)
            return result

    def estimate_monthly_spend(self) -> dict[str, float]:
        """Estimate monthly spend based on current daily average."""
        daily_costs = self.get_daily_costs(days=7)

        if not daily_costs:
            return {"current_month": 0.0, "projected_month": 0.0, "daily_average": 0.0}

        total_cost = sum(day["cost"] for day in daily_costs)
        daily_avg = total_cost / len(daily_costs)

        # Get current month cost
        now = datetime.now()
        current_month_cost = (
            sum(
                day["cost"]
                for day in daily_costs
                if datetime.fromisoformat(
                    day["date"][:10] if len(day["date"]) > 10 else day["date"]
                ).month
                == now.month
            )
            if daily_costs
            else 0
        )

        # Project for remaining days in month
        days_in_month = 30
        projected = daily_avg * days_in_month

        return {
            "current_month": current_month_cost,
            "projected_month": projected,
            "daily_average": daily_avg,
        }

    def get_cache_stats(self) -> list[dict[str, Any]]:
        """Get cache statistics."""
        if DUCKDB_AVAILABLE:
            result = self.conn.execute("""
                SELECT cache_type, hits, misses, last_hit_at, last_miss_at
                FROM cache_stats
            """).fetchall()

            return [
                {
                    "cache_type": row[0],
                    "hits": row[1],
                    "misses": row[2],
                    "hit_rate": row[1] / (row[1] + row[2]) * 100 if (row[1] + row[2]) > 0 else 0,
                    "last_hit_at": row[3],
                    "last_miss_at": row[4],
                }
                for row in result
            ]
        else:
            result = []
            for cache_type, stats in self._data.get("cache_stats", {}).items():
                hits = stats.get("hits", 0)
                misses = stats.get("misses", 0)
                result.append(
                    {
                        "cache_type": cache_type,
                        "hits": hits,
                        "misses": misses,
                        "hit_rate": hits / (hits + misses) * 100 if (hits + misses) > 0 else 0,
                        "last_hit_at": stats.get("last_hit_at"),
                        "last_miss_at": stats.get("last_miss_at"),
                    }
                )
            return result

    def get_error_stats(self, days: int = 7) -> list[dict[str, Any]]:
        """Get error statistics."""
        start_date = datetime.now() - timedelta(days=days)

        if DUCKDB_AVAILABLE:
            result = self.conn.execute(
                """
                SELECT
                    error_type,
                    model,
                    COUNT(*) as count,
                    MAX(timestamp) as last_occurrence
                FROM errors
                WHERE timestamp >= ?
                GROUP BY error_type, model
                ORDER BY count DESC
            """,
                (start_date,),
            ).fetchall()

            return [
                {"error_type": row[0], "model": row[1], "count": row[2], "last_occurrence": row[3]}
                for row in result
            ]
        else:
            # JSON fallback
            errors = {}
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            for err in self._data.get("errors", []):
                if err["timestamp"] < cutoff:
                    continue
                key = f"{err['error_type']}:{err.get('model', 'unknown')}"
                if key not in errors:
                    errors[key] = {
                        "error_type": err["error_type"],
                        "model": err.get("model", "unknown"),
                        "count": 0,
                        "last_occurrence": err["timestamp"],
                    }
                errors[key]["count"] += 1
                if err["timestamp"] > errors[key]["last_occurrence"]:
                    errors[key]["last_occurrence"] = err["timestamp"]

            return sorted(errors.values(), key=lambda x: x["count"], reverse=True)

    def get_performance_summary(self) -> dict[str, Any]:
        """Get a comprehensive performance summary."""
        daily_costs = self.get_daily_costs(days=1)
        today_cost = daily_costs[0]["cost"] if daily_costs else 0.0

        weekly_costs = self.get_daily_costs(days=7)
        weekly_cost = sum(day["cost"] for day in weekly_costs)

        model_breakdown = self.get_cost_by_model(days=7)
        feature_breakdown = self.get_cost_by_feature(days=7)
        cache_stats = self.get_cache_stats()
        error_stats = self.get_error_stats(days=7)
        monthly_estimate = self.estimate_monthly_spend()

        total_requests = sum(day["requests"] for day in weekly_costs)
        total_errors = sum(day.get("errors", 0) for day in weekly_costs)

        avg_latency = 0
        if weekly_costs:
            avg_latency = sum(day.get("avg_latency", 0) for day in weekly_costs) / len(weekly_costs)

        return {
            "today": {
                "cost": today_cost,
                "requests": daily_costs[0]["requests"] if daily_costs else 0,
                "errors": daily_costs[0].get("errors", 0) if daily_costs else 0,
            },
            "this_week": {"cost": weekly_cost, "requests": total_requests, "errors": total_errors},
            "monthly_estimate": monthly_estimate,
            "budget_status": {
                "daily_limit": self._budget_alert.daily_limit,
                "monthly_limit": self._budget_alert.monthly_limit,
                "daily_used_percent": (today_cost / self._budget_alert.daily_limit * 100)
                if self._budget_alert.daily_limit > 0
                else 0,
            },
            "model_breakdown": model_breakdown[:5],
            "feature_breakdown": feature_breakdown[:5],
            "cache_stats": cache_stats,
            "error_stats": error_stats[:5],
            "avg_latency_ms": avg_latency,
            "error_rate": (total_errors / total_requests * 100) if total_requests > 0 else 0,
        }


class CostTracker:
    """
    High-level cost tracking interface.
    Provides convenient methods for common cost tracking operations.
    """

    def __init__(self):
        self.collector = MetricsCollector()

    def track_llm_call(
        self,
        model: str,
        prompt: str,
        response: str,
        feature: str = "unknown",
        latency_ms: float = 0.0,
        success: bool = True,
    ) -> float:
        """
        Track an LLM call with automatic token estimation.

        Args:
            model: Model name
            prompt: Input prompt text
            response: Response text
            feature: Feature/module name
            latency_ms: Request latency
            success: Whether the call succeeded

        Returns:
            Calculated cost
        """
        # Estimate tokens (rough approximation: 4 chars ≈ 1 token)
        tokens_in = len(prompt) // 4
        tokens_out = len(response) // 4

        cost = self.collector.calculate_cost(model, tokens_in, tokens_out)

        self.collector.track_request(
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost=cost,
            feature=feature,
            success=success,
        )

        return cost

    @contextmanager
    def track_latency(self, model: str, feature: str = "unknown"):
        """
        Context manager to track request latency.

        Usage:
            with cost_tracker.track_latency("gpt-4", "chat"):
                response = make_api_call()
        """
    def get_daily_costs(self, days: int = 30) -> list[dict[str, Any]]:
        """Get daily cost breakdown."""
        return self.collector.get_daily_costs(days)

    def get_cost_by_feature(self, feature_name: str | None = None, days: int = 30) -> Any:
        """Get cost by feature."""
        if feature_name:
            features = self.collector.get_cost_by_feature(days)
            for f in features:
                if f["feature"] == feature_name:
                    return f
            return None
        return self.collector.get_cost_by_feature(days)

    def estimate_monthly_spend(self) -> dict[str, float]:
        """Estimate monthly spending."""
        return self.collector.estimate_monthly_spend()

    def set_budget_limit(self, daily: float | None = None, monthly: float | None = None):
        """Set budget limits."""
        self.collector.set_budget_limits(daily, monthly)


class DashboardGenerator:
    """
    Generates dashboards and visualizations for performance metrics.
    """

    def __init__(self, output_dir: str | None = None):
        self.collector = MetricsCollector()
        self.output_dir = (
            Path(output_dir)
            if output_dir
            else Path(__file__).parent.parent.parent / "data" / "dashboards"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_daily_report(self, days: int = 7, format: str = "json") -> str:
        """
        Generate a daily report.

        Args:
            days: Number of days to include
            format: Output format (json, csv)

        Returns:
            Path to generated report file
        """
        daily_costs = self.collector.get_daily_costs(days)

        if format == "json":
            output_file = self.output_dir / f"daily_report_{datetime.now().strftime('%Y%m%d')}.json"
            report = {
                "generated_at": datetime.now().isoformat(),
                "period_days": days,
                "daily_costs": daily_costs,
                "summary": {
                    "total_cost": sum(day["cost"] for day in daily_costs),
                    "total_requests": sum(day["requests"] for day in daily_costs),
                    "total_errors": sum(day.get("errors", 0) for day in daily_costs),
                },
            }
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2, default=str)

        elif format == "csv":
            output_file = self.output_dir / f"daily_report_{datetime.now().strftime('%Y%m%d')}.csv"

            if PANDAS_AVAILABLE:
                df = pd.DataFrame(daily_costs)
                df.to_csv(output_file, index=False)
            else:
                import csv

                with open(output_file, "w", newline="") as f:
                    if daily_costs:
                        writer = csv.DictWriter(f, fieldnames=daily_costs[0].keys())
                        writer.writeheader()
                        writer.writerows(daily_costs)
        else:
            raise ValueError(f"Unsupported format: {format}")

        return str(output_file)

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary for display."""
        return self.collector.get_performance_summary()

    def plot_cost_trend(self, days: int = 30, output_file: str | None = None) -> str | None:
        """
        Generate a cost trend visualization.

        Args:
            days: Number of days to plot
            output_file: Optional output file path

        Returns:
            Path to generated plot file or None if matplotlib unavailable
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available - cannot generate plot")
            return None

        daily_costs = self.collector.get_daily_costs(days)

        if not daily_costs:
            logger.warning("No data available for plotting")
            return None

        # Prepare data
        dates = [
            datetime.fromisoformat(day["date"][:10] if len(day["date"]) > 10 else day["date"])
            for day in daily_costs
        ]
        costs = [day["cost"] for day in daily_costs]

        # Create plot
        plt.figure(figsize=(12, 6))
        plt.plot(dates, costs, marker="o", linewidth=2, markersize=6)
        plt.fill_between(dates, costs, alpha=0.3)

        plt.title(f"Daily API Costs (Last {days} Days)", fontsize=14, fontweight="bold")
        plt.xlabel("Date", fontsize=12)
        plt.ylabel("Cost (USD)", fontsize=12)
        plt.grid(True, alpha=0.3)

        # Format x-axis
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
        plt.xticks(rotation=45)

        # Add budget line if set
        budget = self.collector._budget_alert.daily_limit
        if budget > 0:
            plt.axhline(y=budget, color="r", linestyle="--", label=f"Daily Budget (${budget:.2f})")
            plt.legend()

        plt.tight_layout()

        # Save plot
        if output_file is None:
            output_file = self.output_dir / f"cost_trend_{datetime.now().strftime('%Y%m%d')}.png"
        else:
            output_file = Path(output_file)

        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        plt.close()

        return str(output_file)

    def plot_model_breakdown(
        self, days: int = 7, output_file: str | None = None
    ) -> str | None:
        """
        Generate a pie chart of costs by model.

        Args:
            days: Number of days to include
            output_file: Optional output file path

        Returns:
            Path to generated plot file or None if matplotlib unavailable
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        model_data = self.collector.get_cost_by_model(days)

        if not model_data:
            return None

        models = [m["model"].split("/")[-1][:20] for m in model_data[:8]]  # Top 8 models
        costs = [m["cost"] for m in model_data[:8]]

        # Add "Other" category if there are more models
        if len(model_data) > 8:
            other_cost = sum(m["cost"] for m in model_data[8:])
            models.append("Other")
            costs.append(other_cost)

        plt.figure(figsize=(10, 8))
        colors = plt.cm.Set3(range(len(models)))
        plt.pie(costs, labels=models, autopct="%1.1f%%", startangle=90, colors=colors)
        plt.title(f"Cost Breakdown by Model (Last {days} Days)", fontsize=14, fontweight="bold")
        plt.axis("equal")

        if output_file is None:
            output_file = (
                self.output_dir / f"model_breakdown_{datetime.now().strftime('%Y%m%d')}.png"
            )
        else:
            output_file = Path(output_file)

        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        plt.close()

        return str(output_file)

    def generate_html_dashboard(self, output_file: str | None = None) -> str:
        """
        Generate an HTML dashboard.

        Returns:
            Path to generated HTML file
        """
        summary = self.get_performance_summary()

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Kitty AI Performance Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-value {{
            font-size: 32px;
            font-weight: bold;
            color: #4CAF50;
        }}
        .metric-label {{
            color: #666;
            margin-top: 5px;
        }}
        .alert {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }}
        .alert-warning {{
            background: #f8d7da;
            border-color: #dc3545;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .section {{
            margin: 30px 0;
        }}
        .section h2 {{
            color: #333;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Kitty AI Performance Dashboard</h1>
        <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">${summary["today"]["cost"]:.4f}</div>
                <div class="metric-label">Today's Cost</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${summary["this_week"]["cost"]:.4f}</div>
                <div class="metric-label">This Week's Cost</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${summary["monthly_estimate"]["projected_month"]:.2f}</div>
                <div class="metric-label">Projected Monthly</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{summary["today"]["requests"]}</div>
                <div class="metric-label">Today's Requests</div>
            </div>
        </div>
"""

        # Budget alert
        budget_pct = summary["budget_status"]["daily_used_percent"]
        if budget_pct > 90:
            html += f"""
        <div class="alert alert-warning">
            <strong>Budget Alert!</strong> Daily budget {budget_pct:.1f}% consumed
            (${summary["today"]["cost"]:.4f} / ${summary["budget_status"]["daily_limit"]:.2f})
        </div>
"""
        elif budget_pct > 75:
            html += f"""
        <div class="alert">
            <strong>Warning:</strong> Daily budget {budget_pct:.1f}% consumed
            (${summary["today"]["cost"]:.4f} / ${summary["budget_status"]["daily_limit"]:.2f})
        </div>
"""

        # Model breakdown
        html += """
        <div class="section">
            <h2>Cost by Model (Top 5)</h2>
            <table>
                <tr>
                    <th>Model</th>
                    <th>Requests</th>
                    <th>Cost</th>
                    <th>Avg Latency</th>
                </tr>
"""
        for model in summary["model_breakdown"]:
            html += f"""
                <tr>
                    <td>{model["model"]}</td>
                    <td>{model["requests"]}</td>
                    <td>${model["cost"]:.4f}</td>
                    <td>{model["avg_latency"]:.0f}ms</td>
                </tr>
"""
        html += """
            </table>
        </div>
"""

        # Feature breakdown
        html += """
        <div class="section">
            <h2>Cost by Feature (Top 5)</h2>
            <table>
                <tr>
                    <th>Feature</th>
                    <th>Requests</th>
                    <th>Cost</th>
                    <th>Avg Latency</th>
                </tr>
"""
        for feature in summary["feature_breakdown"]:
            html += f"""
                <tr>
                    <td>{feature["feature"]}</td>
                    <td>{feature["requests"]}</td>
                    <td>${feature["cost"]:.4f}</td>
                    <td>{feature["avg_latency"]:.0f}ms</td>
                </tr>
"""
        html += """
            </table>
        </div>
"""

        html += """
    </div>
</body>
</html>
"""

        if output_file is None:
            output_file = (
                self.output_dir / f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            )
        else:
            output_file = Path(output_file)

        with open(output_file, "w") as f:
            f.write(html)

        return str(output_file)


# Lazy globals — defer DB connection until first use so test collection
# doesn't lock the live server's database files.
class _Lazy:
    def __init__(self, cls, *a, **kw):
        self._cls, self._a, self._kw, self._obj = cls, a, kw, None
    def __getattr__(self, n):
        if self._obj is None:
            self._obj = self._cls(*self._a, **self._kw)
        return getattr(self._obj, n)

metrics_collector = _Lazy(MetricsCollector)
cost_tracker = _Lazy(CostTracker)
