"""
Correction Memory - Stores user corrections and injects them into context.
Use: /fix <correction text> to teach Kitty.

Extended with:
- Categories: Component ID, Procedure, Safety, Theory
- Correction count tracking per category/component
- Finetune trigger at 50 total corrections
- 5x weighting for correction retrieval
- Teach-back summary generation
- Transparency: track which corrections were used
"""

import json
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import chromadb
    from chromadb.config import Settings
    from textblob import TextBlob
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


class CorrectionCategory(str, Enum):
    """Categories for corrections to enable targeted tracking and retrieval."""

    COMPONENT_ID = "component_id"  # Component identification corrections
    PROCEDURE = "procedure"  # Procedure/step corrections
    SAFETY = "safety"  # Safety-related corrections
    THEORY = "theory"  # Theoretical/conceptual corrections
    GENERAL = "general"  # Uncategorized corrections


@dataclass
class CorrectionRecord:
    """Represents a single correction record with full metadata."""

    id: int
    original_query: str
    correction_text: str
    category: CorrectionCategory
    component_id: str | None  # Associated component (e.g., "R101", "U5")
    timestamp: str
    applied_count: int
    last_applied: str | None
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "original_query": self.original_query,
            "correction_text": self.correction_text,
            "category": self.category.value,
            "component_id": self.component_id,
            "timestamp": self.timestamp,
            "applied_count": self.applied_count,
            "last_applied": self.last_applied,
            "tags": self.tags,
        }


@dataclass
class CategoryStats:
    """Statistics for a specific correction category."""

    category: CorrectionCategory
    total_corrections: int
    total_applications: int
    unique_components: int
    recent_count_7d: int
    recent_count_30d: int


@dataclass
class CorrectionContext:
    """Result from retrieving correction context with transparency tracking."""

    context_text: str
    used_correction_ids: list[int]
    total_corrections_available: int
    weighted_score_sum: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_text": self.context_text,
            "used_correction_ids": self.used_correction_ids,
            "total_corrections_available": self.total_corrections_available,
            "weighted_score_sum": self.weighted_score_sum,
        }


@dataclass
class TeachBackSummary:
    """Summary of corrections for teach-back/verification."""

    total_corrections: int
    by_category: dict[str, int]
    top_components: list[tuple[str, int]]
    recent_corrections: list[CorrectionRecord]
    frequent_mistakes: list[tuple[str, int]]  # (pattern, count)
    finetune_recommended: bool

    def format_summary(self) -> str:
        """Format as human-readable summary."""
        lines = [
            "📚 CORRECTION SUMMARY",
            f"Total corrections: {self.total_corrections}",
            f"Finetune recommended: {'Yes' if self.finetune_recommended else 'No'}",
            "",
            "By Category:",
        ]
        for cat, count in self.by_category.items():
            lines.append(f"  - {cat}: {count}")

        if self.top_components:
            lines.extend(["", "Top Components with Corrections:"])
            for comp, count in self.top_components[:5]:
                lines.append(f"  - {comp}: {count} corrections")

        if self.frequent_mistakes:
            lines.extend(["", "Frequent Mistake Patterns:"])
            for pattern, count in self.frequent_mistakes[:5]:
                lines.append(f"  - {pattern}: {count} times")

        return "\n".join(lines)


class CorrectionMemory:
    """
    Extended correction memory with categorization, tracking, and weighted retrieval.

    Features:
    - Categories: Component ID, Procedure, Safety, Theory, General
    - Per-category and per-component correction counting
    - Finetune trigger at 50 total corrections
    - 5x weighting for correction retrieval vs other memory
    - Teach-back summary generation
    - Transparency: tracks which corrections were used in context
    """

    # Configuration constants
    FINETUNE_THRESHOLD = 50
    CORRECTION_WEIGHT_MULTIPLIER = 5.0
    DEFAULT_MAX_ITEMS = 3
    TEACHBACK_RECENT_DAYS = 30

    def __init__(self, db_path: str = "data/corrections.db", persist_dir: str = "./data/chroma"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

        # Initialize ChromaDB for context snapshots
        self.persist_dir = persist_dir
        self.collection = None
        if CHROMA_AVAILABLE:
            try:
                from .chroma_manager import ChromaDBManager
                settings = Settings(anonymized_telemetry_enabled=False)
                self.client = ChromaDBManager.get_client(self.persist_dir, settings)
                self.collection = ChromaDBManager.get_collection(
                    self.persist_dir, "context_snapshots", settings
                )
            except Exception as e:
                print(f"⚠️  Failed to initialize ChromaDB for snapshots: {e}")

    def _init_db(self):
        """Initialize database with extended schema."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                # Main corrections table with category and component tracking
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS corrections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        original_query TEXT NOT NULL,
                        correction_text TEXT NOT NULL,
                        category TEXT DEFAULT 'general',
                        component_id TEXT,
                        timestamp TEXT NOT NULL,
                        applied_count INTEGER DEFAULT 1,
                        last_applied TEXT,
                        tags TEXT DEFAULT '[]'
                    )
                """)
                # Idempotent migration: add scope column if not present
                try:
                    conn.execute("ALTER TABLE corrections ADD COLUMN scope TEXT DEFAULT 'durable'")
                    conn.commit()
                except Exception:
                    pass  # Column already exists

                # Track which corrections were used in context generation
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS correction_usage_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        correction_id INTEGER NOT NULL,
                        query_text TEXT,
                        timestamp TEXT NOT NULL,
                        context_included INTEGER DEFAULT 1,
                        FOREIGN KEY (correction_id) REFERENCES corrections(id)
                    )
                """)

                # Migration: add missing columns if DB exists from older schema
                try:
                    conn.execute("ALTER TABLE corrections ADD COLUMN category TEXT DEFAULT 'general'")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                try:
                    conn.execute("ALTER TABLE corrections ADD COLUMN component_id TEXT")
                except sqlite3.OperationalError:
                    pass
                try:
                    conn.execute("ALTER TABLE corrections ADD COLUMN last_applied TEXT")
                except sqlite3.OperationalError:
                    pass

                # Indices for efficient querying
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_corrections_category
                    ON corrections(category)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_corrections_component
                    ON corrections(component_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_corrections_applied
                    ON corrections(applied_count DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_corrections_timestamp
                    ON corrections(timestamp)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_usage_correction
                    ON correction_usage_log(correction_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_usage_timestamp
                    ON correction_usage_log(timestamp)
                """)

                conn.commit()

    def add_correction(
        self,
        original_query: str,
        correction: str,
        category: CorrectionCategory = CorrectionCategory.GENERAL,
        component_id: str | None = None,
        tags: list[str] | None = None,
    ) -> int:
        """
        Add a new correction with category and optional component association.

        Args:
            original_query: The original (incorrect) query/response
            correction: The corrected text
            category: Category of correction (component_id, procedure, safety, theory, general)
            component_id: Associated component (e.g., "R101", "U5", "IC1")
            tags: Additional tags for filtering

        Returns:
            The ID of the created correction record
        """
        now = datetime.now().isoformat()

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO corrections
                    (original_query, correction_text, category, component_id, timestamp, tags)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        original_query,
                        correction,
                        category.value,
                        component_id,
                        now,
                        json.dumps(tags or []),
                    ),
                )
                conn.commit()
                return cursor.lastrowid or 0

    def get_relevant_context(
        self,
        current_query: str,
        max_items: int = 3,
        component_filter: str | None = None,
        category_filter: CorrectionCategory | None = None,
    ) -> CorrectionContext:
        """
        Retrieve relevant corrections with 5x weighting and transparency tracking.

        Args:
            current_query: The current query to find relevant corrections for
            max_items: Maximum number of corrections to include
            component_filter: Optional filter by specific component
            category_filter: Optional filter by category

        Returns:
            CorrectionContext with context text and transparency metadata
        """
        query_words = set(re.findall(r"[A-Za-z0-9]+", current_query.lower()))

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                # Build query with optional filters
                sql = (
                    "SELECT id, original_query, correction_text, applied_count, "
                    "category, component_id, timestamp FROM corrections WHERE 1=1"
                )
                params = []

                if component_filter:
                    sql += " AND component_id = ?"
                    params.append(component_filter)

                if category_filter:
                    sql += " AND category = ?"
                    params.append(category_filter.value)

                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()

        # Score corrections with recency + frequency weighting
        now_ts = datetime.now()
        scored = []
        for row_id, orig, corr, count, cat, comp, ts_str in rows:
            orig_words = set(re.findall(r"[A-Za-z0-9]+", orig.lower()))
            corr_words = set(re.findall(r"[A-Za-z0-9]+", corr.lower()))
            overlap = len(query_words & (orig_words | corr_words))

            if overlap > 0 or component_filter or category_filter:
                # 1. Base score from word overlap
                base_score = overlap

                # 2. Recency decay — corrections from the last 30 days get 2x boost,
                #    older corrections decay exponentially (half-life: 60 days)
                try:
                    correction_ts = datetime.fromisoformat(ts_str)
                    days_old = max(0, (now_ts - correction_ts).days)
                except Exception:
                    days_old = 999  # very old if timestamp is invalid
                recency_factor = 2.0 if days_old <= 30 else 2.0 * (0.5 ** (days_old / 60.0))

                # 3. Frequency boost — each prior application adds 15% (was 10%)
                frequency_factor = 1 + 0.15 * count

                # Combine and apply 5x correction weighting
                weighted_score = base_score * recency_factor * frequency_factor * self.CORRECTION_WEIGHT_MULTIPLIER

                scored.append((weighted_score, row_id, orig, corr, cat, comp))

        # Sort by weighted score and take top items
        scored.sort(reverse=True)
        top_items = scored[:max_items]

        # Build context text and track used corrections
        context_parts = []
        used_ids = []
        total_score = 0.0

        for score, row_id, orig, corr, cat, comp in top_items:
            used_ids.append(row_id)
            total_score += score

            # Format with category and component info for transparency
            prefix = "Past correction"
            if comp:
                prefix += f" [{comp}]"
            if cat != CorrectionCategory.GENERAL.value:
                prefix += f" ({cat})"

            context_parts.append(f"{prefix}: {corr}")

            # Log usage for transparency
            self._log_correction_usage(row_id, current_query)

        context_text = "\n".join(context_parts) if context_parts else ""

        return CorrectionContext(
            context_text=context_text,
            used_correction_ids=used_ids,
            total_corrections_available=len(rows),
            weighted_score_sum=total_score,
        )

    def get_relevant_context_text(
        self,
        current_query: str,
        max_items: int = 3,
        component_filter: str | None = None,
        category_filter: CorrectionCategory | None = None,
    ) -> str:
        """
        Convenience method returning just the context text (backward compatible).

        Returns:
            Formatted context string or empty string if no relevant corrections
        """
        context = self.get_relevant_context(
            current_query, max_items, component_filter, category_filter
        )
        return context.context_text

    def _log_correction_usage(self, correction_id: int, query_text: str):
        """Log that a correction was used in context generation."""
        now = datetime.now().isoformat()

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO correction_usage_log (correction_id, query_text, timestamp)
                    VALUES (?, ?, ?)
                    """,
                    (correction_id, query_text, now),
                )
                conn.commit()

    def increment_usage(self, correction_id: int):
        """
        Increment the applied_count for a correction and update last_applied.
        """
        now = datetime.now().isoformat()

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE corrections
                    SET applied_count = applied_count + 1, last_applied = ?
                    WHERE id = ?
                    """,
                    (now, correction_id),
                )
                conn.commit()

    def get_correction_stats(self) -> dict[str, Any]:
        """
        Get comprehensive correction statistics.

        Returns:
            Dict with total count, per-category stats, and finetune recommendation
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                # Total count
                total = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]

                # Count per category
                cat_counts = conn.execute(
                    "SELECT category, COUNT(*) FROM corrections GROUP BY category"
                ).fetchall()

                # Count per component
                comp_counts = conn.execute(
                    """
                    SELECT component_id, COUNT(*)
                    FROM corrections
                    WHERE component_id IS NOT NULL
                    GROUP BY component_id
                    ORDER BY COUNT(*) DESC
                    """
                ).fetchall()

                # Total applications
                total_applications = conn.execute(
                    "SELECT COALESCE(SUM(applied_count), 0) FROM corrections"
                ).fetchone()[0]

                # Recent corrections (30 days)
                thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
                recent_count = conn.execute(
                    "SELECT COUNT(*) FROM corrections WHERE timestamp > ?", (thirty_days_ago,)
                ).fetchone()[0]

        return {
            "total_corrections": total,
            "by_category": {cat: count for cat, count in cat_counts},
            "by_component": {comp: count for comp, count in comp_counts if comp},
            "total_applications": total_applications,
            "recent_corrections_30d": recent_count,
            "finetune_recommended": total >= self.FINETUNE_THRESHOLD,
            "finetune_threshold": self.FINETUNE_THRESHOLD,
            "corrections_until_finetune": max(0, self.FINETUNE_THRESHOLD - total),
        }

    def get_category_stats(self, category: CorrectionCategory) -> CategoryStats:
        """
        Get detailed statistics for a specific category.
        """
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                # Total in category
                total = conn.execute(
                    "SELECT COUNT(*) FROM corrections WHERE category = ?", (category.value,)
                ).fetchone()[0]

                # Total applications
                applications = conn.execute(
                    """
                    SELECT COALESCE(SUM(applied_count), 0)
                    FROM corrections WHERE category = ?
                    """,
                    (category.value,),
                ).fetchone()[0]

                # Unique components
                unique_components = conn.execute(
                    """
                    SELECT COUNT(DISTINCT component_id)
                    FROM corrections
                    WHERE category = ? AND component_id IS NOT NULL
                    """,
                    (category.value,),
                ).fetchone()[0]

                # Recent counts
                recent_7d = conn.execute(
                    """
                    SELECT COUNT(*) FROM corrections
                    WHERE category = ? AND timestamp > ?
                    """,
                    (category.value, seven_days_ago),
                ).fetchone()[0]

                recent_30d = conn.execute(
                    """
                    SELECT COUNT(*) FROM corrections
                    WHERE category = ? AND timestamp > ?
                    """,
                    (category.value, thirty_days_ago),
                ).fetchone()[0]

        return CategoryStats(
            category=category,
            total_corrections=total,
            total_applications=applications,
            unique_components=unique_components,
            recent_count_7d=recent_7d,
            recent_count_30d=recent_30d,
        )

    def should_trigger_finetune(self) -> tuple[bool, dict[str, Any]]:
        """
        Check if finetune should be triggered based on correction count.

        Returns:
            Tuple of (should_trigger, details_dict)
        """
        stats = self.get_correction_stats()
        total = stats["total_corrections"]

        should_trigger = total >= self.FINETUNE_THRESHOLD

        details = {
            "total_corrections": total,
            "threshold": self.FINETUNE_THRESHOLD,
            "should_trigger": should_trigger,
            "by_category": stats["by_category"],
            "corrections_until_finetune": max(0, self.FINETUNE_THRESHOLD - total),
            "recommendation": (
                f"Finetune recommended: {total} corrections accumulated"
                if should_trigger
                else f"{self.FINETUNE_THRESHOLD - total} more corrections needed for finetune consideration"
            ),
        }

        return should_trigger, details

    def generate_teach_back_summary(self) -> TeachBackSummary:
        """
        Generate a comprehensive teach-back summary of all corrections.

        Returns:
            TeachBackSummary with statistics and frequent patterns
        """
        stats = self.get_correction_stats()

        # Get recent corrections
        recent_cutoff = (datetime.now() - timedelta(days=self.TEACHBACK_RECENT_DAYS)).isoformat()

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                # Recent corrections as records
                conn.row_factory = sqlite3.Row
                recent_rows = conn.execute(
                    """
                    SELECT * FROM corrections
                    WHERE timestamp > ?
                    ORDER BY timestamp DESC
                    LIMIT 10
                    """,
                    (recent_cutoff,),
                ).fetchall()

                recent_corrections = [
                    CorrectionRecord(
                        id=row["id"],
                        original_query=row["original_query"],
                        correction_text=row["correction_text"],
                        category=CorrectionCategory(row["category"]),
                        component_id=row["component_id"],
                        timestamp=row["timestamp"],
                        applied_count=row["applied_count"],
                        last_applied=row["last_applied"],
                        tags=json.loads(row["tags"]),
                    )
                    for row in recent_rows
                ]

                # Top components
                comp_rows = conn.execute(
                    """
                    SELECT component_id, COUNT(*) as cnt
                    FROM corrections
                    WHERE component_id IS NOT NULL
                    GROUP BY component_id
                    ORDER BY cnt DESC
                    LIMIT 5
                    """
                ).fetchall()
                top_components = [(row[0], row[1]) for row in comp_rows]

                # Frequent mistakes (from original_query patterns)
                # Simple pattern: first few words of query
                mistake_rows = conn.execute(
                    """
                    SELECT original_query, COUNT(*) as cnt
                    FROM corrections
                    GROUP BY original_query
                    HAVING cnt > 1
                    ORDER BY cnt DESC
                    LIMIT 5
                    """
                ).fetchall()
                frequent_mistakes = [(row[0][:50] + "...", row[1]) for row in mistake_rows]

        return TeachBackSummary(
            total_corrections=stats["total_corrections"],
            by_category=stats["by_category"],
            top_components=top_components,
            recent_corrections=recent_corrections,
            frequent_mistakes=frequent_mistakes,
            finetune_recommended=stats["finetune_recommended"],
        )

    def get_corrections_by_component(self, component_id: str) -> list[CorrectionRecord]:
        """
        Get all corrections associated with a specific component.
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM corrections WHERE component_id = ? ORDER BY timestamp DESC",
                    (component_id,),
                ).fetchall()

                return [
                    CorrectionRecord(
                        id=row["id"],
                        original_query=row["original_query"],
                        correction_text=row["correction_text"],
                        category=CorrectionCategory(row["category"]),
                        component_id=row["component_id"],
                        timestamp=row["timestamp"],
                        applied_count=row["applied_count"],
                        last_applied=row["last_applied"],
                        tags=json.loads(row["tags"]),
                    )
                    for row in rows
                ]

    def get_correction_by_id(self, correction_id: int) -> CorrectionRecord | None:
        """
        Get a single correction by ID.
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM corrections WHERE id = ?", (correction_id,)
                ).fetchone()

                if not row:
                    return None

                return CorrectionRecord(
                    id=row["id"],
                    original_query=row["original_query"],
                    correction_text=row["correction_text"],
                    category=CorrectionCategory(row["category"]),
                    component_id=row["component_id"],
                    timestamp=row["timestamp"],
                    applied_count=row["applied_count"],
                    last_applied=row["last_applied"],
                    tags=json.loads(row["tags"]),
                )

    def get_usage_transparency_report(
        self, correction_ids: list[int] | None = None, since: str | None = None
    ) -> dict[str, Any]:
        """
        Get transparency report showing which corrections were used and when.

        Args:
            correction_ids: Optional list of specific correction IDs to report on
            since: Optional ISO timestamp to filter from

        Returns:
            Dict with usage statistics and timeline
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                sql = """
                    SELECT cul.correction_id, cul.query_text, cul.timestamp,
                           c.correction_text, c.category
                    FROM correction_usage_log cul
                    JOIN corrections c ON cul.correction_id = c.id
                    WHERE 1=1
                """
                params = []

                if correction_ids:
                    placeholders = ",".join("?" * len(correction_ids))
                    sql += f" AND cul.correction_id IN ({placeholders})"
                    params.extend(correction_ids)

                if since:
                    sql += " AND cul.timestamp > ?"
                    params.append(since)

                sql += " ORDER BY cul.timestamp DESC"

                rows = conn.execute(sql, params).fetchall()

                # Count usage per correction
                usage_counts = {}
                for row in rows:
                    cid = row[0]
                    usage_counts[cid] = usage_counts.get(cid, 0) + 1

        return {
            "total_usage_events": len(rows),
            "unique_corrections_used": len(usage_counts),
            "usage_by_correction": usage_counts,
            "recent_usage": [
                {
                    "correction_id": row[0],
                    "query_text": row[1][:100] + "..." if len(row[1]) > 100 else row[1],
                    "timestamp": row[2],
                    "correction_preview": row[3][:50] + "..." if len(row[3]) > 50 else row[3],
                    "category": row[4],
                }
                for row in rows[:20]  # Last 20 usages
            ],
        }

    def export_for_backup(self) -> list[dict[str, Any]]:
        """
        Export all corrections for backup purposes.
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM corrections")
                return [
                    {
                        "id": row["id"],
                        "original_query": row["original_query"],
                        "correction_text": row["correction_text"],
                        "category": row["category"],
                        "component_id": row["component_id"],
                        "timestamp": row["timestamp"],
                        "applied_count": row["applied_count"],
                        "last_applied": row["last_applied"],
                        "tags": json.loads(row["tags"]),
                    }
                    for row in cursor.fetchall()
                ]

    def import_from_backup(self, corrections: list[dict[str, Any]]) -> int:
        """
        Import corrections from a backup.

        Returns:
            Number of corrections imported
        """
        count = 0

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                for corr in corrections:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO corrections
                        (id, original_query, correction_text, category, component_id,
                         timestamp, applied_count, last_applied, tags)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            corr.get("id"),
                            corr["original_query"],
                            corr["correction_text"],
                            corr.get("category", "general"),
                            corr.get("component_id"),
                            corr["timestamp"],
                            corr.get("applied_count", 1),
                            corr.get("last_applied"),
                            json.dumps(corr.get("tags", [])),
                        ),
                    )
                    count += 1

                conn.commit()

        return count

    def capture_context_snapshot(self, user_message: str, domain: str):
        """
        Silently log emotional tone, topics, identity signals, and open loops.
        This is non-blocking and should be called asynchronously after each user message.
        """
        if not CHROMA_AVAILABLE or self.collection is None:
            return None

        # Simple sentiment analysis
        try:
            blob = TextBlob(user_message)
            sentiment_score = blob.sentiment.polarity  # -1.0 to 1.0

            # Extract key topics (basic noun phrase extraction)
            topics = [np for np in blob.noun_phrases if len(np) > 2][:5]
        except Exception:
            sentiment_score = 0.0
            topics = []

        # Detect identity signals (e.g., "I used to X but now I Y")
        identity_signals = []
        if "used to" in user_message.lower() and "but now" in user_message.lower():
            identity_signals.append("identity_shift")

        # Detect open loops (mentions of projects without closure)
        open_loops = []
        project_keywords = ["project", "podcast", "repair", "build", "fix", "tracking", "ridgeline", "amp"]
        for kw in project_keywords:
            if kw in user_message.lower():
                open_loops.append(kw)

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "domain": domain,
            "sentiment": sentiment_score,
            "sentiment_label": "positive" if sentiment_score > 0.1 else "negative" if sentiment_score < -0.1 else "neutral",
            "topics": topics,
            "identity_signals": identity_signals,
            "open_loops": open_loops,
            "raw_message": user_message[:500]  # truncated for reference
        }

        # Store in ChromaDB with a dedicated type
        self.collection.add(
            documents=[user_message],
            metadatas=[{"type": "context_snapshot", "snapshot": json.dumps(snapshot)}],
            ids=[f"snapshot_{datetime.now().timestamp()}_{uuid.uuid4().hex[:6]}"]
        )

        return snapshot

    def get_recent_snapshots(self, days: int = 7, limit: int = 5):
        """
        Retrieve context snapshots from the last N days, sorted by recency.
        Returns a list of snapshot dicts.
        """
        if not CHROMA_AVAILABLE or self.collection is None:
            return []

        # ChromaDB doesn't support date filtering natively, so we query more and filter
        try:
            results = self.collection.get(
                where={"type": "context_snapshot"},
                limit=limit * 3  # get extra to filter
            )
        except Exception:
            return []

        snapshots = []
        cutoff = datetime.now().timestamp() - (days * 24 * 3600)

        for meta in results['metadatas']:
            snap = json.loads(meta['snapshot'])
            try:
                ts = datetime.fromisoformat(snap['timestamp']).timestamp()
                if ts >= cutoff:
                    snapshots.append(snap)
            except Exception:
                continue

        # Sort by timestamp descending and take limit
        snapshots.sort(key=lambda x: x['timestamp'], reverse=True)
        return snapshots[:limit]


__all__ = [
    "CorrectionMemory",
    "CorrectionCategory",
    "CorrectionRecord",
    "CategoryStats",
    "CorrectionContext",
    "TeachBackSummary",
]
