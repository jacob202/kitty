"""
Predictive Context Prefetcher for Kitty.

Captures behavioral "fingerprint" (time, git branch, recent files, bluetooth)
Matches against historical patterns
Preloads relevant context before user asks

Architecture:
1. FingerprintCapture - captures current behavioral fingerprint
2. PatternMatcher - stores fingerprints in SQLite with cosine similarity
3. ContextLoader - loads MemoryWeave facts and relevant files
4. PredictivePrefetcher - main API with caching
"""

import hashlib
import json
import math
import sqlite3
import subprocess
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.core.db_config import get_db_path

# Register database
_DB_PATH = get_db_path("prefetcher")
_lock = threading.Lock()


def _init_db():
    """Initialize prefetcher database with WAL mode."""
    _DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(str(_DB_PATH)) as c:
        c.execute("PRAGMA journal_mode=WAL")

        # Fingerprint patterns (learned over time)
        c.execute("""
            CREATE TABLE IF NOT EXISTS fingerprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time_slot TEXT NOT NULL,
                weekday INTEGER NOT NULL,
                git_branch TEXT NOT NULL,
                recent_files_hash TEXT NOT NULL,
                bluetooth_devices_hash TEXT NOT NULL,
                context_bucket TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                access_count INTEGER DEFAULT 1,
                UNIQUE(time_slot, weekday, git_branch, recent_files_hash, bluetooth_devices_hash)
            )
        """)

        # Context bucket mappings (which files/facts to load for each pattern)
        c.execute("""
            CREATE TABLE IF NOT EXISTS context_buckets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bucket_name TEXT NOT NULL UNIQUE,
                memory_weave_facts TEXT NOT NULL,
                relevant_files TEXT NOT NULL,
                last_updated TEXT
            )
        """)

        # Learned associations
        c.execute("""
            CREATE TABLE IF NOT EXISTS learned_associations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint_id INTEGER NOT NULL,
                bucket_name TEXT NOT NULL,
                success_count INTEGER DEFAULT 1,
                last_success TEXT,
                FOREIGN KEY (fingerprint_id) REFERENCES fingerprints(id)
            )
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_fp_time ON fingerprints(time_slot)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fp_branch ON fingerprints(git_branch)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_bucket_name ON context_buckets(bucket_name)")


# Initialize on import
_init_db()


# ============================================================================
# Part 1: FingerprintCapture
# ============================================================================


@dataclass
class BehavioralFingerprint:
    """Captured behavioral fingerprint."""

    time_slot: str  # HH:MM (rounded to 15min blocks)
    weekday: int  # 0=Monday, 6=Sunday
    git_branch: str  # Current git branch
    recent_files: list[str]  # Top 3 recently modified files
    bluetooth_devices: list[str]  # Connected bluetooth devices

    # Computed hashes for database storage
    recent_files_hash: str = ""
    bluetooth_devices_hash: str = ""

    def __post_init__(self):
        """Compute hashes after initialization."""
        self.recent_files_hash = self._hash_list(self.recent_files)
        self.bluetooth_devices_hash = self._hash_list(self.bluetooth_devices)

    @staticmethod
    def _hash_list(items: list[str]) -> str:
        """Create deterministic hash from list."""
        if not items:
            return "none"
        combined = "|".join(sorted(items))
        return hashlib.sha256(combined.encode()).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class FingerprintCapture:
    """Captures behavioral fingerprint for prediction."""

    def __init__(self):
        self._git_cache: tuple[str, float] | None = None
        self._files_cache: tuple[list[str], float] | None = None
        self._bluetooth_cache: tuple[list[str], float] | None = None
        self._cache_ttl: float = 30.0  # 30 second TTL for captures

    def capture(self) -> BehavioralFingerprint:
        """Capture current behavioral fingerprint."""
        now = datetime.now()

        return BehavioralFingerprint(
            time_slot=self._get_time_slot(now),
            weekday=now.weekday(),
            git_branch=self._get_git_branch(),
            recent_files=self._get_recent_files(),
            bluetooth_devices=self._get_bluetooth_devices(),
        )

    def _get_time_slot(self, now: datetime) -> str:
        """Round time to 15-minute slot."""
        minute = (now.minute // 15) * 15
        return f"{now.hour:02d}:{minute:02d}"

    def _get_git_branch(self) -> str:
        """Get current git branch (cached)."""
        now = datetime.now().timestamp()

        # Check cache
        if self._git_cache:
            branch, timestamp = self._git_cache
            if now - timestamp < self._cache_ttl:
                return branch

        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=2,
            )
            branch = result.stdout.strip() or "none"
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            branch = "none"

        self._git_cache = (branch, now)
        return branch

    def _get_recent_files(self) -> list[str]:
        """Get top 3 recently modified files (cached)."""
        now = datetime.now().timestamp()

        if self._files_cache:
            files, timestamp = self._files_cache
            if now - timestamp < self._cache_ttl:
                return files

        try:
            # Use git to get recently modified files
            result = subprocess.run(
                ["git", "status", "-s", "--porcelain"],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=2,
            )
            files = []
            for line in result.stdout.strip().split("\n")[:10]:
                if line:
                    # Parse: status  path
                    parts = line.split(" ", 1)
                    if len(parts) == 2:
                        path = parts[1].strip()
                        if path and not path.startswith("."):
                            files.append(path)

            # Get top 3 unique
            files = list(dict.fromkeys(files))[:3]
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            files = []

        self._files_cache = (files, now)
        return files

    def _get_bluetooth_devices(self) -> list[str]:
        """Get connected bluetooth devices (cached)."""
        now = datetime.now().timestamp()

        if self._bluetooth_cache:
            devices, timestamp = self._bluetooth_cache
            if now - timestamp < self._cache_ttl:
                return devices

        devices = []

        # Try blueutil on macOS
        try:
            result = subprocess.run(
                ["blueutil", "--connected", "--format", "json"],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                devices = [d.get("name", d.get("address", "unknown")) for d in data]
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass

        # Fallback: try system_profiler
        if not devices:
            try:
                result = subprocess.run(
                    ["system_profiler", "SPBluetoothDataType"],
                    cwd=Path.cwd(),
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                # Parse for connected devices
                lines = result.stdout.split("\n")
                in_connected = False
                for line in lines:
                    if "Connected:" in line:
                        in_connected = True
                    elif in_connected and line.strip().startswith("{"):
                        break
                    elif in_connected and ":" in line:
                        name = line.split(":", 1)[1].strip()
                        if name:
                            devices.append(name)
            except Exception:
                pass

        self._bluetooth_cache = (devices, now)
        return devices


# ============================================================================
# Part 2: PatternMatcher
# ============================================================================


class PatternMatcher:
    """Matches fingerprints against historical patterns using cosine similarity."""

    def __init__(self):
        self._fingerprint_cache: tuple[BehavioralFingerprint, float] | None = None
        self._cache_ttl: float = 5.0  # Short TTL for matching

    def store_fingerprint(self, fp: BehavioralFingerprint, context_bucket: str) -> int:
        """Store fingerprint and return database ID."""
        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                c.execute("PRAGMA journal_mode=WAL")

                # Try insert, update on conflict
                try:
                    c.execute(
                        """
                        INSERT INTO fingerprints (
                            time_slot, weekday, git_branch,
                            recent_files_hash, bluetooth_devices_hash,
                            context_bucket, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            fp.time_slot,
                            fp.weekday,
                            fp.git_branch,
                            fp.recent_files_hash,
                            fp.bluetooth_devices_hash,
                            context_bucket,
                            datetime.now().isoformat(),
                        ),
                    )
                    fp_id = c.lastrowid
                except sqlite3.IntegrityError:
                    # Already exists, get ID and increment access count
                    c.execute(
                        """
                        SELECT id FROM fingerprints WHERE
                            time_slot = ? AND weekday = ? AND git_branch = ? AND
                            recent_files_hash = ? AND bluetooth_devices_hash = ?
                    """,
                        (
                            fp.time_slot,
                            fp.weekday,
                            fp.git_branch,
                            fp.recent_files_hash,
                            fp.bluetooth_devices_hash,
                        ),
                    )
                    row = c.fetchone()
                    fp_id = row[0] if row else None

                    if fp_id:
                        c.execute(
                            """
                            UPDATE fingerprints SET access_count = access_count + 1
                            WHERE id = ?
                        """,
                            (fp_id,),
                        )

                return fp_id

    def find_best_match(self, fp: BehavioralFingerprint) -> dict[str, Any] | None:
        """Find best matching pattern using cosine similarity."""
        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                c.execute("PRAGMA journal_mode=WAL")

                # Get all fingerprints
                c.execute("""
                    SELECT id, time_slot, weekday, git_branch, recent_files_hash,
                           bluetooth_devices_hash, context_bucket, access_count
                    FROM fingerprints
                    WHERE access_count >= 1
                """)
                rows = c.fetchall()

                if not rows:
                    return None

                best_match = None
                best_score = -1.0

                for row in rows:
                    score = self._cosine_similarity(
                        fp,
                        {
                            "time_slot": row[1],
                            "weekday": row[2],
                            "git_branch": row[3],
                            "recent_files_hash": row[4],
                            "bluetooth_devices_hash": row[5],
                        },
                    )

                    if score > best_score:
                        best_score = score
                        best_match = {
                            "id": row[0],
                            "time_slot": row[1],
                            "weekday": row[2],
                            "git_branch": row[3],
                            "context_bucket": row[6],
                            "access_count": row[7],
                            "similarity": score,
                        }

                return best_match if best_match and best_match["similarity"] > 0.3 else None

    def _cosine_similarity(self, fp: BehavioralFingerprint, stored: dict[str, str]) -> float:
        """Calculate cosine similarity between fingerprints."""
        # Build feature vectors
        fp_vec = self._fingerprint_to_vector(fp)
        stored_vec = self._stored_to_vector(stored)

        # Cosine similarity
        dot = sum(a * b for a, b in zip(fp_vec, stored_vec))
        mag_fp = math.sqrt(sum(a * a for a in fp_vec))
        mag_stored = math.sqrt(sum(a * a for a in stored_vec))

        if mag_fp == 0 or mag_stored == 0:
            return 0.0

        return dot / (mag_fp * mag_stored)

    def _fingerprint_to_vector(self, fp: BehavioralFingerprint) -> list[float]:
        """Convert fingerprint to feature vector."""
        # Hash-based features for flexibility
        vec = []

        # Time slot (hour only)
        hour = int(fp.time_slot.split(":")[0])
        vec.append(hour / 24.0)

        # Weekday
        vec.append(fp.weekday / 6.0)

        # Git branch (hash-based - normalized)
        branch_hash = int(hashlib.md5(fp.git_branch.encode()).hexdigest()[:8], 16)
        vec.append((branch_hash % 100) / 100.0)

        # Recent files similarity indicator
        vec.append(1.0 if fp.recent_files else 0.0)

        # Bluetooth devices indicator
        vec.append(1.0 if fp.bluetooth_devices else 0.0)

        return vec

    def _stored_to_vector(self, stored: dict[str, str]) -> list[float]:
        """Convert stored pattern to feature vector."""
        vec = []

        # Time slot
        time_slot = stored.get("time_slot", "00:00")
        hour = int(time_slot.split(":")[0])
        vec.append(hour / 24.0)

        # Weekday
        weekday = int(stored.get("weekday", 0))
        vec.append(weekday / 6.0)

        # Git branch
        branch = stored.get("git_branch", "none")
        branch_hash = int(hashlib.md5(branch.encode()).hexdigest()[:8], 16)
        vec.append((branch_hash % 100) / 100.0)

        # Files presence indicator
        files_hash = stored.get("recent_files_hash", "none")
        vec.append(0.0 if files_hash == "none" else 1.0)

        # Bluetooth presence indicator
        bt_hash = stored.get("bluetooth_devices_hash", "none")
        vec.append(0.0 if bt_hash == "none" else 1.0)

        return vec


# ============================================================================
# Part 3: ContextLoader
# ============================================================================


class ContextLoader:
    """Loads context for matched pattern."""

    def __init__(self):
        self._weave = None

    def load_context(self, bucket_name: str) -> dict[str, Any]:
        """Load MemoryWeave facts and relevant files for bucket."""
        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                c.execute("PRAGMA journal_mode=WAL")

                c.execute(
                    """
                    SELECT memory_weave_facts, relevant_files
                    FROM context_buckets
                    WHERE bucket_name = ?
                """,
                    (bucket_name,),
                )

                row = c.fetchone()

                if row:
                    json.loads(row[0])
                    files = json.loads(row[1])
                else:
                    files = []

        # Load from MemoryWeave if available
        weave_facts = self._load_weave_facts(bucket_name)

        return {
            "bucket_name": bucket_name,
            "memory_weave_facts": weave_facts,
            "relevant_files": files,
            "loaded_at": datetime.now().isoformat(),
        }

    def _load_weave_facts(self, bucket_name: str) -> dict[str, Any]:
        """Load facts from MemoryWeave."""
        try:
            from src.memory.memory_weave import get_weave

            weave = get_weave()

            # Query common patterns based on bucket
            facts = {}

            # Get recent failures for this bucket context
            events = weave.get_events(event_type="failure", limit=5)
            facts["recent_failures"] = [
                {"description": e.description, "severity": e.severity} for e in events
            ]

            # Get verified edges for this bucket
            edges = weave.get_edges(entity=bucket_name, limit=10)
            facts["knowledge_edges"] = [
                {
                    "entity": e.entity,
                    "relation": e.relation,
                    "value": e.value,
                    "confidence": e.confidence,
                }
                for e in edges
            ]

            return facts

        except ImportError:
            return {"error": "MemoryWeave not available"}

    def register_bucket(
        self, bucket_name: str, memory_weave_facts: dict[str, Any], relevant_files: list[str]
    ) -> None:
        """Register a new context bucket."""
        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                c.execute("PRAGMA journal_mode=WAL")

                c.execute(
                    """
                    INSERT OR REPLACE INTO context_buckets (
                        bucket_name, memory_weave_facts, relevant_files, last_updated
                    ) VALUES (?, ?, ?, ?)
                """,
                    (
                        bucket_name,
                        json.dumps(memory_weave_facts),
                        json.dumps(relevant_files),
                        datetime.now().isoformat(),
                    ),
                )


# ============================================================================
# Part 4: PredictivePrefetcher
# ============================================================================


@dataclass
class PrefetchContext:
    """Prefetched context to inject into prompt."""

    bucket_name: str
    memory_weave_facts: dict[str, Any]
    relevant_files: list[str]
    similarity_score: float
    cached: bool


class PredictivePrefetcher:
    """Main predictive prefetcher with caching."""

    _instance: Optional["PredictivePrefetcher"] = None

    def __new__(cls) -> "PredictivePrefetcher":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._capture = FingerprintCapture()
        self._matcher = PatternMatcher()
        self._loader = ContextLoader()

        # Cache for prefetch results
        self._cache: dict[str, Any] | None = None
        self._cache_timestamp: datetime | None = None
        self._cache_ttl: float = 60.0  # 1 minute TTL

        # Known context buckets (can be extended)
        self._known_buckets = {
            "coding": {
                "files": ["src/", "tests/", "*.py"],
                "facts": {"context": "coding_workflow"},
            },
            "debugging": {"files": ["data/logs/", "*.log"], "facts": {"context": "debugging_session"}},
            "review": {"files": ["./"], "facts": {"context": "code_review"}},
            "writing": {"files": ["docs/", "*.md"], "facts": {"context": "documentation"}},
            "default": {"files": ["./"], "facts": {"context": "general"}},
        }

    def prefetch(self, force_refresh: bool = False) -> PrefetchContext:
        """Prefetch context based on current fingerprint.

        Args:
            force_refresh: Force cache refresh if True

        Returns:
            PrefetchContext to inject into prompt
        """
        now = datetime.now()

        # Check cache validity
        if not force_refresh and self._cache:
            age = (
                (now - self._cache_timestamp).total_seconds()
                if self._cache_timestamp
                else float("inf")
            )
            if age < self._cache_ttl:
                return PrefetchContext(
                    bucket_name=self._cache["bucket_name"],
                    memory_weave_facts=self._cache.get("memory_weave_facts", {}),
                    relevant_files=self._cache.get("relevant_files", []),
                    similarity_score=self._cache.get("similarity_score", 0.0),
                    cached=True,
                )

        # Capture current fingerprint
        fp = self._capture.capture()

        # Find best matching pattern
        match = self._matcher.find_best_match(fp)

        if match:
            bucket_name = match["context_bucket"]
            similarity = match["similarity"]
        else:
            # No match - infer bucket from current state
            bucket_name = self._infer_bucket(fp)
            similarity = 0.0

        # Load context
        context = self._loader.load_context(bucket_name)

        # Store fingerprint for learning
        self._matcher.store_fingerprint(fp, bucket_name)

        # Build result
        result = PrefetchContext(
            bucket_name=bucket_name,
            memory_weave_facts=context.get("memory_weave_facts", {}),
            relevant_files=context.get("relevant_files", []),
            similarity_score=similarity,
            cached=False,
        )

        # Update cache
        self._cache = {
            "bucket_name": bucket_name,
            "memory_weave_facts": result.memory_weave_facts,
            "relevant_files": result.relevant_files,
            "similarity_score": similarity,
        }
        self._cache_timestamp = now

        return result

    def _infer_bucket(self, fp: BehavioralFingerprint) -> str:
        """Infer context bucket from fingerprint."""
        # Time-based inference
        hour = int(fp.time_slot.split(":")[0])

        # Check file patterns
        if fp.recent_files:
            for f in fp.recent_files:
                if any(ext in f for ext in [".py", ".ts", ".js"]):
                    return "coding"
                elif ".md" in f or "docs" in f:
                    return "writing"
                elif "test" in f.lower():
                    return "review"

        # Check git branch
        if "main" in fp.git_branch or "master" in fp.git_branch:
            return "review"

        # Time-based defaults
        if 9 <= hour < 12:
            return "coding"  # Morning = coding
        elif 14 <= hour < 17:
            return "review"  # Afternoon = reviews
        else:
            return "default"

    def get_fingerprint(self) -> BehavioralFingerprint:
        """Get current fingerprint without prefetching."""
        return self._capture.capture()

    def get_status(self) -> dict[str, Any]:
        """Get prefetcher status."""
        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                c.execute("PRAGMA journal_mode=WAL")

                c.execute("SELECT COUNT(*) FROM fingerprints")
                fp_count = c.fetchone()[0]

                c.execute("SELECT COUNT(*) FROM context_buckets")
                bucket_count = c.fetchone()[0]

        return {
            "initialized": self._initialized,
            "fingerprint_count": fp_count,
            "bucket_count": bucket_count,
            "cache_valid": self._cache is not None,
            "cache_age_seconds": (
                (datetime.now() - self._cache_timestamp).total_seconds()
                if self._cache_timestamp
                else None
            ),
        }


# Singleton accessor
def get_prefetcher() -> PredictivePrefetcher:
    """Get singleton prefetcher instance."""
    return PredictivePrefetcher()


# ============================================================================
# Integration
# ============================================================================


def prefetch(force_refresh: bool = False) -> dict[str, Any]:
    """Convenience function to prefetch context.

    Returns dict suitable for injecting into prompt context.
    """
    prefetcher = get_prefetcher()
    ctx = prefetcher.prefetch(force_refresh)

    return {
        "bucket": ctx.bucket_name,
        "facts": ctx.memory_weave_facts,
        "files": ctx.relevant_files,
        "confidence": ctx.similarity_score,
        "from_cache": ctx.cached,
    }


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Predictive Context Prefetcher")
    parser.add_argument("--status", action="store_true", help="Show prefetcher status")
    parser.add_argument("--capture", action="store_true", help="Capture fingerprint")
    parser.add_argument("--force-refresh", action="store_true", help="Force cache refresh")

    args = parser.parse_args()

    if args.status:
        prefetcher = get_prefetcher()
        status = prefetcher.get_status()
        print(json.dumps(status, indent=2))

    elif args.capture:
        fp = get_prefetcher().get_fingerprint()
        print(json.dumps(fp.to_dict(), indent=2))

    else:
        result = prefetch(force_refresh=args.force_refresh)
        print(json.dumps(result, indent=2))
