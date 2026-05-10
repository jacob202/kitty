"""
Memory Weave - Temporal Knowledge Graph for Kitty.

Problem: Kitty forgets what failed yesterday and tries the same broken approach.
Current memory is just static JSON blobs.

Solution: A temporal knowledge graph that tracks:
- Provenance (where did this fact come from?)
- Confidence decay (facts get stale over time)
- Conflict resolution (contradicting facts get weighted)
- Event patterns (API failures, user corrections, etc.)

The Weave learns from:
1. User corrections ("No, it's 47Ω not 470Ω")
2. Tool failures (DeepSeek timeout at 2am)
3. Source conflicts (web says X, manual says Y)
"""

import json
import math
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum

from src.core.db_config import get_db_path

_DB_PATH = get_db_path("memory_weave")
_lock = threading.Lock()

_CACHE_MAX_SIZE = 500
_CACHE_TTL_SECONDS = 1800  # 30 minutes


def _init_db():
    _DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(str(_DB_PATH)) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=-8192")

        # Knowledge graph edges
        c.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity TEXT NOT NULL,
                relation TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source TEXT NOT NULL,
                source_type TEXT DEFAULT 'unknown',
                timestamp TEXT NOT NULL,
                last_verified TEXT,
                deprecated INTEGER DEFAULT 0,
                deprecated_by INTEGER,
                deprecated_reason TEXT,
                UNIQUE(entity, relation, source)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_edges_entity ON edges(entity)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_edges_timestamp ON edges(timestamp)")

        # Events (failures, corrections, etc.)
        c.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity TEXT,
                description TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")

        # Temporal reliability windows
        c.execute("""
            CREATE TABLE IF NOT EXISTS reliability_windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource TEXT NOT NULL,
                reliability TEXT DEFAULT 'unknown',
                window_start TEXT,
                window_end TEXT,
                failure_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                last_updated TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_reliability_resource ON reliability_windows(resource)")

        # Conversation logs for pattern analysis
        c.execute("""
            CREATE TABLE IF NOT EXISTS conversation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                annotated INTEGER DEFAULT 0
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON conversation_logs(timestamp)")

        c.commit()


_init_db()


class SourceType(Enum):
    USER_CORRECTION = "user_correction"
    USER_MANUAL = "user_manual"
    VERBAL_CONFIRMATION = "verbal_confirmation"
    WEB_SEARCH = "web_search"
    DOCUMENT = "document"
    KITTYP_GUESS = "kitty_guess"
    KITTYP_CORRECTED = "kitty_corrected"
    TRAINING_DATA = "training_data"
    UNKNOWN = "unknown"


@dataclass
class WeaveEdge:
    """A fact edge in the knowledge graph."""

    id: int | None
    entity: str
    relation: str
    value: str
    confidence: float
    source: str
    source_type: str
    timestamp: str
    last_verified: str | None = None
    deprecated: bool = False
    deprecated_by: int | None = None
    deprecated_reason: str | None = None

    @property
    def age_days(self) -> float:
        """How many days since this edge was created."""
        created = datetime.fromisoformat(self.timestamp)
        return (datetime.now() - created).total_seconds() / 86400


@dataclass
class WeaveQuery:
    """Query result from the Memory Weave."""

    fact: str
    confidence: float
    last_verified: str | None
    source_chain: list[str]
    related_failures: list[str]
    is_stale: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class MemoryWeave:
    """
    Temporal knowledge graph with confidence decay and conflict resolution.

    Core operations:
    - weave.fact(entity, relation, value, source=...)  # Add a fact
    - weave.query(entity, relation)  # Get best fact
    - weave.correct(entity, relation, new_value, reason=...)  # Deprecate old, add new
    - weave.event(event_type, description)  # Log an event
    - weave.get_reliability(resource)  # Check temporal reliability
    """

    # Decay parameters
    DECAY_LAMBDA = 0.023  # e^(-0.023 * 30) ≈ 0.5 after 30 days
    STALE_THRESHOLD_DAYS = 30
    CORRECTION_BOOST = 0.98  # User corrections get high confidence

    def __init__(self):
        self._cache: dict[tuple[str, str], list[WeaveEdge]] = {}
        self._cache_timestamps: dict[tuple[str, str], float] = {}

    # ========================================================================
    # CORE OPERATIONS
    # ========================================================================

    def fact(
        self,
        entity: str,
        relation: str,
        value: str,
        source: str,
        source_type: str = "unknown",
        confidence: float = 0.5,
    ) -> int:
        """
        Weave a new fact into the graph.

        Args:
            entity: The thing (e.g., "PTH487A", "Sansui AU-7900")
            relation: The attribute (e.g., "resistance", "uses_transistor")
            value: The value (e.g., "47Ω", "2SA726")
            source: Where this came from (e.g., "user manual pg 23")
            source_type: Type of source for weighting
            confidence: Initial confidence (0-1)

        Returns:
            Edge ID
        """
        now = datetime.now().isoformat()

        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                cursor = c.execute(
                    """
                    INSERT INTO edges
                    (entity, relation, value, confidence, source, source_type, timestamp, last_verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (entity, relation, value, confidence, source, source_type, now, now),
                )
                edge_id = cursor.lastrowid
                c.commit()

        # Invalidate cache
        self._cache.pop((entity, relation), None)
        return edge_id

    def correct(
        self,
        entity: str,
        relation: str,
        new_value: str,
        source: str,
        source_type: str = "user_correction",
        reason: str = None,
    ) -> int:
        """
        Deprecate old fact(s) and weave a corrected one.

        When a user says "No, it's 47Ω not 470Ω", this:
        1. Deprecates the old edge(s)
        2. Creates new edge with high confidence
        3. Links new to old via deprecated_by

        Args:
            entity, relation: What to correct
            new_value: The new correct value
            source: Who/what corrected it
            source_type: Type of correction
            reason: Why it was wrong

        Returns:
            New edge ID
        """
        now = datetime.now().isoformat()

        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                # Find and deprecate old edges
                old_edges = c.execute(
                    """
                    SELECT id FROM edges
                    WHERE entity = ? AND relation = ? AND deprecated = 0
                """,
                    (entity, relation),
                ).fetchall()

                for (old_id,) in old_edges:
                    c.execute(
                        """
                        UPDATE edges
                        SET deprecated = 1,
                            deprecated_by = (SELECT COALESCE(MAX(id), 0) + 1 FROM edges),
                            deprecated_reason = ?
                        WHERE id = ?
                    """,
                        (reason or "user correction", old_id),
                    )

                # Log the correction event
                c.execute(
                    """
                    INSERT INTO events (event_type, entity, description, severity, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        "correction",
                        entity,
                        f"Corrected {relation} from old to {new_value}",
                        "info",
                        now,
                        json.dumps(
                            {"old_values": [e[0] for e in old_edges], "new_value": new_value}
                        ),
                    ),
                )

                # Create new edge with boost
                new_confidence = self.CORRECTION_BOOST
                cursor = c.execute(
                    """
                    INSERT INTO edges
                    (entity, relation, value, confidence, source, source_type, timestamp, last_verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (entity, relation, new_value, new_confidence, source, source_type, now, now),
                )
                edge_id = cursor.lastrowid
                c.commit()

        self._cache.pop((entity, relation), None)
        return edge_id

    def event(
        self,
        event_type: str,
        entity: str = None,
        description: str = None,
        severity: str = "info",
        metadata: dict = None,
    ):
        """
        Log an event (failure, success, etc.).

        Example: weave.event("api_timeout", "DeepSeek", "Timeout at 2am")
        """
        now = datetime.now().isoformat()

        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                c.execute(
                    """
                    INSERT INTO events (event_type, entity, description, severity, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (event_type, entity, description, severity, now, json.dumps(metadata or {})),
                )
                c.commit()

    def get_recent_events(self, event_type: str = None, hours: int = 24, limit: int = 50) -> list[dict]:
        """Get recent events from the weave."""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                sql = "SELECT event_type, entity, description, severity, timestamp, metadata FROM events WHERE timestamp > ?"
                params = [cutoff]
                if event_type:
                    sql += " AND event_type = ?"
                    params.append(event_type)
                sql += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                rows = c.execute(sql, params).fetchall()

        return [
            {
                "event_type": r[0],
                "entity": r[1],
                "description": r[2],
                "severity": r[3],
                "timestamp": r[4],
                "metadata": json.loads(r[5]) if r[5] else {}
            }
            for r in rows
        ]

    def query(self, entity: str, relation: str) -> WeaveQuery | None:
        """
        Query for the best fact matching entity+relation.

        Applies:
        - Confidence decay (older facts lose confidence)
        - Source weighting (user corrections > web > training)
        - Deprecation filtering

        Returns:
            WeaveQuery with best fact, or None if no match
        """
        # Check cache
        cache_key = (entity, relation)
        if cache_key not in self._cache:
            self._load_edges(entity, relation)

        edges = self._cache.get(cache_key, [])
        if not edges:
            return None

        # Score and rank edges
        scored = []
        for edge in edges:
            if edge.deprecated:
                continue

            score = self._calculate_score(edge)
            scored.append((score, edge))

        if not scored:
            return None

        # Get best
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_edge = scored[0]

        # Get source chain
        source_chain = self._build_source_chain(best_edge)

        # Get related failures
        related_failures = self._get_related_failures(entity, relation)

        # Check staleness
        is_stale = best_edge.age_days > self.STABLE_THRESHOLD_DAYS

        return WeaveQuery(
            fact=f"{best_edge.entity} {best_edge.relation} = {best_edge.value}",
            confidence=best_score,
            last_verified=best_edge.last_verified,
            source_chain=source_chain,
            related_failures=related_failures,
            is_stale=is_stale,
        )

    def get_reliability(self, resource: str, current_time: datetime = None) -> dict:
        """
        Check temporal reliability of a resource (API, model, etc.).

        Returns reliability score based on recent failure/success patterns.
        Useful for routing decisions (e.g., "DeepSeek has been flaky at 2am").
        """
        current_time = current_time or datetime.now()

        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                # Get recent events for this resource
                window_start = (current_time - timedelta(hours=6)).isoformat()
                recent_events = c.execute(
                    """
                    SELECT event_type, COUNT(*) as count
                    FROM events
                    WHERE entity = ? AND timestamp > ?
                    GROUP BY event_type
                """,
                    (resource, window_start),
                ).fetchall()

                failures = sum(count for et, count in recent_events if "fail" in et.lower())
                successes = sum(count for et, count in recent_events if "success" in et.lower())
                total = failures + successes

                if total == 0:
                    reliability = "unknown"
                    score = 0.5
                else:
                    score = successes / total
                    if score > 0.9:
                        reliability = "high"
                    elif score > 0.7:
                        reliability = "medium"
                    else:
                        reliability = "low"

                return {
                    "resource": resource,
                    "reliability": reliability,
                    "score": score,
                    "recent_failures": failures,
                    "recent_successes": successes,
                    "window": "last 6 hours",
                }

    def get_conflicts(self, entity: str, relation: str) -> list[WeaveQuery]:
        """Get all conflicting values for an entity+relation."""
        edges = self._cache.get((entity, relation), [])
        if not edges:
            self._load_edges(entity, relation)
            edges = self._cache.get((entity, relation), [])

        return [
            WeaveQuery(
                fact=f"{e.entity} {e.relation} = {e.value}",
                confidence=self._calculate_score(e),
                last_verified=e.last_verified,
                source_chain=[e.source],
                related_failures=[],
                is_stale=e.age_days > self.STABLE_THRESHOLD_DAYS,
            )
            for e in edges
            if not e.deprecated
        ]

    def surface_conflict(self, entity: str, relation: str) -> dict:
        """
        Surface a conflict to the orchestrator with evidence weights.
        Used when multiple sources disagree.

        Returns dict with conflicting facts and recommendation.
        """
        conflicts = self.get_conflicts(entity, relation)

        if len(conflicts) < 2:
            return {"has_conflict": False}

        # Sort by confidence
        conflicts.sort(key=lambda x: x.confidence, reverse=True)

        return {
            "has_conflict": True,
            "conflicts": [c.to_dict() for c in conflicts[:5]],
            "recommendation": "Surface ambiguity to user for clarification",
            "best_fact": conflicts[0].to_dict() if conflicts else None,
        }

    # ========================================================================
    # INTERNAL HELPERS
    # ========================================================================

    def _load_edges(self, entity: str, relation: str):
        """Load edges from DB into cache with TTL eviction."""
        now = time.time()

        # Periodic eviction of stale and oversized cache
        if len(self._cache) > _CACHE_MAX_SIZE:
            stale_keys = [k for k, ts in self._cache_timestamps.items() if now - ts > _CACHE_TTL_SECONDS]
            for k in stale_keys:
                self._cache.pop(k, None)
                self._cache_timestamps.pop(k, None)

            # If still too large, evict oldest half
            if len(self._cache) > _CACHE_MAX_SIZE:
                sorted_keys = sorted(self._cache_timestamps, key=self._cache_timestamps.get)
                for k in sorted_keys[:len(sorted_keys) // 2]:
                    self._cache.pop(k, None)
                    self._cache_timestamps.pop(k, None)

        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                rows = c.execute(
                    """
                    SELECT id, entity, relation, value, confidence, source,
                           source_type, timestamp, last_verified, deprecated,
                           deprecated_by, deprecated_reason
                    FROM edges
                    WHERE entity = ? AND (relation = ? OR ? = '*')
                """,
                    (entity, relation, relation),
                ).fetchall()

        edges = [
            WeaveEdge(
                id=r[0],
                entity=r[1],
                relation=r[2],
                value=r[3],
                confidence=r[4],
                source=r[5],
                source_type=r[6],
                timestamp=r[7],
                last_verified=r[8],
                deprecated=bool(r[9]),
                deprecated_by=r[10],
                deprecated_reason=r[11],
            )
            for r in rows
        ]
        self._cache[(entity, relation)] = edges
        self._cache_timestamps[(entity, relation)] = time.time()

    def _calculate_score(self, edge: WeaveEdge) -> float:
        """Calculate confidence score with decay."""
        # Base decay
        days = edge.age_days
        decay = math.exp(-self.DECAY_LAMBDA * days)

        # Source weighting
        source_weights = {
            "user_correction": 1.0,
            "verbal_confirmation": 0.95,
            "user_manual": 0.9,
            "document": 0.85,
            "web_search": 0.7,
            "kitty_corrected": 0.6,
            "training_data": 0.4,
            "unknown": 0.3,
        }
        source_weight = source_weights.get(edge.source_type, 0.5)

        # Combined score
        score = edge.confidence * decay * source_weight
        return min(1.0, score)

    def _build_source_chain(self, edge: WeaveEdge) -> list[str]:
        """Build the chain of sources for an edge."""
        chain = [edge.source]

        # Follow deprecation chain backwards
        current = edge
        while current.deprecated_by:
            with _lock:
                with sqlite3.connect(str(_DB_PATH)) as c:
                    parent = c.execute(
                        """
                        SELECT source FROM edges WHERE id = ?
                    """,
                        (current.deprecated_by,),
                    ).fetchone()

            if parent:
                chain.append(f"(superseded) {parent[0]}")
                break
            else:
                break

        return chain

    def _get_related_failures(self, entity: str, relation: str) -> list[str]:
        """Get failures related to this entity+relation."""
        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                failures = c.execute(
                    """
                    SELECT description, timestamp FROM events
                    WHERE entity = ? AND (event_type LIKE '%fail%' OR event_type LIKE '%error%')
                    ORDER BY timestamp DESC LIMIT 5
                """,
                    (entity,),
                ).fetchall()

        return [f"{f[1]}: {f[0]}" for f in failures]

    # ========================================================================
    # LOGGING & ANALYSIS
    # ========================================================================

    def log_conversation(self, role: str, content: str):
        """Log a conversation turn for pattern analysis."""
        now = datetime.now().isoformat()

        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                c.execute(
                    """
                    INSERT INTO conversation_logs (timestamp, role, content)
                    VALUES (?, ?, ?)
                """,
                    (now, role, content),
                )
                c.commit()

    def detect_corrections(self, hours: int = 24) -> list[dict]:
        """Detect user corrections in recent conversations."""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                logs = c.execute(
                    """
                    SELECT timestamp, role, content FROM conversation_logs
                    WHERE timestamp > ? AND role = 'user'
                    ORDER BY timestamp DESC
                """,
                    (cutoff,),
                ).fetchall()

        # Pattern match for corrections
        correction_patterns = [
            r"no[,\s]+(actually|wait)",
            r"it'?s\s+not\s+",
            r"wrong\s*[,:]",
            r"(should be|needs to be)\s+",
            r"try\s+(the|that)\s+",
        ]

        corrections = []
        for timestamp, role, content in logs:
            for pattern in correction_patterns:
                import re

                if re.search(pattern, content, re.IGNORECASE):
                    corrections.append(
                        {
                            "timestamp": timestamp,
                            "content": content,
                            "pattern": pattern,
                        }
                    )
                    break

        return corrections

    def get_stale_facts(self, days: int = 30) -> list[WeaveEdge]:
        """Get facts that haven't been verified in N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                rows = c.execute(
                    """
                    SELECT id, entity, relation, value, confidence, source,
                           source_type, timestamp, last_verified, deprecated,
                           deprecated_by, deprecated_reason
                    FROM edges
                    WHERE last_verified < ? AND deprecated = 0
                """,
                    (cutoff,),
                ).fetchall()

        return [
            WeaveEdge(
                id=r[0],
                entity=r[1],
                relation=r[2],
                value=r[3],
                confidence=r[4],
                source=r[5],
                source_type=r[6],
                timestamp=r[7],
                last_verified=r[8],
                deprecated=bool(r[9]),
                deprecated_by=r[10],
                deprecated_reason=r[11],
            )
            for r in rows
        ]


# Singleton instance
_weave = None


def get_weave() -> MemoryWeave:
    """Get the singleton Memory Weave instance."""
    global _weave
    if _weave is None:
        _weave = MemoryWeave()
    return _weave
