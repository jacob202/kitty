"""
Metrics Collector — Production-grade time-series metrics for Kitty AI.
Collects API response times, LLM latency, DB performance, error rates, cache stats, and active users.
Stores in DuckDB with automatic aggregation by minute/hour/day.
"""

import functools
import json
import statistics
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
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
    print("[WARN] duckdb not available - metrics will use JSON fallback")


@dataclass
class APIMetric:
    """API request metric."""

    timestamp: datetime
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    request_size_bytes: int = 0
    response_size_bytes: int = 0
    user_id: str | None = None
    error_type: str | None = None


@dataclass
class LLMMetric:
    """LLM call metric."""

    timestamp: datetime
    model: str
    provider: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
    feature: str
    success: bool = True
    error_type: str | None = None
    cache_hit: bool = False


@dataclass
class DBMetric:
    """Database query metric."""

    timestamp: datetime
    query_type: str
    table_name: str
    execution_time_ms: float
    rows_affected: int = 0
    rows_returned: int = 0
    success: bool = True
    error_type: str | None = None


@dataclass
class CacheMetric:
    """Cache operation metric."""

    timestamp: datetime
    cache_type: str
    operation: str  # 'hit', 'miss', 'set', 'delete'
    key: str | None = None
    size_bytes: int = 0
    ttl_seconds: int | None = None


@dataclass
class ComponentAccuracy:
    """Component identification accuracy metric."""

    timestamp: datetime
    component_type: str
    identification_method: str
    confidence_score: float
    was_correct: bool
    user_feedback: str | None = None


@dataclass
class UserSession:
    """User session tracking."""

    session_id: str
    user_id: str | None
    started_at: datetime
    last_activity: datetime
    ip_address: str | None = None
    user_agent: str | None = None


class MetricsCollector:
    """
    Production-grade metrics collector for Kitty AI.
    Thread-safe singleton with DuckDB time-series storage.
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
        self._lock = threading.RLock()

        # In-memory buffers for high-frequency metrics
        self._api_buffer: deque = deque(maxlen=10000)
        self._llm_buffer: deque = deque(maxlen=10000)
        self._db_buffer: deque = deque(maxlen=5000)
        self._cache_buffer: deque = deque(maxlen=5000)
        self._accuracy_buffer: deque = deque(maxlen=1000)

        # Active sessions
        self._active_sessions: dict[str, UserSession] = {}
        self._sessions_lock = threading.RLock()

        # Callbacks for real-time processing
        self._callbacks: list[Callable] = []

        # Initialize storage
        if DUCKDB_AVAILABLE:
            self._init_database()
        else:
            self._init_json_fallback()

    def _get_default_db_path(self) -> str:
        """Get default database path."""
        project_dir = Path(__file__).parent.parent.parent
        data_dir = project_dir / "data" / "observability"
        data_dir.mkdir(parents=True, exist_ok=True)
        return str(data_dir / "metrics.duckdb")

    def _init_database(self):
        """Initialize DuckDB tables with time-series optimizations."""
        self.conn = duckdb.connect(self.db_path)

        # API metrics table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS api_metrics (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                endpoint VARCHAR NOT NULL,
                method VARCHAR NOT NULL,
                status_code INTEGER NOT NULL,
                response_time_ms DECIMAL(10, 2) NOT NULL,
                request_size_bytes INTEGER DEFAULT 0,
                response_size_bytes INTEGER DEFAULT 0,
                user_id VARCHAR,
                error_type VARCHAR
            )
        """)

        # LLM metrics table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_metrics (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                model VARCHAR NOT NULL,
                provider VARCHAR NOT NULL,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                latency_ms DECIMAL(10, 2) NOT NULL,
                cost_usd DECIMAL(10, 6) DEFAULT 0.0,
                feature VARCHAR NOT NULL,
                success BOOLEAN DEFAULT TRUE,
                error_type VARCHAR,
                cache_hit BOOLEAN DEFAULT FALSE
            )
        """)

        # Database metrics table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS db_metrics (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                query_type VARCHAR NOT NULL,
                table_name VARCHAR NOT NULL,
                execution_time_ms DECIMAL(10, 2) NOT NULL,
                rows_affected INTEGER DEFAULT 0,
                rows_returned INTEGER DEFAULT 0,
                success BOOLEAN DEFAULT TRUE,
                error_type VARCHAR
            )
        """)

        # Cache metrics table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_metrics (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                cache_type VARCHAR NOT NULL,
                operation VARCHAR NOT NULL,
                key VARCHAR,
                size_bytes INTEGER DEFAULT 0,
                ttl_seconds INTEGER
            )
        """)

        # Component accuracy table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS component_accuracy (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                component_type VARCHAR NOT NULL,
                identification_method VARCHAR NOT NULL,
                confidence_score DECIMAL(5, 4) NOT NULL,
                was_correct BOOLEAN NOT NULL,
                user_feedback VARCHAR
            )
        """)

        # User sessions table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                started_at TIMESTAMP NOT NULL,
                last_activity TIMESTAMP NOT NULL,
                ip_address VARCHAR,
                user_agent VARCHAR
            )
        """)

        # Aggregated metrics tables for fast dashboard queries
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS api_metrics_minute (
                bucket TIMESTAMP NOT NULL,
                endpoint VARCHAR NOT NULL,
                method VARCHAR NOT NULL,
                request_count INTEGER DEFAULT 0,
                avg_response_time_ms DECIMAL(10, 2),
                p95_response_time_ms DECIMAL(10, 2),
                p99_response_time_ms DECIMAL(10, 2),
                error_count INTEGER DEFAULT 0,
                error_rate_percent DECIMAL(5, 2),
                PRIMARY KEY (bucket, endpoint, method)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_metrics_hourly (
                bucket TIMESTAMP NOT NULL,
                model VARCHAR NOT NULL,
                feature VARCHAR NOT NULL,
                call_count INTEGER DEFAULT 0,
                total_tokens_in INTEGER DEFAULT 0,
                total_tokens_out INTEGER DEFAULT 0,
                avg_latency_ms DECIMAL(10, 2),
                total_cost_usd DECIMAL(10, 6) DEFAULT 0.0,
                error_count INTEGER DEFAULT 0,
                cache_hit_rate DECIMAL(5, 2),
                PRIMARY KEY (bucket, model, feature)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS db_metrics_hourly (
                bucket TIMESTAMP NOT NULL,
                query_type VARCHAR NOT NULL,
                table_name VARCHAR NOT NULL,
                query_count INTEGER DEFAULT 0,
                avg_execution_time_ms DECIMAL(10, 2),
                total_rows_affected INTEGER DEFAULT 0,
                total_rows_returned INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                PRIMARY KEY (bucket, query_type, table_name)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_metrics_hourly (
                bucket TIMESTAMP NOT NULL,
                cache_type VARCHAR NOT NULL,
                hits INTEGER DEFAULT 0,
                misses INTEGER DEFAULT 0,
                sets INTEGER DEFAULT 0,
                deletes INTEGER DEFAULT 0,
                hit_rate_percent DECIMAL(5, 2),
                PRIMARY KEY (bucket, cache_type)
            )
        """)

        # Create indexes for common queries
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_api_timestamp ON api_metrics(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_api_endpoint ON api_metrics(endpoint)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_timestamp ON llm_metrics(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_model ON llm_metrics(model)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_db_timestamp ON db_metrics(timestamp)")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_timestamp ON cache_metrics(timestamp)"
        )

    def _init_json_fallback(self):
        """Initialize JSON file fallback when DuckDB is not available."""
        self.json_path = self.db_path.replace(".duckdb", ".json")
        self._data = {
            "api_metrics": [],
            "llm_metrics": [],
            "db_metrics": [],
            "cache_metrics": [],
            "component_accuracy": [],
            "user_sessions": {},
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
                print(f"[WARN] Failed to load metrics JSON: {e}")

    def _save_json_data(self):
        """Save data to JSON file."""
        try:
            with open(self.json_path, "w") as f:
                json.dump(self._data, f, indent=2, default=str)
        except Exception as e:
            print(f"[WARN] Failed to save metrics JSON: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Metric Recording Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def track_api_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        request_size_bytes: int = 0,
        response_size_bytes: int = 0,
        user_id: str | None = None,
        error_type: str | None = None,
    ) -> APIMetric:
        """Track an API request."""
        metric = APIMetric(
            timestamp=datetime.now(),
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            request_size_bytes=request_size_bytes,
            response_size_bytes=response_size_bytes,
            user_id=user_id,
            error_type=error_type if status_code >= 400 else None,
        )

        with self._lock:
            self._api_buffer.append(metric)

            if DUCKDB_AVAILABLE:
                self.conn.execute(
                    """
                    INSERT INTO api_metrics
                    (timestamp, endpoint, method, status_code, response_time_ms,
                     request_size_bytes, response_size_bytes, user_id, error_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        metric.timestamp,
                        metric.endpoint,
                        metric.method,
                        metric.status_code,
                        metric.response_time_ms,
                        metric.request_size_bytes,
                        metric.response_size_bytes,
                        metric.user_id,
                        metric.error_type,
                    ),
                )
            else:
                self._data["api_metrics"].append(asdict(metric))
                self._save_json_data()

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback("api", metric)
            except Exception:
                pass

        return metric

    def track_llm_call(
        self,
        model: str,
        provider: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        cost_usd: float,
        feature: str,
        success: bool = True,
        error_type: str | None = None,
        cache_hit: bool = False,
    ) -> LLMMetric:
        """Track an LLM API call."""
        metric = LLMMetric(
            timestamp=datetime.now(),
            model=model,
            provider=provider,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            feature=feature,
            success=success,
            error_type=error_type,
            cache_hit=cache_hit,
        )

        with self._lock:
            self._llm_buffer.append(metric)

            if DUCKDB_AVAILABLE:
                self.conn.execute(
                    """
                    INSERT INTO llm_metrics
                    (timestamp, model, provider, tokens_in, tokens_out, latency_ms,
                     cost_usd, feature, success, error_type, cache_hit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        metric.timestamp,
                        metric.model,
                        metric.provider,
                        metric.tokens_in,
                        metric.tokens_out,
                        metric.latency_ms,
                        metric.cost_usd,
                        metric.feature,
                        metric.success,
                        metric.error_type,
                        metric.cache_hit,
                    ),
                )
            else:
                self._data["llm_metrics"].append(asdict(metric))
                self._save_json_data()

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback("llm", metric)
            except Exception:
                pass

        return metric

    def track_db_query(
        self,
        query_type: str,
        table_name: str,
        execution_time_ms: float,
        rows_affected: int = 0,
        rows_returned: int = 0,
        success: bool = True,
        error_type: str | None = None,
    ) -> DBMetric:
        """Track a database query."""
        metric = DBMetric(
            timestamp=datetime.now(),
            query_type=query_type,
            table_name=table_name,
            execution_time_ms=execution_time_ms,
            rows_affected=rows_affected,
            rows_returned=rows_returned,
            success=success,
            error_type=error_type,
        )

        with self._lock:
            self._db_buffer.append(metric)

            if DUCKDB_AVAILABLE:
                self.conn.execute(
                    """
                    INSERT INTO db_metrics
                    (timestamp, query_type, table_name, execution_time_ms,
                     rows_affected, rows_returned, success, error_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        metric.timestamp,
                        metric.query_type,
                        metric.table_name,
                        metric.execution_time_ms,
                        metric.rows_affected,
                        metric.rows_returned,
                        metric.success,
                        metric.error_type,
                    ),
                )
            else:
                self._data["db_metrics"].append(asdict(metric))
                self._save_json_data()

        return metric

    def track_cache_op(
        self,
        cache_type: str,
        operation: str,
        key: str | None = None,
        size_bytes: int = 0,
        ttl_seconds: int | None = None,
    ) -> CacheMetric:
        """Track a cache operation."""
        metric = CacheMetric(
            timestamp=datetime.now(),
            cache_type=cache_type,
            operation=operation,
            key=key,
            size_bytes=size_bytes,
            ttl_seconds=ttl_seconds,
        )

        with self._lock:
            self._cache_buffer.append(metric)

            if DUCKDB_AVAILABLE:
                self.conn.execute(
                    """
                    INSERT INTO cache_metrics
                    (timestamp, cache_type, operation, key, size_bytes, ttl_seconds)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        metric.timestamp,
                        metric.cache_type,
                        metric.operation,
                        metric.key,
                        metric.size_bytes,
                        metric.ttl_seconds,
                    ),
                )
            else:
                self._data["cache_metrics"].append(asdict(metric))
                self._save_json_data()

        return metric

    def track_component_accuracy(
        self,
        component_type: str,
        identification_method: str,
        confidence_score: float,
        was_correct: bool,
        user_feedback: str | None = None,
    ) -> ComponentAccuracy:
        """Track component identification accuracy."""
        metric = ComponentAccuracy(
            timestamp=datetime.now(),
            component_type=component_type,
            identification_method=identification_method,
            confidence_score=confidence_score,
            was_correct=was_correct,
            user_feedback=user_feedback,
        )

        with self._lock:
            self._accuracy_buffer.append(metric)

            if DUCKDB_AVAILABLE:
                self.conn.execute(
                    """
                    INSERT INTO component_accuracy
                    (timestamp, component_type, identification_method,
                     confidence_score, was_correct, user_feedback)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        metric.timestamp,
                        metric.component_type,
                        metric.identification_method,
                        metric.confidence_score,
                        metric.was_correct,
                        metric.user_feedback,
                    ),
                )
            else:
                self._data["component_accuracy"].append(asdict(metric))
                self._save_json_data()

        return metric

    def track_session_start(
        self,
        session_id: str,
        user_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):
        """Track a user session start."""
        now = datetime.now()
        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            started_at=now,
            last_activity=now,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        with self._sessions_lock:
            self._active_sessions[session_id] = session

            if DUCKDB_AVAILABLE:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO user_sessions
                    (session_id, user_id, started_at, last_activity, ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        session.session_id,
                        session.user_id,
                        session.started_at,
                        session.last_activity,
                        session.ip_address,
                        session.user_agent,
                    ),
                )

    def track_session_activity(self, session_id: str):
        """Update last activity for a session."""
        with self._sessions_lock:
            if session_id in self._active_sessions:
                self._active_sessions[session_id].last_activity = datetime.now()

    def track_session_end(self, session_id: str):
        """Track a user session end."""
        with self._sessions_lock:
            if session_id in self._active_sessions:
                del self._active_sessions[session_id]

    # ═══════════════════════════════════════════════════════════════════════════
    # Aggregation Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def aggregate_minute_metrics(self):
        """Aggregate API metrics to minute buckets."""
        if not DUCKDB_AVAILABLE:
            return

        # Get the last aggregation timestamp
        result = self.conn.execute("SELECT MAX(bucket) FROM api_metrics_minute").fetchone()
        last_bucket = result[0] if result[0] else datetime.now() - timedelta(hours=1)

        # Aggregate new metrics
        self.conn.execute(
            """
            INSERT INTO api_metrics_minute
            SELECT
                DATE_TRUNC('minute', timestamp) as bucket,
                endpoint,
                method,
                COUNT(*) as request_count,
                AVG(response_time_ms) as avg_response_time_ms,
                APPROX_QUANTILE(response_time_ms, 0.95) as p95_response_time_ms,
                APPROX_QUANTILE(response_time_ms, 0.99) as p99_response_time_ms,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count,
                (SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as error_rate_percent
            FROM api_metrics
            WHERE timestamp > ?
            GROUP BY DATE_TRUNC('minute', timestamp), endpoint, method
            ON CONFLICT (bucket, endpoint, method) DO UPDATE SET
                request_count = EXCLUDED.request_count,
                avg_response_time_ms = EXCLUDED.avg_response_time_ms,
                p95_response_time_ms = EXCLUDED.p95_response_time_ms,
                p99_response_time_ms = EXCLUDED.p99_response_time_ms,
                error_count = EXCLUDED.error_count,
                error_rate_percent = EXCLUDED.error_rate_percent
        """,
            (last_bucket,),
        )

    def aggregate_hourly_metrics(self):
        """Aggregate metrics to hourly buckets."""
        if not DUCKDB_AVAILABLE:
            return

        # Aggregate LLM metrics
        self.conn.execute(
            """
            INSERT INTO llm_metrics_hourly
            SELECT
                DATE_TRUNC('hour', timestamp) as bucket,
                model,
                feature,
                COUNT(*) as call_count,
                SUM(tokens_in) as total_tokens_in,
                SUM(tokens_out) as total_tokens_out,
                AVG(latency_ms) as avg_latency_ms,
                SUM(cost_usd) as total_cost_usd,
                SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as error_count,
                (SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as cache_hit_rate
            FROM llm_metrics
            WHERE timestamp > DATE_TRUNC('hour', NOW() - INTERVAL '1 hour')
            GROUP BY DATE_TRUNC('hour', timestamp), model, feature
            ON CONFLICT (bucket, model, feature) DO UPDATE SET
                call_count = EXCLUDED.call_count,
                total_tokens_in = EXCLUDED.total_tokens_in,
                total_tokens_out = EXCLUDED.total_tokens_out,
                avg_latency_ms = EXCLUDED.avg_latency_ms,
                total_cost_usd = EXCLUDED.total_cost_usd,
                error_count = EXCLUDED.error_count,
                cache_hit_rate = EXCLUDED.cache_hit_rate
        """
        )

        # Aggregate DB metrics
        self.conn.execute(
            """
            INSERT INTO db_metrics_hourly
            SELECT
                DATE_TRUNC('hour', timestamp) as bucket,
                query_type,
                table_name,
                COUNT(*) as query_count,
                AVG(execution_time_ms) as avg_execution_time_ms,
                SUM(rows_affected) as total_rows_affected,
                SUM(rows_returned) as total_rows_returned,
                SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as error_count
            FROM db_metrics
            WHERE timestamp > DATE_TRUNC('hour', NOW() - INTERVAL '1 hour')
            GROUP BY DATE_TRUNC('hour', timestamp), query_type, table_name
            ON CONFLICT (bucket, query_type, table_name) DO UPDATE SET
                query_count = EXCLUDED.query_count,
                avg_execution_time_ms = EXCLUDED.avg_execution_time_ms,
                total_rows_affected = EXCLUDED.total_rows_affected,
                total_rows_returned = EXCLUDED.total_rows_returned,
                error_count = EXCLUDED.error_count
        """
        )

        # Aggregate cache metrics
        self.conn.execute(
            """
            INSERT INTO cache_metrics_hourly
            SELECT
                DATE_TRUNC('hour', timestamp) as bucket,
                cache_type,
                SUM(CASE WHEN operation = 'hit' THEN 1 ELSE 0 END) as hits,
                SUM(CASE WHEN operation = 'miss' THEN 1 ELSE 0 END) as misses,
                SUM(CASE WHEN operation = 'set' THEN 1 ELSE 0 END) as sets,
                SUM(CASE WHEN operation = 'delete' THEN 1 ELSE 0 END) as deletes,
                CASE
                    WHEN SUM(CASE WHEN operation IN ('hit', 'miss') THEN 1 ELSE 0 END) > 0
                    THEN SUM(CASE WHEN operation = 'hit' THEN 1 ELSE 0 END) * 100.0 /
                         SUM(CASE WHEN operation IN ('hit', 'miss') THEN 1 ELSE 0 END)
                    ELSE 0
                END as hit_rate_percent
            FROM cache_metrics
            WHERE timestamp > DATE_TRUNC('hour', NOW() - INTERVAL '1 hour')
            GROUP BY DATE_TRUNC('hour', timestamp), cache_type
            ON CONFLICT (bucket, cache_type) DO UPDATE SET
                hits = EXCLUDED.hits,
                misses = EXCLUDED.misses,
                sets = EXCLUDED.sets,
                deletes = EXCLUDED.deletes,
                hit_rate_percent = EXCLUDED.hit_rate_percent
        """
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Query Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def get_active_user_count(self, window_minutes: int = 5) -> int:
        """Get count of active users in the last N minutes."""
        cutoff = datetime.now() - timedelta(minutes=window_minutes)

        with self._sessions_lock:
            # Count sessions with activity in the window
            active = sum(1 for s in self._active_sessions.values() if s.last_activity >= cutoff)
            return active

    def get_api_stats(self, minutes: int = 5) -> dict[str, Any]:
        """Get API statistics for the last N minutes."""
        cutoff = datetime.now() - timedelta(minutes=minutes)

        if DUCKDB_AVAILABLE:
            result = self.conn.execute(
                """
                SELECT
                    COUNT(*) as total_requests,
                    AVG(response_time_ms) as avg_response_time,
                    APPROX_QUANTILE(response_time_ms, 0.95) as p95_response_time,
                    APPROX_QUANTILE(response_time_ms, 0.99) as p99_response_time,
                    SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count,
                    COUNT(DISTINCT user_id) as unique_users
                FROM api_metrics
                WHERE timestamp >= ?
            """,
                (cutoff,),
            ).fetchone()

            return {
                "total_requests": result[0] or 0,
                "avg_response_time_ms": round(result[1] or 0, 2),
                "p95_response_time_ms": round(result[2] or 0, 2),
                "p99_response_time_ms": round(result[3] or 0, 2),
                "error_count": result[4] or 0,
                "error_rate": (result[4] / result[0] * 100) if result[0] else 0,
                "unique_users": result[5] or 0,
            }
        else:
            # JSON fallback
            metrics = [
                m
                for m in self._data["api_metrics"]
                if datetime.fromisoformat(m["timestamp"]) >= cutoff
            ]

            if not metrics:
                return {
                    "total_requests": 0,
                    "avg_response_time_ms": 0,
                    "error_count": 0,
                    "error_rate": 0,
                    "unique_users": 0,
                }

            times = [m["response_time_ms"] for m in metrics]
            errors = sum(1 for m in metrics if m["status_code"] >= 400)

            return {
                "total_requests": len(metrics),
                "avg_response_time_ms": round(statistics.mean(times), 2),
                "error_count": errors,
                "error_rate": round(errors / len(metrics) * 100, 2),
                "unique_users": len(set(m.get("user_id") for m in metrics if m.get("user_id"))),
            }

    def get_llm_stats(self, hours: int = 1) -> dict[str, Any]:
        """Get LLM statistics for the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)

        if DUCKDB_AVAILABLE:
            result = self.conn.execute(
                """
                SELECT
                    COUNT(*) as total_calls,
                    SUM(tokens_in) as total_tokens_in,
                    SUM(tokens_out) as total_tokens_out,
                    SUM(cost_usd) as total_cost,
                    AVG(latency_ms) as avg_latency,
                    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as error_count,
                    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) as cache_hits
                FROM llm_metrics
                WHERE timestamp >= ?
            """,
                (cutoff,),
            ).fetchone()

            return {
                "total_calls": result[0] or 0,
                "total_tokens_in": result[1] or 0,
                "total_tokens_out": result[2] or 0,
                "total_cost_usd": round(result[3] or 0, 4),
                "avg_latency_ms": round(result[4] or 0, 2),
                "error_count": result[5] or 0,
                "cache_hits": result[6] or 0,
            }
        else:
            # JSON fallback
            metrics = [
                m
                for m in self._data["llm_metrics"]
                if datetime.fromisoformat(m["timestamp"]) >= cutoff
            ]

            if not metrics:
                return {
                    "total_calls": 0,
                    "total_tokens_in": 0,
                    "total_tokens_out": 0,
                    "total_cost_usd": 0,
                    "error_count": 0,
                    "cache_hits": 0,
                }

            return {
                "total_calls": len(metrics),
                "total_tokens_in": sum(m["tokens_in"] for m in metrics),
                "total_tokens_out": sum(m["tokens_out"] for m in metrics),
                "total_cost_usd": round(sum(m["cost_usd"] for m in metrics), 4),
                "avg_latency_ms": round(statistics.mean(m["latency_ms"] for m in metrics), 2),
                "error_count": sum(1 for m in metrics if not m["success"]),
                "cache_hits": sum(1 for m in metrics if m.get("cache_hit")),
            }

    def get_endpoint_stats(self, minutes: int = 5, limit: int = 20) -> list[dict[str, Any]]:
        """Get statistics per endpoint."""
        cutoff = datetime.now() - timedelta(minutes=minutes)

        if DUCKDB_AVAILABLE:
            results = self.conn.execute(
                """
                SELECT
                    endpoint,
                    method,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time,
                    APPROX_QUANTILE(response_time_ms, 0.95) as p95_response_time,
                    SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count
                FROM api_metrics
                WHERE timestamp >= ?
                GROUP BY endpoint, method
                ORDER BY request_count DESC
                LIMIT ?
            """,
                (cutoff, limit),
            ).fetchall()

            return [
                {
                    "endpoint": r[0],
                    "method": r[1],
                    "request_count": r[2],
                    "avg_response_time_ms": round(r[3] or 0, 2),
                    "p95_response_time_ms": round(r[4] or 0, 2),
                    "error_count": r[5] or 0,
                }
                for r in results
            ]
        else:
            # JSON fallback with aggregation
            metrics = [
                m
                for m in self._data["api_metrics"]
                if datetime.fromisoformat(m["timestamp"]) >= cutoff
            ]

            stats = defaultdict(lambda: {"times": [], "errors": 0})
            for m in metrics:
                key = (m["endpoint"], m["method"])
                stats[key]["times"].append(m["response_time_ms"])
                if m["status_code"] >= 400:
                    stats[key]["errors"] += 1

            result = []
            for (endpoint, method), data in sorted(
                stats.items(), key=lambda x: -len(x[1]["times"])
            )[:limit]:
                times = data["times"]
                result.append(
                    {
                        "endpoint": endpoint,
                        "method": method,
                        "request_count": len(times),
                        "avg_response_time_ms": round(statistics.mean(times), 2),
                        "error_count": data["errors"],
                    }
                )
            return result

    def get_cache_stats(self, hours: int = 1) -> dict[str, Any]:
        """Get cache statistics."""
        cutoff = datetime.now() - timedelta(hours=hours)

        if DUCKDB_AVAILABLE:
            results = self.conn.execute(
                """
                SELECT
                    cache_type,
                    SUM(CASE WHEN operation = 'hit' THEN 1 ELSE 0 END) as hits,
                    SUM(CASE WHEN operation = 'miss' THEN 1 ELSE 0 END) as misses,
                    SUM(CASE WHEN operation = 'set' THEN 1 ELSE 0 END) as sets,
                    SUM(CASE WHEN operation = 'delete' THEN 1 ELSE 0 END) as deletes
                FROM cache_metrics
                WHERE timestamp >= ?
                GROUP BY cache_type
            """,
                (cutoff,),
            ).fetchall()

            stats = {}
            for r in results:
                hits, misses = r[1] or 0, r[2] or 0
                total = hits + misses
                stats[r[0]] = {
                    "hits": hits,
                    "misses": misses,
                    "sets": r[3] or 0,
                    "deletes": r[4] or 0,
                    "hit_rate": round(hits / total * 100, 2) if total > 0 else 0,
                }
            return stats
        else:
            # JSON fallback
            metrics = [
                m
                for m in self._data["cache_metrics"]
                if datetime.fromisoformat(m["timestamp"]) >= cutoff
            ]

            stats = defaultdict(lambda: {"hits": 0, "misses": 0, "sets": 0, "deletes": 0})
            for m in metrics:
                op = m["operation"]
                if op in stats[m["cache_type"]]:
                    stats[m["cache_type"]][op] += 1

            result = {}
            for cache_type, data in stats.items():
                total = data["hits"] + data["misses"]
                result[cache_type] = {
                    **data,
                    "hit_rate": round(data["hits"] / total * 100, 2) if total > 0 else 0,
                }
            return result

    # ═══════════════════════════════════════════════════════════════════════════
    # Utility Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def register_callback(self, callback: Callable):
        """Register a callback for real-time metric notifications."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable):
        """Unregister a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get a comprehensive metrics summary."""
        api_stats = self.get_api_stats(minutes=5)
        llm_stats = self.get_llm_stats(hours=1)
        cache_stats = self.get_cache_stats(hours=1)
        active_users = self.get_active_user_count(minutes=5)

        return {
            "timestamp": datetime.now().isoformat(),
            "api": api_stats,
            "llm": llm_stats,
            "cache": cache_stats,
            "active_users": active_users,
            "active_sessions": len(self._active_sessions),
        }

    def export_metrics(self, start_time: datetime, end_time: datetime, format: str = "json") -> str:
        """Export metrics to a file."""
        if format == "json":
            if DUCKDB_AVAILABLE:
                # Export from DuckDB
                api_data = (
                    self.conn.execute(
                        "SELECT * FROM api_metrics WHERE timestamp BETWEEN ? AND ?",
                        (start_time, end_time),
                    )
                    .fetchdf()
                    .to_dict("records")
                )
                llm_data = (
                    self.conn.execute(
                        "SELECT * FROM llm_metrics WHERE timestamp BETWEEN ? AND ?",
                        (start_time, end_time),
                    )
                    .fetchdf()
                    .to_dict("records")
                )
            else:
                api_data = [
                    m
                    for m in self._data["api_metrics"]
                    if start_time <= datetime.fromisoformat(m["timestamp"]) <= end_time
                ]
                llm_data = [
                    m
                    for m in self._data["llm_metrics"]
                    if start_time <= datetime.fromisoformat(m["timestamp"]) <= end_time
                ]

            export_data = {
                "exported_at": datetime.now().isoformat(),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "api_metrics": api_data,
                "llm_metrics": llm_data,
            }

            export_path = (
                Path(self.db_path).parent
                / f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(export_path, "w") as f:
                json.dump(export_data, f, indent=2, default=str)

            return str(export_path)

        elif format == "csv":
            # Export to CSV

            export_path = (
                Path(self.db_path).parent / f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if DUCKDB_AVAILABLE:
                # Use DuckDB's CSV export
                self.conn.execute(
                    f"""
                    COPY (
                        SELECT * FROM api_metrics
                        WHERE timestamp BETWEEN '{start_time}' AND '{end_time}'
                    ) TO '{export_path}' (HEADER, DELIMITER ',')
                """
                )

            return str(export_path)

        else:
            raise ValueError(f"Unsupported export format: {format}")

    def cleanup_old_metrics(self, days: int = 30):
        """Clean up metrics older than N days."""
        cutoff = datetime.now() - timedelta(days=days)

        if DUCKDB_AVAILABLE:
            self.conn.execute("DELETE FROM api_metrics WHERE timestamp < ?", (cutoff,))
            self.conn.execute("DELETE FROM llm_metrics WHERE timestamp < ?", (cutoff,))
            self.conn.execute("DELETE FROM db_metrics WHERE timestamp < ?", (cutoff,))
            self.conn.execute("DELETE FROM cache_metrics WHERE timestamp < ?", (cutoff,))
            self.conn.execute("DELETE FROM component_accuracy WHERE timestamp < ?", (cutoff,))
        else:
            for key in [
                "api_metrics",
                "llm_metrics",
                "db_metrics",
                "cache_metrics",
                "component_accuracy",
            ]:
                self._data[key] = [
                    m for m in self._data[key] if datetime.fromisoformat(m["timestamp"]) >= cutoff
                ]
            self._save_json_data()


# Lazy singleton — defers DB connection until first use so test collection
# doesn't lock the live server's database files.
class _LazyMetrics:
    _obj = None
    def __getattr__(self, n):
        if self._obj is None:
            self._obj = MetricsCollector()
        return getattr(self._obj, n)

metrics_collector = _LazyMetrics()


def track_api_request(*args, **kwargs) -> APIMetric:
    """Convenience function to track API request."""
    return metrics_collector.track_api_request(*args, **kwargs)


def track_llm_call(*args, **kwargs) -> LLMMetric:
    """Convenience function to track LLM call."""
    return metrics_collector.track_llm_call(*args, **kwargs)


def track_db_query(*args, **kwargs) -> DBMetric:
    """Convenience function to track DB query."""
    return metrics_collector.track_db_query(*args, **kwargs)


def track_cache_op(*args, **kwargs) -> CacheMetric:
    """Convenience function to track cache operation."""
    return metrics_collector.track_cache_op(*args, **kwargs)


def timed_endpoint(endpoint_name: str):
    """Decorator to automatically time API endpoints."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            error_type = None
            status_code = 200

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_type = type(e).__name__
                status_code = 500
                raise
            finally:
                elapsed_ms = (time.time() - start_time) * 1000
                metrics_collector.track_api_request(
                    endpoint=endpoint_name,
                    method="GET",  # Default, can be overridden
                    status_code=status_code,
                    response_time_ms=elapsed_ms,
                    error_type=error_type,
                )

        return wrapper

    return decorator



