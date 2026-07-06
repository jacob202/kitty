"""Memory Weave — temporal knowledge graph for Kitty.

Ported from ``~/Projects/kitty-salvage/memory/memory_weave.py`` (the
abandoned ``src/*`` architecture, 737 lines) onto the current
``gateway/storage_router`` + ``memory_graph`` substrate. See
``docs/plans/chore-master-fix-and-deepen.md`` (C-track) and the salvage
dig verdict at ``~/Projects/kitty-salvage/README.md``.

The MemoryWeave is a temporal knowledge graph that tracks facts with
provenance, confidence decay, and conflict resolution. It learns from:
  1. User corrections ("No, it's 47Ω not 470Ω")
  2. Tool failures (DeepSeek timeout at 2am)
  3. Source conflicts (web says X, manual says Y)

Core operations:
  - ``weave.fact(entity, relation, value, source=...)`` — add a fact
  - ``weave.query(entity, relation)`` — get the best fact (with decay)
  - ``weave.correct(entity, relation, new_value, reason=...)`` — deprecate old, add new
  - ``weave.event(event_type, description)`` — log an event
  - ``weave.get_reliability(resource)`` — temporal reliability score

Status (2026-07-05):
  - Schema landed as migration 013 (``gateway/migrations/013_memory_weave.sql``).
  - Core operations ported: ``fact``, ``correct``, ``event``,
    ``get_recent_events``, ``query`` (with its 4 private helpers).
  - Remaining methods stubbed with ``NotImplementedError`` for next session:
    ``get_reliability``, ``get_conflicts``, ``surface_conflict``,
    ``log_conversation``, ``detect_corrections``, ``get_stale_facts``.
"""
from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

_lock = threading.Lock()

_CACHE_MAX_SIZE = 500
_CACHE_TTL_SECONDS = 1800  # 30 minutes


# ── Enums and dataclasses (port verbatim) ─────────────────────────────


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

    id: Optional[int]
    entity: str
    relation: str
    value: str
    confidence: float
    source: str
    source_type: str
    timestamp: str
    last_verified: Optional[str] = None
    deprecated: bool = False
    deprecated_by: Optional[int] = None
    deprecated_reason: Optional[str] = None

    @property
    def age_days(self) -> float:
        """How many days since this edge was created."""
        created = datetime.fromisoformat(self.timestamp)
        return (datetime.now() - created).total_seconds() / 86400


@dataclass
class WeaveQuery:
    """Result of a knowledge graph query, with provenance + confidence."""

    fact: str
    confidence: float
    last_verified: Optional[str]
    source_chain: list[str]
    related_failures: list[str]
    is_stale: bool

    def to_dict(self) -> dict:
        return {
            "fact": self.fact,
            "confidence": self.confidence,
            "last_verified": self.last_verified,
            "source_chain": list(self.source_chain),
            "related_failures": list(self.related_failures),
            "is_stale": self.is_stale,
        }


# ── Class ─────────────────────────────────────────────────────────────


class MemoryWeave:
    """Temporal knowledge graph with confidence decay and conflict resolution.

    Core operations:
      - ``fact(entity, relation, value, source=...)`` — add a fact
      - ``query(entity, relation)`` — get best fact
      - ``correct(entity, relation, new_value, reason=...)`` — deprecate old, add new
      - ``event(event_type, description)`` — log an event
      - ``get_reliability(resource)`` — temporal reliability score
    """

    DECAY_LAMBDA = 0.023  # e^(-0.023 * 30) ≈ 0.5 after 30 days
    STALE_THRESHOLD_DAYS = 30
    CORRECTION_BOOST = 0.98  # User corrections get high confidence

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], list[WeaveEdge]] = {}
        self._cache_timestamps: dict[tuple[str, str], float] = {}

    # ── CORE OPERATIONS (ported) ───────────────────────────────────────

    def fact(
        self,
        entity: str,
        relation: str,
        value: str,
        source: str,
        source_type: str = "unknown",
        confidence: float = 0.5,
    ) -> int:
        """Weave a new fact into the graph. Returns edge ID."""
        now = datetime.now().isoformat()

        with _lock:
            with kitty_db.connect(KITTY_DB_FILE) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO weave_edges
                    (entity, relation, value, confidence, source, source_type,
                     timestamp, last_verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (entity, relation, value, confidence, source, source_type, now, now),
                )
                edge_id = cursor.lastrowid
                conn.commit()

        self._cache.pop((entity, relation), None)
        return edge_id

    def correct(
        self,
        entity: str,
        relation: str,
        new_value: str,
        source: str,
        source_type: str = "user_correction",
        reason: Optional[str] = None,
    ) -> int:
        """Deprecate old fact(s) and weave a corrected one. Returns new edge ID."""
        now = datetime.now().isoformat()

        with _lock:
            with kitty_db.connect(KITTY_DB_FILE) as conn:
                old_edges = conn.execute(
                    """
                    SELECT id FROM weave_edges
                    WHERE entity = ? AND relation = ? AND deprecated = 0
                    """,
                    (entity, relation),
                ).fetchall()

                for (old_id,) in old_edges:
                    conn.execute(
                        """
                        UPDATE weave_edges
                        SET deprecated = 1,
                            deprecated_by = (SELECT COALESCE(MAX(id), 0) + 1 FROM weave_edges),
                            deprecated_reason = ?
                        WHERE id = ?
                        """,
                        (reason or "user correction", old_id),
                    )

                conn.execute(
                    """
                    INSERT INTO weave_events
                    (event_type, entity, description, severity, timestamp, metadata)
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

                new_confidence = self.CORRECTION_BOOST
                cursor = conn.execute(
                    """
                    INSERT INTO weave_edges
                    (entity, relation, value, confidence, source, source_type,
                     timestamp, last_verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (entity, relation, new_value, new_confidence, source, source_type, now, now),
                )
                edge_id = cursor.lastrowid
                conn.commit()

        self._cache.pop((entity, relation), None)
        return edge_id

    def event(
        self,
        event_type: str,
        entity: Optional[str] = None,
        description: Optional[str] = None,
        severity: str = "info",
        metadata: Optional[dict] = None,
    ) -> None:
        """Log an event (failure, success, etc.)."""
        now = datetime.now().isoformat()

        with _lock:
            with kitty_db.connect(KITTY_DB_FILE) as conn:
                conn.execute(
                    """
                    INSERT INTO weave_events
                    (event_type, entity, description, severity, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (event_type, entity, description, severity, now, json.dumps(metadata or {})),
                )
                conn.commit()

    def get_recent_events(
        self,
        event_type: Optional[str] = None,
        hours: int = 24,
        limit: int = 50,
    ) -> list[dict]:
        """Get recent events from the weave."""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with _lock:
            with kitty_db.connect(KITTY_DB_FILE) as conn:
                sql = (
                    "SELECT event_type, entity, description, severity, timestamp, metadata "
                    "FROM weave_events WHERE timestamp > ?"
                )
                params: list = [cutoff]
                if event_type:
                    sql += " AND event_type = ?"
                    params.append(event_type)
                sql += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(sql, params).fetchall()

        return [
            {
                "event_type": r[0],
                "entity": r[1],
                "description": r[2],
                "severity": r[3],
                "timestamp": r[4],
                "metadata": json.loads(r[5]) if r[5] else {},
            }
            for r in rows
        ]

    def query(self, entity: str, relation: str) -> Optional[WeaveQuery]:
        """Query for the best fact matching entity+relation.

        Applies confidence decay, source weighting, deprecation filtering.
        Returns a WeaveQuery, or None if no match.
        """
        cache_key = (entity, relation)
        if cache_key not in self._cache:
            self._load_edges(entity, relation)

        edges = self._cache.get(cache_key, [])
        if not edges:
            return None

        scored: list[tuple[float, WeaveEdge]] = []
        for edge in edges:
            if edge.deprecated:
                continue
            score = self._calculate_score(edge)
            scored.append((score, edge))

        if not scored:
            return None

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_edge = scored[0]
        source_chain = self._build_source_chain(best_edge)
        related_failures = self._get_related_failures(entity, relation)
        is_stale = best_edge.age_days > self.STALE_THRESHOLD_DAYS

        return WeaveQuery(
            fact=f"{best_edge.entity} {best_edge.relation} = {best_edge.value}",
            confidence=best_score,
            last_verified=best_edge.last_verified,
            source_chain=source_chain,
            related_failures=related_failures,
            is_stale=is_stale,
        )

    # ── PRIVATE HELPERS (ported for query()) ──────────────────────────

    def _load_edges(self, entity: str, relation: str) -> None:
        """Load all non-deprecated edges for (entity, relation) into the cache."""
        with _lock:
            with kitty_db.connect(KITTY_DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT * FROM weave_edges
                    WHERE entity = ? AND relation = ? AND deprecated = 0
                    ORDER BY timestamp DESC
                    """,
                    (entity, relation),
                ).fetchall()

        edges = [
            WeaveEdge(
                id=row["id"],
                entity=row["entity"],
                relation=row["relation"],
                value=row["value"],
                confidence=row["confidence"],
                source=row["source"],
                source_type=row["source_type"],
                timestamp=row["timestamp"],
                last_verified=row["last_verified"],
                deprecated=bool(row["deprecated"]),
                deprecated_by=row["deprecated_by"],
                deprecated_reason=row["deprecated_reason"],
            )
            for row in rows
        ]

        # Evict oldest cache entries if over the cap
        if len(self._cache) >= _CACHE_MAX_SIZE:
            oldest = min(self._cache_timestamps.items(), key=lambda kv: kv[1])[0]
            self._cache.pop(oldest, None)
            self._cache_timestamps.pop(oldest, None)

        self._cache[(entity, relation)] = edges
        self._cache_timestamps[(entity, relation)] = time.time()

    def _calculate_score(self, edge: WeaveEdge) -> float:
        """Score = base_confidence * decay * source_weight."""
        base = edge.confidence
        age = edge.age_days
        decay = math.exp(-self.DECAY_LAMBDA * age)
        source_weight = self._source_weight(edge.source_type)
        return base * decay * source_weight

    def _build_source_chain(self, edge: WeaveEdge) -> list[str]:
        """Build a human-readable chain: how did we get to this fact?"""
        chain = [f"{edge.source_type}: {edge.source}"]
        if edge.deprecated_by:
            # Could recurse, but for now stop at one hop
            with _lock:
                with kitty_db.connect(KITTY_DB_FILE) as conn:
                    parent = conn.execute(
                        "SELECT source, source_type FROM weave_edges WHERE id = ?",
                        (edge.deprecated_by,),
                    ).fetchone()
            if parent:
                chain.append(f"supersedes {parent[1]}: {parent[0]}")
        return chain

    def _get_related_failures(self, entity: str, relation: str) -> list[str]:
        """Find recent failure events mentioning this entity."""
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        with _lock:
            with kitty_db.connect(KITTY_DB_FILE) as conn:
                rows = conn.execute(
                    """
                    SELECT description FROM weave_events
                    WHERE entity = ? AND event_type LIKE '%fail%' AND timestamp > ?
                    ORDER BY timestamp DESC LIMIT 5
                    """,
                    (entity, cutoff),
                ).fetchall()
        return [r[0] for r in rows if r[0]]

    def _source_weight(self, source_type: str) -> float:
        """Weight by source authority. User corrections > manual > web > training."""
        weights = {
            SourceType.USER_CORRECTION.value: 1.0,
            SourceType.USER_MANUAL.value: 0.95,
            SourceType.VERBAL_CONFIRMATION.value: 0.9,
            SourceType.DOCUMENT.value: 0.85,
            SourceType.WEB_SEARCH.value: 0.6,
            SourceType.KITTYP_CORRECTED.value: 0.7,
            SourceType.KITTYP_GUESS.value: 0.3,
            SourceType.TRAINING_DATA.value: 0.4,
            SourceType.UNKNOWN.value: 0.5,
        }
        return weights.get(source_type, 0.5)

    # ── RELIABILITY + CONFLICTS (port) ─────────────────────────────────

    def get_reliability(
        self, resource: str, current_time: Optional[datetime] = None
    ) -> dict:
        """Check temporal reliability of a resource (API, model, etc.).

        Returns reliability score based on recent failure/success patterns.
        Useful for routing decisions (e.g., "DeepSeek has been flaky at 2am").
        """
        current_time = current_time or datetime.now()

        with _lock:
            with kitty_db.connect(KITTY_DB_FILE) as conn:
                window_start = (current_time - timedelta(hours=6)).isoformat()
                recent_events = conn.execute(
                    """
                    SELECT event_type, COUNT(*) AS count
                    FROM weave_events
                    WHERE entity = ? AND timestamp > ?
                    GROUP BY event_type
                    """,
                    (resource, window_start),
                ).fetchall()

        failures = sum(count for et, count in recent_events if "fail" in et.lower())
        successes = sum(
            count for et, count in recent_events if "success" in et.lower()
        )
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
                is_stale=e.age_days > self.STALE_THRESHOLD_DAYS,
            )
            for e in edges
            if not e.deprecated
        ]

    def surface_conflict(self, entity: str, relation: str) -> dict:
        """Surface a conflict to the orchestrator with evidence weights.

        Used when multiple sources disagree. Returns dict with conflicting
        facts and a recommendation.
        """
        conflicts = self.get_conflicts(entity, relation)

        if len(conflicts) < 2:
            return {"has_conflict": False}

        conflicts.sort(key=lambda x: x.confidence, reverse=True)

        return {
            "has_conflict": True,
            "conflicts": [c.to_dict() for c in conflicts[:5]],
            "recommendation": "Surface ambiguity to user for clarification",
            "best_fact": conflicts[0].to_dict() if conflicts else None,
        }

    # ── LOGGING + ANALYSIS (port) ───────────────────────────────────────

    def log_conversation(self, role: str, content: str) -> None:
        """Log a conversation turn for pattern analysis."""
        now = datetime.now().isoformat()

        with _lock:
            with kitty_db.connect(KITTY_DB_FILE) as conn:
                conn.execute(
                    """
                    INSERT INTO weave_conversation_logs (timestamp, role, content)
                    VALUES (?, ?, ?)
                    """,
                    (now, role, content),
                )
                conn.commit()

    def detect_corrections(self, hours: int = 24) -> list[dict]:
        """Detect user corrections in recent conversations via regex patterns."""
        import re

        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        correction_patterns = [
            r"no[,\s]+(actually|wait)",
            r"it'?s\s+not\s+",
            r"wrong\s*[,:]",
            r"(should be|needs to be)\s+",
            r"try\s+(the|that)\s+",
        ]
        compiled = [re.compile(p, re.IGNORECASE) for p in correction_patterns]

        with _lock:
            with kitty_db.connect(KITTY_DB_FILE) as conn:
                logs = conn.execute(
                    """
                    SELECT timestamp, role, content FROM weave_conversation_logs
                    WHERE timestamp > ? AND role = 'user'
                    ORDER BY timestamp DESC
                    """,
                    (cutoff,),
                ).fetchall()

        corrections: list[dict] = []
        for timestamp, _role, content in logs:
            for pattern in compiled:
                if pattern.search(content):
                    corrections.append(
                        {
                            "timestamp": timestamp,
                            "content": content,
                            "pattern": pattern.pattern,
                        }
                    )
                    break
        return corrections

    def get_stale_facts(self, days: int = 30) -> list[WeaveEdge]:
        """Get facts that haven't been verified in N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with _lock:
            with kitty_db.connect(KITTY_DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT * FROM weave_edges
                    WHERE last_verified < ? AND deprecated = 0
                    """,
                    (cutoff,),
                ).fetchall()
        return [
            WeaveEdge(
                id=row["id"],
                entity=row["entity"],
                relation=row["relation"],
                value=row["value"],
                confidence=row["confidence"],
                source=row["source"],
                source_type=row["source_type"],
                timestamp=row["timestamp"],
                last_verified=row["last_verified"],
                deprecated=bool(row["deprecated"]),
                deprecated_by=row["deprecated_by"],
                deprecated_reason=row["deprecated_reason"],
            )
            for row in rows
        ]


# ── Module-level singleton (matches the original pattern) ──────────────


_weave: Optional[MemoryWeave] = None


def get_weave() -> MemoryWeave:
    """Return the process-wide MemoryWeave singleton."""
    global _weave
    if _weave is None:
        _weave = MemoryWeave()
    return _weave
